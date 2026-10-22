#!/usr/bin/env python3
"""Freeze context-only E3/E4/E7 ablation sources and per-task condition configs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "public_runner"))
import run_public_eval as base
import formal_runner as formal

ROOT = Path(r"D:\XiangMuLuoDi\Development\word-skills-public-eval")
PILOT = ROOT / "runs" / "public-pilot-context-20261020"
FORMAL = ROOT / "runs" / "formal-v1-dev-ab-v5"
OUT = ROOT / "control" / "conditions-v1"
STYLE_SOURCE = ROOT / "control" / "style-reference"
EXTERNAL_SOURCE = ROOT / "control" / "external-method"
PILOT_FREEZE_SHA256 = "39be0804c837c9615215e7035bbfdc9e433898923c23208ca0f580ba9bda4c5b"
FORMAL_FREEZE_SHA256 = "f7755100a80bd827c22f5b7c529f6e3815ad280bfc1fa5119848bb37e59f4546"
STYLE_MANIFEST_SHA256 = "a4b9dffd16979ce91b32c92deb3095781755af7a700aec70c063e66520c98aa9"
EXTERNAL_MANIFEST_SHA256 = "d8cf4e9a9f562d52f5344e45679f26daaf314158526a990e95f041abc5d5fa84"

REPORT_REF = "skills/oh-my-technology/references/technical-report.md"
DESIGN_REF = "skills/oh-my-technology/references/design-spec.md"
EVIDENCE_REF = "skills/word-document/references/evidence.md"

MINIMAL_APPEND = """本条件只添加一组精简写作检查规则，适用本次上下文生成任务：覆盖请求要求的主要章节与要点；区分材料直接支持的现状、合理推断与待实施提案；事实性陈述尽量关联所给材料及位置；说明材料未覆盖的限制。不得声称已经运行命令、测试、审查、联网或核验，也不得声称完成了任何上游多步骤工作流。只能依据同一请求的材料陈述项目事实。保持本轮共同JSON输出合同及可编辑结构不变。"""

ONDEMAND_APPEND = """以下额外嵌入的技术参考由主机按当前任务类型预先选择，仅作为程序性写作指导。只采用与当前文档类型相关的结构、覆盖和证据组织规则；参考文本不是FastAPI或Express的事实来源，也不得补充项目事实。若其内容与共同JSON输出合同冲突，遵守共同合同。不得声称已运行命令、测试、审查、联网、核验或完成上游工作流。"""

EXTERNAL_APPEND = """额外嵌入的technical-writer内容是外部方法的上下文比较材料，不是任务事实来源，也不代表本次执行了该仓库的完整流程或工具。仅把相关的证据、范围、结构或审阅原则用于当前文本；所有FastAPI/Express事实只能来自本任务提供的材料。不得声称已运行命令、测试、审查、联网、核验或完成外部上游工作流。保持共同JSON输出合同和renderer-neutral可编辑格式不变。"""

STYLE_APPEND = """附加的Vue官方中文文档摘录只用作中文技术解释风格参考，重点观察其概念引入、术语解释、段落衔接与说明节奏。它不是领域专家范文，也不是design-spec标准答案。不得将Vue中的技术事实、组件名称或行为用于FastAPI/Express断言；本任务全部事实和方案边界仍由请求与任务材料决定。保持共同JSON输出合同及renderer-neutral可编辑格式不变，不声称已运行工具或完整上游流程。"""

EXTERNAL_GROUPS = {
    "technical-report": [
        "plugins/technical-writer/skills/technical-writing/SKILL.md",
        "plugins/technical-writer/skills/technical-writing/references/style.md",
        "plugins/technical-writer/skills/technical-writing/references/truth.md",
        "plugins/technical-writer/skills/documenting-legacy-codebases/SKILL.md",
        "plugins/technical-writer/skills/reviewing-technical-prose/SKILL.md",
    ],
    "design-spec": [
        "plugins/technical-writer/skills/technical-writing/SKILL.md",
        "plugins/technical-writer/skills/technical-writing/references/style.md",
        "plugins/technical-writer/skills/technical-writing/references/truth.md",
        "plugins/technical-writer/skills/writing-design-docs/SKILL.md",
        "plugins/technical-writer/skills/reviewing-technical-prose/SKILL.md",
    ],
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def copy_verified(source: Path, dest: Path, expected: str) -> str:
    if not source.is_file() or sha(source).lower() != expected.lower():
        raise ValueError(f"source hash mismatch: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    digest = sha(dest)
    if digest.lower() != expected.lower():
        raise ValueError(f"copy hash mismatch: {dest}")
    return digest


def build(out: Path = OUT, refresh: bool = False) -> Path:
    if out.exists() and not refresh:
        raise FileExistsError(f"Refusing to overwrite conditions directory: {out}; pass --refresh to update the prior v4-bound preparation")
    if sha(PILOT / "freeze.json") != PILOT_FREEZE_SHA256:
        raise ValueError("pilot freeze changed")
    if sha(FORMAL / "formal-freeze.json") != FORMAL_FREEZE_SHA256:
        raise ValueError("formal AB freeze changed")
    formal_freeze = formal.verify_formal(FORMAL)
    if sha(STYLE_SOURCE / "manifest.json") != STYLE_MANIFEST_SHA256:
        raise ValueError("Vue style-reference manifest changed")
    if sha(EXTERNAL_SOURCE / "manifest.json") != EXTERNAL_MANIFEST_SHA256:
        raise ValueError("external-method manifest changed")

    style_manifest = load(STYLE_SOURCE / "manifest.json")
    external_manifest = load(EXTERNAL_SOURCE / "manifest.json")
    style_rel = style_manifest["excerpt"]["file"]
    style_digest = style_manifest["excerpt"]["sha256"]
    if style_rel != "style-excerpt.md":
        raise ValueError("unexpected Vue excerpt path")
    formal_tasks = base.read_tasks(FORMAL / "tasks.jsonl")
    writing = [t for t in formal_tasks if t["kind"] in {"technical-report", "design-spec"}]
    if len(writing) != 4 or {t["split"] for t in writing} != {"development"}:
        raise ValueError("expected exactly the four frozen development writing tasks")

    out.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    output_style = out / "contexts" / "vue-style" / "style-excerpt.md"
    copied[output_style.relative_to(out).as_posix()] = copy_verified(
        STYLE_SOURCE / style_rel, output_style, style_digest)

    external_lookup = {row["path"]: row for row in external_manifest["files"]}
    external_copies: dict[str, str] = {}
    for source_rel in sorted({p for group in EXTERNAL_GROUPS.values() for p in group}):
        item = external_lookup.get(source_rel)
        if not item:
            raise ValueError(f"external source absent from pinned manifest: {source_rel}")
        dest = out / "contexts" / "external-method" / source_rel
        digest = copy_verified(EXTERNAL_SOURCE / source_rel, dest, item["sha256"])
        external_copies[dest.relative_to(out).as_posix()] = digest

    contents = {
        "M": MINIMAL_APPEND,
        "D": ONDEMAND_APPEND,
        "X": EXTERNAL_APPEND,
        "S": STYLE_APPEND,
    }
    for condition_id, content in contents.items():
        path = out / "contexts" / "instructions" / f"{condition_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        copied[path.relative_to(out).as_posix()] = sha(path)

    task_configs = {}
    task_provenance = []
    for task in writing:
        task_id, kind = task["id"], task["kind"]
        prototype = next((t for t in base.read_tasks(PILOT / "tasks.jsonl") if t["kind"] == kind), None)
        if not prototype:
            raise ValueError(f"pilot has no relevant frozen Skill bundle prototype for {task_id}")
        pilot_case = PILOT / "frozen" / prototype["id"] / "current"
        ok, changed = base.verify_frozen_case(pilot_case, PILOT)
        if not ok:
            raise ValueError(f"pilot current bundle changed: {prototype['id']}: {changed}")
        bundle = load(pilot_case / "bundle-manifest.json")
        selected_ref = REPORT_REF if kind == "technical-report" else DESIGN_REF
        if selected_ref not in bundle or EVIDENCE_REF not in bundle:
            raise ValueError(f"required frozen on-demand reference missing: {task_id}")
        selected_sources = []
        for ref in (EVIDENCE_REF, selected_ref):
            dest = out / "contexts" / "pilot-current-reference" / ref
            digest = copy_verified(pilot_case / ref, dest, bundle[ref])
            copied[dest.relative_to(out).as_posix()] = digest
            selected_sources.append({"path": dest.relative_to(out / "contexts").as_posix(), "sha256": digest,
                                     "source_id": f"pilot-frozen:{prototype['id']}:{ref}",
                                     "role": "host_selected_reference"})

        external_sources = []
        for ref in EXTERNAL_GROUPS[kind]:
            item = external_lookup[ref]
            rel = Path("external-method") / ref
            external_sources.append({"path": rel.as_posix(), "sha256": item["sha256"],
                                     "source_id": f"riekelt/technical-writer@{external_manifest['commit']}:{ref}",
                                     "role": "external_method_context"})

        config = {"conditions": [
            {"id": "S", "base_condition": "current", "prompt_append": STYLE_APPEND,
             "extra_sources": [{"path": "vue-style/style-excerpt.md", "sha256": style_digest,
                                "source_id": f"vuejs-translations/docs-zh-cn@{style_manifest['commit']}:{style_manifest['excerpt']['from']}:{style_manifest['excerpt']['line_start']}-{style_manifest['excerpt']['line_end']}",
                                "role": "cross_project_style_reference"}]},
            {"id": "M", "base_condition": "plain", "prompt_append": MINIMAL_APPEND,
             "extra_sources": []},
            {"id": "D", "base_condition": "plain", "prompt_append": ONDEMAND_APPEND,
             "extra_sources": selected_sources},
            {"id": "X", "base_condition": "plain", "prompt_append": EXTERNAL_APPEND,
             "extra_sources": external_sources},
        ]}
        config_path = out / "configs" / f"{task_id}.json"
        dump(config_path, config)
        copied[config_path.relative_to(out).as_posix()] = sha(config_path)
        task_configs[task_id] = {"config": config_path.relative_to(out).as_posix(),
                                 "sha256": sha(config_path), "kind": kind,
                                 "selected_on_demand_reference_ids": [x["source_id"] for x in selected_sources],
                                 "selected_external_source_ids": [x["source_id"] for x in external_sources]}
        task_provenance.append({"task_id": task_id, "kind": kind, "pilot_bundle_task_id": prototype["id"],
                                "pilot_current_bundle_manifest_sha256": sha(pilot_case / "bundle-manifest.json"),
                                "on_demand_reference_hashes": {x["path"]: x["sha256"] for x in selected_sources}})

    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_scope": "context_only_generation",
        "formal_freeze_sha256": sha(FORMAL / "formal-freeze.json"),
        "pilot_freeze_sha256": sha(PILOT / "freeze.json"),
        "source_task_jsonl_sha256": formal_freeze["source_tasks_sha256"],
        "planned_jobs": {"S": 12, "M": 12, "D": 12, "X": 12,
                         "total_new_generations": 48},
        "task_configs": task_configs,
        "task_provenance": task_provenance,
        "vue_style_source_manifest_sha256": STYLE_MANIFEST_SHA256,
        "vue_style_repository": style_manifest["repository"], "vue_style_commit": style_manifest["commit"],
        "vue_style_license": style_manifest["license"], "vue_style_excerpt": style_manifest["excerpt"],
        "external_method_source_manifest_sha256": EXTERNAL_MANIFEST_SHA256,
        "external_method_repository": external_manifest["repository"], "external_method_commit": external_manifest["commit"],
        "external_method_license": external_manifest["license"], "external_method_role": external_manifest["role"],
        "copied_context_hashes": copied | external_copies,
        "prompt_contract": "formal-v1 common JSON contract inherited; condition additions do not replace or extend its schema",
        "tool_claim_limit": "no tools executed; do not claim upstream workflow or validation",
        "source_roles": {"S": "cross_project_style_reference (Vue Chinese prose only)",
                         "M": "host-authored minimal checklist instruction; no extra source records",
                         "D": "host_selected_reference records from frozen pilot current bundle",
                         "X": "external_method_context records from MIT-licensed source snapshot"},
        "adaptation_diff": [
            {"source": "Vue official Chinese docs excerpt", "content": "copied verbatim contiguous source lines; used only as cross-project prose-style context"},
            {"source": "pilot frozen technical/evidence references", "content": "copied verbatim; selected by task type for D; no project facts added"},
            {"source": "riekelt/technical-writer pinned MIT files", "content": "copied verbatim; selected by document type and presented as context-only comparator"},
            {"source": "condition instructions and mappings", "content": "host-authored additions; preserve the common JSON contract and forbid claims of unrun tools/workflows"},
        ],
        "prompt_length_accounting": "exact UTF-8 bytes and decoded characters are in prompt-inventory.json; token usage is unknown until actual CLI turns",
        "hidden_gold_access": False,
    }
    dump(out / "manifest.json", manifest)
    (out / "manifest.sha256").write_text(sha(out / "manifest.json") + "  manifest.json\n", encoding="ascii")
    write_readme(out, manifest)
    return out


def write_readme(out: Path, manifest: dict) -> None:
    lines = [
        "# Writing ablation conditions v1", "",
        "This directory freezes condition contexts for the four formal-v1 development writing tasks. It contains no gold or heldout data and makes no model calls.", "",
        "Each task gets an independent config because D/on-demand selection depends on whether the task requests a technical report or design spec. Each config contains four conditions, three repeats each: S (E3 style), M (E4 minimal), D (E4 on-demand), and X (E7 external), for 12 jobs per task and 48 new generations total. Formal baseline B is in the separate v5 AB run and is not duplicated here.", "",
        "S adds one contiguous excerpt from the official Vue Chinese docs at a pinned commit as role `cross_project_style_reference`. It is only a Chinese explanatory-prose style reference, not domain evidence or a design-spec exemplar. M adds a short host-authored evidence/scope/proposal integrity checklist with no extra source records. D adds only the frozen evidence reference plus the frozen task-type reference from the pilot current bundle as role `host_selected_reference`, while preserving the plain condition prompt prefix. X adds original MIT-licensed technical-writer context files selected by task type as role `external_method_context`. All conditions preserve the shared JSON contract and prohibit claims of tools or workflows that were not run.", "",
        "The E7 material is an adapted context-only comparator, not an evaluation of the upstream plugin end-to-end. All source origins, licenses, commits, line spans, source hashes, copied hashes, and per-task selected references are in `manifest.json`; the exact prompt additions are in `contexts/instructions/` and repeated in each config. After preparing runs, `ablation_contexts.py inventory --run <run-path> ...` verifies actual prompts and records exact prompt bytes/characters, source-role counts, source hashes, and embedded-content lengths. Token counts remain unknown until CLI execution.", "",
        "Prepare one run per writing task. Example for the technical-report task:", "",
        "```powershell",
        "$py = 'D:\\XiangMuLuoDi\\Development\\oh-my-patent-v0.2.0-cnipa-20260930\\oh-my-patent\\.venv\\Scripts\\python.exe'",
        "$runner = 'D:\\XiangMuLuoDi\\Development\\oh-my-patent-v0.2.0-cnipa-20260930\\oh-my-patent\\evals\\public_runner\\formal_runner.py'",
        "$pilot = 'D:\\XiangMuLuoDi\\Development\\word-skills-public-eval\\runs\\public-pilot-context-20261020'",
        "$data = 'D:\\XiangMuLuoDi\\Development\\word-skills-public-eval\\data\\formal-v1'",
        "$contexts = 'D:\\XiangMuLuoDi\\Development\\word-skills-public-eval\\control\\conditions-v1'",
        "$tasks = 'D:\\XiangMuLuoDi\\Development\\word-skills-public-eval\\runs\\formal-v1-dev-ab-v5\\tasks.jsonl'",
        "& $py $runner prepare --pilot-run $pilot --tasks $tasks --data-root $data --out 'D:\\XiangMuLuoDi\\Development\\word-skills-public-eval\\runs\\formal-v1-writing-fastapi-report' --split development --task fastapi-technical-report-dev --repeat 3 --seed 20261020 --conditions-config (Join-Path $contexts 'configs\\fastapi-technical-report-dev.json') --context-root (Join-Path $contexts 'contexts')",
        "```", "",
        "Repeat with each of the other three task IDs and its matching config/output directory. Combined, the four outputs contain 48 jobs. Do not include baseline B in these configs; compare S/M/D/X outputs with the matching B job from v5 by task identity. The instruction to use task materials as context is not a claim that the runner performed a tool workflow.", "",
        "Adaptation diff: external documents remain verbatim copied source files; only this README and the four condition instructions/config mappings were newly authored. The Vue excerpt is copied verbatim. No upstream text was altered."
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def inventory_runs(run_roots: list[Path], out: Path = OUT / "prompt-inventory.json") -> Path:
    """Verify prepared prompts and record exact prompt/source lengths and hashes."""
    inventories, total_jobs, by_condition = [], 0, {}
    pilot_tasks = base.read_tasks(PILOT / "tasks.jsonl")
    prototypes = {kind: next(t for t in pilot_tasks if t["kind"] == kind)
                  for kind in {"factual-qa", "technical-report", "design-spec"}}
    for run_root in run_roots:
        run_root = run_root.resolve()
        freeze = formal.verify_formal(run_root)
        tasks = {t["id"]: t for t in formal.read_jsonl(run_root / "tasks.jsonl")}
        jobs = formal.read_jsonl(run_root / "schedule.jsonl")
        total_jobs += len(jobs)
        for condition in freeze["conditions"]:
            by_condition[condition["id"]] = by_condition.get(condition["id"], 0) + sum(
                job["condition"] == condition["id"] for job in jobs)
        for task_id, task in tasks.items():
            for condition in freeze["conditions"]:
                condition_id = condition["id"]
                case = run_root / "frozen" / task_id / condition_id
                prompt_bytes = (case / "prompt.txt").read_bytes()
                prompt_raw = prompt_bytes.decode("utf-8")
                # Normalize only the outer Windows prompt line endings for marker parsing.
                prompt = prompt_raw.replace("\r\n", "\n")
                records = formal.prompt_source_records(prompt)
                roles = {}
                source_rows = []
                for row in records:
                    role = row.get("role", "untyped")
                    content = row.get("content", "")
                    stats = roles.setdefault(role, {"count": 0, "characters": 0, "utf8_bytes": 0})
                    stats["count"] += 1
                    stats["characters"] += len(content)
                    stats["utf8_bytes"] += len(content.encode("utf-8"))
                    source_rows.append({"role": role, "path": row.get("path"), "source_id": row.get("source_id"),
                                        "sha256": row.get("sha256"), "characters": len(content),
                                        "utf8_bytes": len(content.encode("utf-8"))})
                skill_count = roles.get("skill_reference", {}).get("count", 0)
                expected_skill_count = len(json.loads((PILOT / "frozen" / prototypes[task["kind"]]["id"] /
                                                        "current" / "bundle-manifest.json").read_text(encoding="utf-8")))
                extra_roles = {role: stats["count"] for role, stats in roles.items()
                               if role not in {"material", "skill_reference"}}
                if condition_id == "S":
                    if skill_count != expected_skill_count or extra_roles != {"cross_project_style_reference": 1}:
                        raise ValueError(f"S prompt source-role mismatch: {task_id}: {roles}")
                elif condition_id == "M":
                    if skill_count or extra_roles:
                        raise ValueError(f"M prompt must have neither Skill nor extra-source records: {task_id}: {roles}")
                elif condition_id == "D":
                    if skill_count or extra_roles != {"host_selected_reference": 2}:
                        raise ValueError(f"D prompt source-role mismatch: {task_id}: {roles}")
                elif condition_id == "X":
                    if skill_count or extra_roles != {"external_method_context": 5}:
                        raise ValueError(f"X prompt source-role mismatch: {task_id}: {roles}")
                elif condition_id == "C":
                    if skill_count != expected_skill_count or task["kind"] != "factual-qa":
                        raise ValueError(f"E2 C must embed the factual-qa current bundle: {task_id}: {roles}")
                else:
                    raise ValueError(f"unexpected condition in context inventory: {condition_id}")
                inventory = {"run_path": str(run_root), "run_freeze_sha256": sha(run_root / "formal-freeze.json"),
                             "task_id": task_id, "kind": task["kind"], "split": task["split"],
                             "condition": condition_id, "prompt_sha256": sha(case / "prompt.txt"),
                             "prompt_characters": len(prompt_raw), "prompt_utf8_bytes": len(prompt_bytes),
                             "record_roles": roles, "sources": source_rows,
                             "expected_skill_reference_count": expected_skill_count,
                             "skill_reference_count_verified": skill_count,
                             "estimated_model_tokens": None}
                inventories.append(inventory)
    result = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "formal_runner": str(Path(formal.__file__).resolve()),
              "formal_runner_sha256": sha(Path(formal.__file__).resolve()),
              "prepared_run_count": len(run_roots), "scheduled_generation_jobs": total_jobs,
              "jobs_by_condition": by_condition,
              "usage_note": "Prompt character/byte lengths are exact. Token counts and service billing remain unknown until CLI execution; no token estimate is fabricated.",
              "prompts": inventories}
    out.parent.mkdir(parents=True, exist_ok=True)
    dump(out, result)
    out.with_suffix(out.suffix + ".sha256").write_text(sha(out) + "  " + out.name + "\n", encoding="ascii")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action")
    p = sub.add_parser("build", help="Build or refresh v5-bound contexts and per-task configs")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--refresh", action="store_true", help="Refresh the existing v4-bound directory with v5-verified configs and manifest")
    p = sub.add_parser("inventory", help="Validate and record actual prepared prompts; no model calls")
    p.add_argument("--run", action="append", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT / "prompt-inventory.json")
    args = parser.parse_args()
    if args.action == "inventory":
        result = inventory_runs(args.run, args.out.resolve())
    else:
        result = build(args.out.resolve(), refresh=args.refresh)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
