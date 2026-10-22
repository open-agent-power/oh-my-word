"""Actual CLI/LibreOffice integration trial using a frozen public FastAPI source.

Host-authored fixtures test delivery mechanics, not writing quality or runtime API
behavior. Existing public evaluation artifacts are read only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from word_skills.common import read_json, sha256, write_json
from word_skills.evidence import contract
from word_skills.ingest import ingest


QUOTES = [
    "The value of the path parameter `item_id` will be passed to your function as the argument `item_id`.",
    "You can declare the type of a path parameter in the function, using standard Python type annotations:",
    "All the data validation is performed under the hood by [Pydantic](https://pydantic.dev/docs/), so you get all the benefits from it. And you know you are in good hands.",
]
FACTS = ["路径参数 `item_id` 的值会作为同名参数传入函数。", "路径参数可以通过标准 Python 类型注解声明类型。", "教程说明，数据校验由 Pydantic 执行。"]


def invoke(args, log):
    run = subprocess.run([sys.executable, "-m", "word_skills", *map(str, args)], capture_output=True,
                         encoding="utf-8", errors="replace", timeout=180)
    write_json(log, {"argv": list(map(str, args)), "returncode": run.returncode,
                     "stdout": run.stdout, "stderr": run.stderr})
    return run.returncode


def run(source_dir, output, soffice):
    output.mkdir(parents=True, exist_ok=False)
    originals = {p: sha256(p) for p in (source_dir / "docs__en__docs__tutorial__path-params.md", source_dir / "LICENSE")}
    material = output / "public-material"
    material.mkdir()
    for path in originals:
        shutil.copyfile(path, material / path.name)
    source = material / "docs__en__docs__tutorial__path-params.md"
    text = source.read_text(encoding="utf-8")
    assert all(quote in text for quote in QUOTES)
    case = output / "case"
    index = ingest([source], case)
    segments = read_json(case / index["sources"][0]["segments"])
    claims = []
    for i, (quote, fact) in enumerate(zip(QUOTES, FACTS), 1):
        locators = [s["locator"] for s in segments if quote in s["text"]]
        assert locators, quote
        claims.append({"id": f"C{i}", "statement": fact, "source_id": "S001", "locators": locators,
                       "quote": quote, "status": "verified", "verified_by": "root-public-source-integration-fixture",
                       "verified_at": "2026-10-21"})
    write_json(case / "evidence.json", {"schema_version": 1, "claims": claims})
    write_json(material / "provenance.json", {"source": "previously frozen public FastAPI path-params tutorial",
        "upstream": "https://github.com/fastapi/fastapi", "scope": "host-authored mechanical integration fixture; no API execution or generation-quality score",
        "inputs": [{"path": str(p), "sha256": h} for p, h in originals.items()]})
    results = []
    for mode in ("technical-report", "design-spec"):
        root = output / mode
        root.mkdir()
        sections, patch = [], {"blocks": {}}
        for i, (sid, title) in enumerate(contract(mode)["required_sections"].items()):
            bid = sid + "-fact"
            blocks = [{"id": bid, "type": "paragraph", "intent": "fact", "text": FACTS[i % 3], "claim_ids": [f"C{i % 3 + 1}"]},
                {"id": sid + "-scope", "type": "paragraph", "intent": "analysis", "claim_ids": [],
                 "text": "本文为基于公开教程编写的交付链路集成样稿；此处只说明材料边界，不记录应用执行结果。" if i == 0 else
                         "设计建议：将参数声明、类型校验与接口约定分别核对，实际行为应另行执行应用测试。"}]
            if i == 2:
                blocks.append({"id": "source-table", "type": "table", "intent": "fact", "claim_ids": ["C1", "C2", "C3"],
                    "headers": ["核对项", "公开材料所述行为"], "rows": [["参数传递", FACTS[0]], ["类型声明", FACTS[1]], ["校验依据", FACTS[2]]]})
                patch["blocks"]["source-table"] = {"widths": [1, 3], "style": "Table Grid"}
            patch["blocks"][bid] = {"inline_format": "markdown"}
            sections.append({"id": sid, "title": title, "blocks": blocks})
        draft = {"schema_version": 1, "mode": mode, "title": "公开路径参数材料交付样稿", "sections": sections,
            "task_requirements": [{"id": "T-source", "text": "引用公开材料并保持正文与证据绑定", "acceptance": "所有事实段关联来源主张",
                                   "block_ids": [s["blocks"][0]["id"] for s in sections]}]}
        write_json(root / "draft.json", draft)
        write_json(root / "patch.json", patch)
        before = {p: sha256(p) for p in [root / "draft.json", *case.rglob("*")] if p.is_file()}
        assert invoke(["freeze-content", root / "draft.json", "--case", case, "--out", root / "lock"], root / "freeze-cli.json") == 0
        assert invoke(["format-content", root / "lock", "--patch", root / "patch.json", "--out", root / "formatted.json"], root / "format-cli.json") == 0
        assert invoke(["build-locked", root / "lock", "--patch", root / "patch.json", "--out", root / "build", "--soffice", soffice], root / "build-cli.json") == 0
        manifest = read_json(root / "build/delivery/manifest.json")
        assert manifest["state"] == "awaiting-review", manifest
        assert all(sha256(p) == h for p, h in before.items())
        write_json(root / "bad-patch.json", {"blocks": {sections[0]["blocks"][0]["id"]: {"text": "unapproved rewrite"}}})
        assert invoke(["build-locked", root / "lock", "--patch", root / "bad-patch.json", "--out", root / "bad-build", "--no-preview"], root / "bad-patch-cli.json") == 2
        assert not list((root / "bad-build").rglob("*.docx"))
        tampered = root / "tampered-lock"
        shutil.copytree(root / "lock", tampered)
        write_json(tampered / "case/evidence.json", {"claims": []})
        assert invoke(["build-locked", tampered, "--patch", root / "patch.json", "--out", root / "bad-source-build", "--no-preview"], root / "bad-source-cli.json") == 2
        assert not list((root / "bad-source-build").rglob("*.docx"))
        results.append({"mode": mode, "state": manifest["state"], "pages": manifest["renderer"]["pages"],
            "input_hashes_unchanged": True, "text_patch_blocked": True, "evidence_tamper_blocked": True,
            "visual_review": "pending", "delivery": str(root / "build/delivery")})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    assert all(sha256(p) == h for p, h in originals.items())
    write_json(output / "summary.json", {"scope": "public-source mechanical integration only", "cases": results})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--soffice", required=True)
    args = parser.parse_args()
    run(args.source_dir, args.out, args.soffice)
