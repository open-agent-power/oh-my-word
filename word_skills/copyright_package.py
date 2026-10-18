"""Preparation and complete material bundles using the shared Word pipeline.

Adapted workflow: Fokkyp/SoftwareCopyright-Skill, MIT, pinned in upstream.lock.json.
This module is an independent implementation; no OfficeCLI executor is bundled.
"""
from pathlib import Path
import json
import hashlib
from uuid import uuid4

from . import copyright
from .common import digest, inside, now, read_json, sha256, write_json


def prepare(source_root, output, *, name="", version=""):
    root, output = Path(source_root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError("prepare needs a fresh output outside the source tree")
    manifest = copyright.scan_sources(root)
    output.mkdir(parents=True)
    write_json(output / "source-manifest.json", manifest)
    draft = copyright.copyright_template()
    draft["case_id"] = "case-" + uuid4().hex
    draft["software"].update(name=name, version=version)
    draft.update(source_manifest="source-manifest.json", source_root=str(root))
    draft["application"].update(software_name=name, software_version=version)
    draft["manual"].update(path="manual.md", software_name=name, software_version=version)
    write_json(output / "copyright.json", draft)
    write_json(output / "selection.json", {"schema_version": 1, "reviewed_by": "",
               "manifest_sha256": sha256(output / "source-manifest.json"),
               "files": [{"path": f["path"], "sha256": f["sha256"], "line_start": 1,
                          "line_end": f["line_count"], "selected": False, "reason": ""}
                         for f in manifest["files"]]})
    write_json(output / "business-understanding.json", {
        "schema_version": 1, "state": "unreviewed-scaffold", "product_purpose": "",
        "audience": "", "features": [], "operations": [], "evidence": [],
        "note": "Read README, actual entrypoints and operation results; do not infer features or rights from names."})
    # Reuse the upstream evidence/candidate stages rather than a second analyzer.
    from .copyright_workflow import run_stage
    workflow = output / "workflow"
    analysis = workflow / "analysis/project.json"
    drafts = workflow / "草稿"
    stages = [
        ("analyze", ["--project", str(root), "--out", str(analysis)]),
        ("business", ["--project", str(root), "--analysis", str(analysis),
                      "--software-name", name, "--out-dir", str(drafts)]),
        ("candidates", ["--project", str(root), "--analysis", str(analysis), "--out-dir", str(drafts)]),
    ]
    for stage, arguments in stages:
        if run_stage(stage, arguments, quiet=True):
            raise ValueError(f"Fokkyp {stage} stage failed; inspect {workflow}")
    return {"state": "scaffold-not-deliverable", "path": str(output), "candidates": len(manifest["files"])}


def apply_selection(path, *, workflow_selection=None, reviewed_by=""):
    path = Path(path).resolve()
    value = read_json(path)
    selected = read_json(path.parent / "selection.json")
    manifest_path = inside(path.parent, value["source_manifest"])
    manifest = read_json(manifest_path)
    if workflow_selection:
        from ._vendor.fokkyp.scripts.common import confirmation_is_current
        upstream_selection = read_json(workflow_selection)
        if not reviewed_by.strip():
            raise ValueError("Record the actual source reviewer when importing a workflow selection")
        if (upstream_selection.get("user_confirmed")
                and not confirmation_is_current(upstream_selection)):
            raise ValueError("Workflow selection confirmation is stale")
        known = {item["path"]: item for item in manifest["files"]}
        projected = []
        for item in upstream_selection.get("files", []):
            if item.get("selected") is not True:
                continue
            entry = known.get(item.get("path"))
            if not entry or not str(item.get("model_reason", "")).strip():
                raise ValueError("Workflow selection needs an inventoried file and a concrete reason")
            projected.append({"path": entry["path"], "sha256": entry["sha256"],
                              "line_start": 1, "line_end": entry["line_count"],
                              "selected": True, "reason": item["model_reason"]})
        selected = {"schema_version": 1, "reviewed_by": reviewed_by,
                    "manifest_sha256": sha256(manifest_path), "files": projected}
    if selected.get("schema_version") != 1 or not selected.get("reviewed_by"):
        raise ValueError("selection requires a recorded source reviewer")
    if selected.get("manifest_sha256") != sha256(manifest_path):
        raise ValueError("selection is stale for this source inventory")
    known = {item["path"]: item for item in manifest["files"]}
    selections, ranges, count = [], {}, 0
    for item in selected.get("files", []):
        if item.get("selected") is not True:
            continue
        entry = known.get(item.get("path"))
        a, b = item.get("line_start"), item.get("line_end")
        if (not entry or item.get("sha256") != entry["sha256"] or not item.get("reason")
                or type(a) is not int or type(b) is not int or not 1 <= a <= b <= entry["line_count"]):
            raise ValueError("selection needs a known hash, valid original line range and reason")
        if any(a <= end and start <= b for start, end in ranges.setdefault(item["path"], [])):
            raise ValueError("selected source ranges overlap")
        ranges[item["path"]].append((a, b))
        source = inside(Path(manifest["source_root"]), item["path"])
        if sha256(source) != entry["sha256"]:
            raise ValueError("source changed after selection review")
        selections.append({key: item[key] for key in ("path", "sha256", "line_start", "line_end", "reason")})
        count += b - a + 1
    if not selections:
        raise ValueError("No source ranges were selected")
    value["code_material"].update(files=selections, selected_line_count=count,
        selection_basis=f"Source review recorded by {selected['reviewed_by']}; no ownership inference")
    write_json(path, value)
    if workflow_selection:
        write_json(path.parent / "selection.json", selected)
    return {"state": "selection-applied", "files": len(selections), "selected_line_count": count}


def package(path, output, *, draft=False, soffice=None, pdftoppm=None, no_preview=False):
    path, output = Path(path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("package output already exists")
    raw = path.read_bytes()
    input_hash = hashlib.sha256(raw).hexdigest()
    value = json.loads(raw.decode("utf-8-sig"))
    # Resolve the same source inventory used by copyright lint/build.
    checked = dict(value)
    if isinstance(checked.get("source_manifest"), str):
        manifest_file = inside(path.parent, checked["source_manifest"])
        manifest_raw = manifest_file.read_bytes()
        checked["source_manifest"] = json.loads(manifest_raw.decode("utf-8-sig"))
    else:
        manifest_file = None
    root = Path(checked["source_manifest"]["source_root"]).resolve()
    if output.is_relative_to(root):
        raise ValueError("package output must be outside the source tree")
    purpose = "preview" if draft else "registration"
    materials = copyright._material_hashes(value, path.parent)
    if manifest_file:
        materials[str(manifest_file)] = hashlib.sha256(manifest_raw).hexdigest()
    validation = copyright.validate_copyright(checked, base_dir=path.parent, purpose=purpose)
    if not validation["passed"]:
        return {"state": "blocked", "validation": validation}
    # Save provenance even for preparation-only documents. Unknown fields remain unknown.
    output.mkdir(parents=True)
    audit = output / "audit"
    audit.mkdir()
    (audit / "copyright.json").write_bytes(raw)
    write_json(audit / "validation.json", validation)
    write_json(audit / "source-manifest.json", checked["source_manifest"])
    write_json(audit / "materials.json", materials)
    deliveries = {}
    for name in ("source", "manual"):
        result = copyright.build(path, output / name, soffice=soffice, pdftoppm=pdftoppm,
                                 no_preview=no_preview, purpose=purpose, document=name)
        deliveries[name] = {"path": name, "build_id": result.get("build_id"), "state": result["state"]}
        if result["state"] not in {"draft", "awaiting-review"}:
            write_json(output / "manifest.json", {"state": "failed", "deliveries": deliveries})
            return {"state": "failed", "document": name, "result": result}
        bound = result.get("inputs", {}).get("audit/business-copyright.json")
        sources = read_json(output / name / "audit/source-index.json")["sources"]
        changed = any(str(s["original_path"]) in materials and s["sha256"] != materials[str(s["original_path"])] for s in sources)
        attachments = [inside(path.parent, s["path"]) for s in value["screenshots"]]
        if manifest_file:
            attachments.append(manifest_file)
        changed |= any(result["inputs"].get(f"audit/business-attachment-{i}{p.suffix}") != materials[str(p)] for i, p in enumerate(attachments))
        if bound != input_hash or changed:
            write_json(output / "manifest.json", {"state": "failed", "reason": "Child input differs from the package validation snapshot"})
            return {"state": "failed", "reason": "Child input differs from the package validation snapshot"}
    if sha256(path) != input_hash or any(not Path(p).is_file() or sha256(p) != h for p, h in materials.items()):
        write_json(output / "manifest.json", {"state": "failed", "reason": "Business input changed during packaging"})
        return {"state": "failed", "reason": "Business input changed during packaging"}
    field_rows = ["申请表信息填写辅助稿" + ("（草稿，不能用于确认权属或提交）" if draft else "（须人工核对官网表单）")]
    groups = {"软件": value["software"], "申请字段": value["application"], "权属声明": value["rights_holder"]}
    for label, fields in groups.items():
        field_rows.append("\n" + label)
        for key, val in fields.items():
            field_rows.append(f"{key}: {val if val not in ('', None) else '[未确认]'}")
    field_rows.append("\n工具未确认权属、当期规则或受理条件；此 TXT 是填写辅助，不是官方申请表。")
    (output / "application-info.txt").write_text("\n".join(field_rows) + "\n", encoding="utf-8")
    pagination = {}
    for name in deliveries:
        m = read_json(output / name / "manifest.json")
        pagination[name] = {"actual_pages": m.get("renderer", {}).get("pages"),
                            "count_basis": "actual PDF renderer" if m.get("renderer") else "not rendered"}
    write_json(output / "pagination.json", {"documents": pagination,
        "note": "Actual rendered pages only. This does not certify full-program selection, minimum lines/page or official deposit eligibility."})
    pending = [i["message"] for i in validation["issues"] if i.get("deferred")]
    (output / "pending-items.md").write_text("# 待核对事项\n\n" + "\n".join("- " + s for s in pending + [
        "核对全部源程序/文档范围、当期页面要求及证明文件。", "实际阅读两个文档和全部页图，逐项记录审阅。"]), encoding="utf-8")
    outputs = {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob("*") if p.is_file() and p.parent == output}
    manifest = {"schema_version": 1, "created_at": now(), "purpose": purpose,
        "state": "draft" if draft or no_preview else "awaiting-review", "ready_for_submission": False,
        "input_sha256": hashlib.sha256(raw).hexdigest(), "deliveries": deliveries,
        "inputs": {p.relative_to(output).as_posix(): sha256(p) for p in audit.iterdir()}, "outputs": outputs,
        "note": "Registration preparation only; each child delivery has an independent audit and page review."}
    manifest["package_id"] = digest(manifest)
    write_json(output / "manifest.json", manifest)
    return manifest


def finalize_package(output):
    """Record a completed bundle review; preparation previews can never be promoted."""
    output = Path(output).resolve()
    manifest = read_json(output / "manifest.json")
    if manifest.get("purpose") != "registration" or manifest.get("state") != "awaiting-review":
        raise ValueError("Only a registration-preparation bundle awaiting review can be finalized")
    for rel, expected in (manifest["inputs"] | manifest["outputs"]).items():
        if sha256(inside(output, rel)) != expected:
            raise ValueError("Bundle inputs or auxiliary files changed; rebuild")
    from .delivery import code_identity, skill_identity
    current_skill_identity = skill_identity()
    for name, delivery in manifest["deliveries"].items():
        folder = inside(output, delivery["path"])
        child = read_json(folder / "manifest.json")
        if child.get("inputs", {}).get("audit/business-copyright.json") != manifest["input_sha256"]:
            raise ValueError("Child business input is not the package input")
        if child.get("skill_identity") != current_skill_identity:
            raise ValueError("Skill instructions changed since child review; rebuild before final package review")
        if (child["state"] != "reviewed" or child["build_id"] != delivery["build_id"]
                or child["code_identity"] != code_identity()):
            raise ValueError("Every child must have a matching, current reviewed delivery")
        for rel, expected in (child["inputs"] | child["outputs"]).items():
            if sha256(inside(folder, rel)) != expected:
                raise ValueError("A child artifact changed after review")
        review = child["review"]
        if sha256(inside(folder, review["path"])) != review["sha256"]:
            raise ValueError("Child review changed")
        delivery.update(state="reviewed", manifest_sha256=sha256(folder / "manifest.json"))
    manifest["state"] = "reviewed"
    write_json(output / "manifest.json", manifest)
    return manifest
