"""Build a small source-backed public-data evaluation pilot.

The downloader is deliberately not included: callers preserve the original
archives and pass a data root containing the pinned SciFact and FastAPI inputs.
Only standard-library transformations are used here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SCIFACT_IDS = [3, 42, 49, 51]
FASTAPI_COMMIT = "993899cc2021daec7ba170c7ee9bcefd45e8db43"
FASTAPI_FILES = [
    "LICENSE",
    "README.md",
    "docs/en/docs/tutorial/path-params.md",
    "docs/en/docs/tutorial/body.md",
    "docs/en/docs/tutorial/dependencies/index.md",
    "fastapi/routing.py",
    "fastapi/params.py",
    "fastapi/applications.py",
]
FASTAPI_EXCERPTS = {
    "fastapi/routing.py": [(129, 168), (397, 524), (1214, 1302)],
    "fastapi/applications.py": [(1207, 1262)],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_material(src: Path, dst: Path, source_id: str, rel: str) -> dict[str, str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return {"path": rel.replace("\\", "/"), "sha256": sha256(dst), "source_id": source_id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_root", type=Path)
    parser.add_argument("scoring_root", type=Path)
    args = parser.parse_args()
    data_root = args.data_root.resolve()
    scoring_root = args.scoring_root.resolve()

    sf = data_root / "sources" / "scifact"
    raw = sf / "raw" / "data"
    claims = [json.loads(line) for line in (raw / "claims_dev.jsonl").read_text(encoding="utf-8").splitlines()]
    corpus = {str(row["doc_id"]): row for row in
              (json.loads(line) for line in (raw / "corpus.jsonl").read_text(encoding="utf-8").splitlines())}
    by_id = {int(c["id"]): c for c in claims}
    task_rows: list[dict[str, object]] = []
    gold_rows: list[dict[str, object]] = []

    for claim_id in SCIFACT_IDS:
        claim = by_id[claim_id]
        task_id = f"scifact-{claim_id:04d}-dev"
        material_dir = data_root / "tasks" / task_id / "materials"
        evidence_docs: list[dict[str, object]] = []
        evidence_gold: list[dict[str, object]] = []
        for doc_id, rationales in claim["evidence"].items():
            source_doc = corpus[str(doc_id)]
            evidence_docs.append({
                "doc_id": int(doc_id), "title": source_doc["title"],
                "abstract": source_doc["abstract"], "structured": source_doc["structured"],
            })
            for rationale in rationales:
                evidence_gold.append({"doc_id": int(doc_id), "label": rationale["label"],
                                      "sentences": rationale["sentences"]})
        material_rel = f"tasks/{task_id}/materials/evidence-abstracts.json"
        material = data_root / material_rel
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_text(json.dumps(evidence_docs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        task_rows.append({
            "id": task_id,
            "kind": "factual-qa",
            "split": "development",
            "request": (
                "Assess the scientific claim using only the supplied source abstract(s). "
                "Return one label: SUPPORT, CONTRADICT, or NOT_ENOUGH_INFO. Give a short "
                "justification and cite the document ID and exact sentence number(s) that "
                "support your conclusion. If the supplied material is insufficient, say so.\n\n"
                f"Claim: {claim['claim']}"
            ),
            "materials": [{"path": material_rel, "sha256": sha256(material), "source_id": "scifact-v1"}],
            "metadata": {"benchmark": "SciFact", "upstream_split": "dev",
                         "upstream_claim_id": claim_id, "language": "en",
                         "task_note": "Evidence-only pilot; no retrieval corpus search is required."},
        })
        gold_rows.append({"id": task_id, "label": evidence_gold[0]["label"],
                          "evidence": evidence_gold,
                          "source_claim_id": claim_id,
                          "source_cited_doc_ids": claim.get("cited_doc_ids", [])})

    fastapi_source = data_root / "sources" / "fastapi" / "raw" / f"fastapi-{FASTAPI_COMMIT}"
    if not fastapi_source.exists():
        fastapi_source = data_root / "sources" / "fastapi" / "raw" / "fastapi-993899c"
    for task_id, kind, objective in [
        ("fastapi-routing-report-dev", "technical-report",
         "请用中文撰写一份面向工程师的正式技术报告，说明 FastAPI 路由参数与请求体的处理路径。重点覆盖：公开路由声明如何进入路由对象、路由对象如何连接请求处理器，以及所给代码如何读取表单/JSON 请求体并开始依赖解析。区分文档明确说明的内容与从代码作出的推断；引用文件路径、行号和符号。结尾列出至少两项这些材料无法回答的问题。材料经过限定摘录，不要声称覆盖完整请求生命周期。"),
        ("fastapi-routing-design-dev", "design-spec",
         "请用中文撰写正式设计说明，提出一个尚不存在的可选路由参数 `max_json_body_bytes`，用于限制单个路由可接收的 JSON 请求体字节数。先概述所给材料能证明的当前行为，再明确标注拟议的 API 位置、配置优先级、超限响应、Content-Type/空请求体边界、兼容性和测试方案。所有新行为都必须称为提案；不要声称现有 FastAPI 已实现该功能。材料经过限定摘录，指出仍需检查的源码位置。"),
    ]:
        # This pilot scopes each writer's inputs to the documentation pages and
        # line-addressed implementation fragments below. The complete pinned
        # upstream archive remains under sources/fastapi/raw for provenance.
        task_material_root = data_root / "tasks" / task_id / "materials"
        task_material_root.mkdir(parents=True, exist_ok=True)
        materials: list[dict[str, str]] = []
        scope: list[dict[str, object]] = []
        doc_files = [
            "docs/en/docs/tutorial/path-params.md",
            "docs/en/docs/tutorial/body.md",
            "docs/en/docs/tutorial/dependencies/index.md",
        ]
        for upstream_rel in doc_files:
            src = fastapi_source / Path(upstream_rel)
            task_rel = f"tasks/{task_id}/materials/{Path(upstream_rel).name}"
            copied = copy_material(src, data_root / task_rel, "fastapi-source-2026-10-20", task_rel)
            materials.append(copied)
            scope.append({"upstream_path": upstream_rel, "line_ranges": "full file",
                          "upstream_sha256": sha256(src), "material_sha256": copied["sha256"]})
        code_parts: list[str] = [
            f"# FastAPI source excerpts at commit {FASTAPI_COMMIT}\n",
            "# The excerpts retain upstream line numbers. Full source archive is preserved separately.\n",
            "# Omitted functions and modules may affect behavior; do not extrapolate beyond these ranges.\n",
        ]
        for upstream_rel, ranges in FASTAPI_EXCERPTS.items():
            src = fastapi_source / Path(upstream_rel)
            original_lines = src.read_text(encoding="utf-8").splitlines()
            for start, end in ranges:
                block = original_lines[start - 1:end]
                code_parts.append(f"\n## {upstream_rel}:{start}-{end}\n")
                code_parts.extend(f"{i}: {line}\n" for i, line in enumerate(block, start))
                scope.append({"upstream_path": upstream_rel, "line_range": f"{start}-{end}",
                              "upstream_sha256": sha256(src),
                              "excerpt_sha256": hashlib.sha256(("\n".join(block) + "\n").encode("utf-8")).hexdigest()})
        code_rel = f"tasks/{task_id}/materials/code-excerpts.md"
        code_path = data_root / code_rel
        code_path.write_text("".join(code_parts), encoding="utf-8")
        materials.append({"path": code_rel, "sha256": sha256(code_path), "source_id": "fastapi-source-2026-10-20"})
        task_rows.append({
            "id": task_id, "kind": kind, "split": "development", "request": objective,
            "materials": materials,
            "metadata": {"project": "FastAPI", "upstream_commit": FASTAPI_COMMIT,
                         "language": "zh", "task_note": "Exploratory single-project writing pilot; deliverable must be Chinese.",
                         "material_scope": scope,
                         "limitations": "Only the listed docs and code line ranges are provided. The pinned complete archive is retained for provenance, but writers should not assume access to omitted functions."},
        })
        if kind == "technical-report":
            criteria = [
                "Explains the documented route-parameter and body behavior without inventing implementation details.",
                "Traces the supplied route declaration and APIRoute excerpts into request_response/get_request_handler.",
                "Covers observed form/JSON body parsing and the beginning of dependency solving with source references.",
                "Separates documentation statements from source-based inferences and marks at least two out-of-scope questions.",
                "Delivers a coherent Chinese technical report for engineers.",
            ]
        else:
            criteria = [
                "Clearly separates evidenced current behavior from the proposed max_json_body_bytes feature.",
                "Defines an opt-in per-route interface and states how it interacts with body parsing and route registration.",
                "Specifies byte counting, JSON/content-type and empty-body boundaries, and a clear over-limit response.",
                "Discusses compatibility and tests, including boundary and malformed-input cases.",
                "Marks every new behavior as a proposal and identifies source locations needing further inspection.",
                "Delivers a coherent Chinese design specification for engineers.",
            ]
        gold_rows.append({"id": task_id, "status": "source-derived checklist; not expert-reviewed",
                          "criteria": criteria,
                          "source_commit": FASTAPI_COMMIT,
                          "review_note": "Scoring guidance only. This is not an expert-authored reference document or an endorsement of any single design."})

    tasks_path = data_root / "tasks.jsonl"
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in task_rows), encoding="utf-8")
    scoring_root.mkdir(parents=True, exist_ok=True)
    gold_path = scoring_root / "gold.jsonl"
    gold_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in gold_rows), encoding="utf-8")
    (scoring_root / "README.md").write_text(
        "# Scoring-side materials\n\n"
        "`gold.jsonl` is confidential to the scoring side and must never be mounted in a generation workspace. "
        "SciFact rows reproduce upstream labels and evidence annotations. FastAPI writing rows are an unreviewed, "
        "source-derived checklist for consistent rubric scoring; they are not expert gold, expert approval, or a "
        "canonical design.\n", encoding="utf-8")

    manifest = {
        "created_utc_date": "2026-10-20",
        "status": "pilot; incomplete full-dataset freeze",
        "data_root_relative_material_paths": True,
        "sources": [
            {"id": "scifact-v1", "name": "SciFact", "repository": "https://github.com/allenai/scifact",
             "revision": "68b98a56d93e0f9da0d2aab4e6c3294699a0f72e",
             "dataset_url": "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz",
             "dataset_file": "sources/scifact/raw/data.tar.gz", "dataset_sha256": sha256(sf / "raw" / "data.tar.gz"),
             "license": "claims/evidence CC BY 4.0; corpus abstracts ODC-By 1.0 (S2ORC)",
             "license_url": "https://github.com/allenai/scifact/blob/master/LICENSE.md",
             "selection": "4 labeled claims from claims_dev.jsonl; source abstracts retained in raw archive and task-local extracted materials."},
            {"id": "fastapi-source-2026-10-20", "name": "FastAPI", "repository": "https://github.com/fastapi/fastapi",
             "revision": FASTAPI_COMMIT,
             "archive_url": f"https://codeload.github.com/fastapi/fastapi/tar.gz/{FASTAPI_COMMIT}",
             "archive_file": f"sources/fastapi/raw/fastapi-993899c.tar.gz",
             "archive_sha256": sha256(data_root / "sources" / "fastapi" / "raw" / "fastapi-993899c.tar.gz"),
             "license": "MIT (repository license; verify any later added files against their own notices)",
             "license_url": f"https://github.com/fastapi/fastapi/blob/{FASTAPI_COMMIT}/LICENSE",
             "selection": "Complete pinned archive retained; task materials are limited to English path/body/dependency tutorial pages and line-addressed routing/application code excerpts."},
        ],
            "limitations": [
            "SciFact uses supplied gold-evidence abstracts, so this pilot does not evaluate open-corpus retrieval.",
            "SciFact's latest S3 archive is mutable; its byte hash is recorded, but upstream does not expose an immutable release identifier in this download URL.",
                "The two writing tasks are Chinese deliverables over scoped English FastAPI documentation and line-numbered source excerpts from one public project; they are development samples, not independent project-level evidence.",
            "No expert has reviewed the tasks, gold extraction, or writing outputs; these are not expert-authored gold for professional writing quality.",
                "FastAPI writing material excerpts omit the rest of the codebase; excerpt ranges and original file hashes are recorded in each task metadata and in code-excerpts.md headers.",
        ],
    }
    write_json(data_root / "dataset-manifest.json", manifest)
    write_json(scoring_root / "manifest.json", {
        "gold_file": "gold.jsonl", "gold_sha256": sha256(gold_path),
        "status": "scoring-side-only; writing checklists are source-derived and not expert-reviewed",
        "task_count": len(gold_rows),
    })
    print(f"Wrote {len(task_rows)} tasks to {tasks_path}")
    print(f"Wrote {len(gold_rows)} scoring rows outside the task data tree: {scoring_root / 'gold.jsonl'}")


if __name__ == "__main__":
    main()
