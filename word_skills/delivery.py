from __future__ import annotations

import importlib.metadata
import shutil
from pathlib import Path

from . import __version__
from .common import digest, finding, inside, now, read_json, sha256, write_json
from .evidence import contract, validate
from .inspect import inspect_docx, inspect_pdf, preview
from .render import fingerprint, render
from .review import review_rows, validate_review


def code_identity():
    root = Path(__file__).parent
    return digest({p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.suffix in {".py", ".yaml"}})


def versions():
    result = {"word-skills": __version__}
    for name in ("python-docx", "docxtpl", "markitdown", "pdfplumber", "pypdf", "PyYAML"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def skill_identity():
    root = Path(__file__).resolve().parents[1]
    paths = [p for folder in ("skills", "shared", "registry") for p in (root / folder).rglob("*") if p.is_file()]
    return digest({p.relative_to(root).as_posix(): sha256(p) for p in sorted(paths)}) if paths else None


def build(draft_path, case, output, template=None, template_mode="style", soffice=None, pdftoppm=None, no_preview=False, *, business_gate=None):
    output, case, draft_path = Path(output).resolve(), Path(case).resolve(), Path(draft_path).resolve()
    draft = read_json(draft_path)
    required_gate = contract(draft["mode"]).get("business_gate")
    if required_gate != business_gate:
        raise ValueError(f"{draft['mode']} requires its dedicated business build command")
    if output.exists():
        raise ValueError("Output directory already exists; use a fresh path to preserve prior deliveries")
    output.mkdir(parents=True)
    audit = output / "audit"
    audit.mkdir()
    validation = validate(draft, case)
    write_json(audit / "validation.json", validation)
    manifest = {"schema_version": 1, "created_at": now(), "state": "blocked", "mode": draft["mode"],
                "code_identity": code_identity(), "skill_identity": skill_identity(), "versions": versions(), "template_mode": template_mode if template else None,
                "business_gate": required_gate, "inputs": {}, "outputs": {}, "review": "not performed"}
    for key in ("case_id", "document_id"):
        if key in draft:
            manifest[key] = draft[key]
    # Keep an auditable, portable snapshot; never mutate the input case or draft.
    shutil.copyfile(draft_path, audit / "draft.json")
    for name in ("source-index.json", "evidence.json"):
        if (case / name).is_file():
            shutil.copyfile(case / name, audit / name)
    for source in (read_json(case / "source-index.json")["sources"] if (case / "source-index.json").is_file() else []):
        for key in ("snapshot", "extracted", "segments"):
            dest = inside(audit, source[key])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(inside(case, source[key]), dest)
    if validation["passed"]:
        for section in draft["sections"]:
            for block in section["blocks"]:
                if block["type"] == "image":
                    source = inside(case, block["path"])
                    dest = inside(audit, block["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, dest)
                    if sha256(dest) != block["sha256"]:
                        raise ValueError("Image changed after validation; rebuild")
    if template:
        shutil.copyfile(template, audit / "reference.docx")
    for p in audit.rglob("*"):
        if p.is_file() and p.name != "validation.json":
            manifest["inputs"][p.relative_to(output).as_posix()] = sha256(p)
    if not validation["passed"]:
        write_json(output / "manifest.json", manifest)
        return manifest
    try:
        profile = render(draft, output / "output.docx", template, template_mode, asset_root=audit)
        actual_profile = fingerprint(output / "output.docx")
        write_json(audit / "template_profile.json", {"reference": profile, "actual": actual_profile})
        validation["issues"] += inspect_docx(output / "output.docx", draft)
        if profile:
            if profile["sections"] != actual_profile["sections"] or profile["styles"] != actual_profile["styles"]:
                validation["issues"].append(finding("TEMPLATE_DRIFT", "Basic page or paragraph style properties differ from reference"))
            for warning in profile["warnings"]:
                validation["issues"].append(finding("TEMPLATE_REVIEW", warning, "warning"))
        if no_preview:
            validation["issues"].append(finding("PREVIEW_MISSING", "Preview explicitly skipped; delivery remains unreviewed", "warning"))
            manifest["state"] = "draft"
        else:
            manifest["renderer"] = preview(output / "output.docx", output, soffice, pdftoppm)
            pdf_check = inspect_pdf(output / "preview.pdf", draft)
            write_json(audit / "layout.json", pdf_check)
            validation["issues"] += pdf_check["issues"]
            manifest["state"] = "business-pending" if required_gate else "awaiting-review"
    except Exception as exc:
        validation["issues"].append(finding("BUILD_FAILED", f"{type(exc).__name__}: {exc}"))
        manifest["state"] = "failed"
    validation["passed"] = not any(x["severity"] == "error" for x in validation["issues"])
    if not validation["passed"]:
        manifest["state"] = "failed"
    write_json(audit / "validation.json", validation)
    for p in sorted(output.rglob("*")):
        rel = p.relative_to(output).as_posix()
        if p.is_file() and rel not in manifest["inputs"] and rel != "manifest.json":
            manifest["outputs"][rel] = sha256(p)
    manifest["build_id"] = digest({"inputs": manifest["inputs"], "outputs": manifest["outputs"], "code": manifest["code_identity"], "skills": manifest["skill_identity"]})
    write_json(output / "manifest.json", manifest)
    return manifest


def review_init(output):
    output = Path(output)
    manifest = read_json(output / "manifest.json")
    if manifest["state"] != "awaiting-review":
        raise ValueError("Only a successful preview build can enter review")
    target = output / "audit/review.json"
    if target.exists():
        raise ValueError("Review exists; preserve or edit it, do not overwrite")
    report = {"schema_version": 1, "build_id": manifest["build_id"], "reviewer": "", "reviewed_at": "",
              "content": {"status": "pending", "notes": ""},
              "pages": [{"image": name, "status": "pending", "notes": ""} for name in manifest["renderer"]["page_images"]],
              "accepted_warnings": [], "findings": []}
    report.update(review_rows(read_json(output / "audit/draft.json")))
    write_json(target, report)
    return report


def finalize(output):
    output = Path(output)
    manifest = read_json(output / "manifest.json")
    if manifest["state"] != "awaiting-review":
        raise ValueError("Delivery must be awaiting-review")
    required_gate = contract(manifest["mode"]).get("business_gate")
    if required_gate:
        business = manifest.get("business", {})
        if business.get("kind") != required_gate or business.get("input") not in manifest["inputs"] or business.get("checks") not in manifest["inputs"]:
            raise ValueError("Business validation audit is missing or unbound")
        if not read_json(output / business["checks"]).get("passed"):
            raise ValueError("Business validation did not pass")
    if manifest["code_identity"] != code_identity():
        raise ValueError("Generator changed since build; rebuild before final review")
    if manifest.get("skill_identity") != skill_identity():
        raise ValueError("Skill instructions changed since build; rebuild before final review")
    for rel, checksum in (manifest["inputs"] | manifest["outputs"]).items():
        path = inside(output, rel)
        if not path.is_file() or sha256(path) != checksum:
            raise ValueError(f"Stale review/artifact: {rel}")
    if not validate(read_json(output / "audit/draft.json"), output / "audit")["passed"]:
        raise ValueError("Source/content validation no longer passes")
    report = read_json(output / "audit/review.json")
    if report.get("build_id") != manifest["build_id"] or not report.get("reviewer") or not report.get("reviewed_at"):
        raise ValueError("Review identity, reviewer and timestamp required")
    if report.get("content", {}).get("status") != "pass" or not report["content"].get("notes"):
        raise ValueError("Content review with concrete notes required")
    validate_review(read_json(output / "audit/draft.json"), report)
    expected = manifest.get("renderer", {}).get("page_images", [])
    reviewed = report.get("pages", [])
    if not expected or len(reviewed) != len(expected) or {p.get("image") for p in reviewed} != set(expected):
        raise ValueError("Every rendered page must be reviewed exactly once")
    if any(p.get("status") != "pass" or not p.get("notes") for p in reviewed):
        raise ValueError("Every page needs a passing visual review and notes")
    if any(f.get("status") != "resolved" for f in report.get("findings", [])):
        raise ValueError("Unresolved review findings")
    warnings = read_json(output / "audit/validation.json")["issues"]
    needed = {digest(w) for w in warnings if w["severity"] == "warning"}
    accepted = {w.get("id") for w in report.get("accepted_warnings", []) if w.get("reason")}
    if needed - accepted:
        raise ValueError("Each warning must be acknowledged by digest and reason")
    manifest["state"] = "reviewed"
    manifest["review"] = {"path": "audit/review.json", "sha256": sha256(output / "audit/review.json"),
                          "meaning": "Recorded content and visual review, not certification of truth or external submission"}
    write_json(output / "manifest.json", manifest)
    return manifest
