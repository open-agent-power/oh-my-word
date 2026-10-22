"""Evidence-bound software copyright material contracts.

This module deliberately stops at deterministic preparation checks.  It does
not decide ownership, legal eligibility, page counts, or submit an
application.  Source files are kept as real files with hashes and line
locations so a reviewer can reproduce every selected excerpt.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
from typing import Any

from .common import finding, inside, read_json, sha256, write_json


SCHEMA_VERSION = 1
_LANGUAGES = {
    ".py": "Python", ".pyw": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".kts": "Kotlin", ".go": "Go", ".rs": "Rust", ".c": "C", ".h": "C/C++",
    ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".cs": "C#",
    ".swift": "Swift", ".php": "PHP", ".rb": "Ruby", ".scala": "Scala",
    ".sql": "SQL", ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell",
    ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML", ".css": "CSS",
}
_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "vendor",
    "dist", "build", "out", "target", "coverage", ".pytest_cache", "__pycache__", "_vendor",
    ".mypy_cache", ".ruff_cache", ".tox", ".agent", ".idea", ".vscode",
    "secrets", "private", "third_party", "site-packages", ".next", ".nuxt", "outputs", ".tools", ".codex",
}
_SECRET_NAMES = {
    ".env", ".env.local", ".env.production", ".npmrc", ".pypirc", "credentials",
    "credentials.json", "secrets.json", "id_rsa", "id_dsa", "known_hosts",
}
_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".cer", ".crt", ".der"}
_MAX_FILE_BYTES = 10 * 1024 * 1024
_CREDENTIAL = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN|OPENAI_API_KEY|DATABASE_PASSWORD|"
    r"DB_PASSWORD|JWT_SECRET)['\"]?\s*[:=]\s*['\"]?[^\s'\"#]{8,}",
    re.IGNORECASE | re.MULTILINE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normal_path(path: str) -> str:
    return Path(str(path).replace("\\", "/")).as_posix()


def _skip_reason(path: Path, root: Path) -> str | None:
    relative = path.relative_to(root)
    if any(part.lower() in _SKIP_DIRS for part in relative.parts[:-1]):
        return "dependency-or-build-directory"
    name = path.name.lower()
    if name in _SECRET_NAMES or name.startswith(".env") or path.suffix.lower() in _SECRET_SUFFIXES:
        return "credential-or-private-key"
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        return "symbolic-link"
    if name.endswith((".min.js", ".min.css", ".generated.cs", ".g.cs", "_pb2.py")):
        return "generated-or-minified"
    if path.stat().st_size > _MAX_FILE_BYTES:
        return "file-too-large"
    if path.suffix.lower() not in _LANGUAGES:
        from ._vendor.fokkyp.scripts.common import is_source_candidate
        if not is_source_candidate(path):
            return "unsupported-source-extension"
    return None


def _decode_source(raw: bytes) -> tuple[str, str]:
    if b"\x00" in raw:
        raise ValueError("binary content")
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("source is not a supported text file")


def _read_source(path: Path) -> tuple[str, str]:
    return _decode_source(path.read_bytes())


def scan_sources(source_root: str | Path) -> dict[str, Any]:
    """Create a reproducible source inventory without copying source code."""
    root = Path(source_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"source root is not a directory: {source_root}")
    files: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for current, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(d for d in dirs if d.lower() not in _SKIP_DIRS and not (current_path / d).is_symlink())
        for filename in sorted(filenames):
            path = current_path / filename
            rel = _normal_path(path.relative_to(root))
            try:
                reason = _skip_reason(path, root)
            except OSError:
                excluded.append({"path": rel, "reason": "unreadable"})
                continue
            if reason:
                if reason != "unsupported-source-extension":
                    excluded.append({"path": rel, "reason": reason})
                continue
            try:
                text, encoding = _read_source(path)
            except (OSError, ValueError):
                excluded.append({"path": rel, "reason": "unreadable-text"})
                continue
            if _CREDENTIAL.search(text):
                excluded.append({"path": rel, "reason": "credential-pattern"})
                continue
            files.append({
                "path": rel,
                "language": _LANGUAGES.get(path.suffix.lower(), "待核对"),
                "encoding": encoding,
                "bytes": path.stat().st_size,
                "line_count": len(text.splitlines()),
                "sha256": sha256(path),
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "source_root": str(root),
        "generated_at": _utc_now(),
        "files": files,
        "excluded": excluded,
        "selection_policy": {
            "include_extensions": sorted(_LANGUAGES),
            "unknown_extensions": "Fokkyp 2.6 content-based candidates; language and program scope require review",
            "excluded_directories": sorted(_SKIP_DIRS),
            "max_file_bytes": _MAX_FILE_BYTES,
            "note": "Inventory metadata only; source content remains at source_root.",
        },
    }


def _issue(code: str, message: str, severity: str = "error", location: str | None = None) -> dict[str, Any]:
    return finding(code, message, severity, location)


def _manifest(value: Any, source_root: Path | None) -> tuple[dict[str, Any] | None, Path | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if isinstance(value, dict):
        manifest_value = value.get("source_manifest")
    else:
        manifest_value = None
    manifest: dict[str, Any] | None = None
    manifest_path: Path | None = None
    if isinstance(manifest_value, dict):
        manifest = manifest_value
    elif isinstance(manifest_value, str) and manifest_value.strip():
        manifest_path = Path(manifest_value).expanduser().resolve()
        try:
            manifest = read_json(manifest_path)
        except (OSError, ValueError) as exc:
            issues.append(_issue("SOURCE_MANIFEST", f"cannot read source manifest: {exc}"))
    if not isinstance(manifest, dict):
        issues.append(_issue("SOURCE_MANIFEST", "source_manifest is required; run copyright scan first"))
        return None, source_root, issues
    if manifest.get("schema_version") != SCHEMA_VERSION or not isinstance(manifest.get("files"), list):
        issues.append(_issue("SOURCE_MANIFEST", "source manifest requires schema_version=1 and files"))
        return None, source_root, issues
    manifest_root = manifest.get("source_root")
    if source_root is None and isinstance(manifest_root, str) and manifest_root:
        source_root = Path(manifest_root).expanduser().resolve()
    if source_root is None or not source_root.is_dir():
        issues.append(_issue("SOURCE_ROOT", "source_root must point to the original source directory"))
    elif isinstance(manifest_root, str) and manifest_root:
        try:
            if Path(manifest_root).expanduser().resolve() != source_root:
                issues.append(_issue("SOURCE_ROOT", "manifest source_root does not match the supplied source root"))
        except OSError:
            issues.append(_issue("SOURCE_ROOT", "manifest source_root is not a valid directory path"))
    return manifest, source_root, issues


def _strings_equal(value: Any, expected: str) -> bool:
    return isinstance(value, str) and value.strip() == expected.strip()


def _knowledge_materials(value, base_dir):
    if "knowledge_context" not in value:
        return {}
    from .knowledge_context import validate_binding
    folder, manifest = validate_binding(value["knowledge_context"], base_dir)
    return {str(folder / rel): checksum for rel, checksum in manifest["inputs"].items()} | {
        str(folder / "context-manifest.json"): value["knowledge_context"]["sha256"]}


def _material_hashes(value, base_dir):
    """Capture files before validation, not after a successful check."""
    paths = [value.get("manual", {}).get("path")] if isinstance(value.get("manual"), dict) else []
    paths += [s.get("path") for s in value.get("screenshots", []) if isinstance(s, dict)] if isinstance(value.get("screenshots"), list) else []
    result = {}
    for rel in paths:
        try:
            if isinstance(rel, str) and rel and not Path(rel).is_absolute():
                file = inside(base_dir, rel)
                if file.is_file():
                    result[str(file)] = sha256(file)
        except (ValueError, OSError):
            pass  # The normal validator reports malformed or missing files.
    result.update(_knowledge_materials(value, base_dir))
    return result


def validate_copyright(value: Any, *, source_root: str | Path | None = None,
                       base_dir: str | Path | None = None, purpose="registration") -> dict[str, Any]:
    """Validate a copyright material draft against its original source inventory."""
    if purpose not in {"registration", "preview"}:
        raise ValueError("purpose must be registration or preview")
    issues: list[dict[str, Any]] = []
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        return {"schema_version": SCHEMA_VERSION, "passed": False, "issues": [_issue("SCHEMA", "copyright draft requires schema_version=1")]}
    if "knowledge_context" in value:
        try:
            _knowledge_materials(value, base_dir)
        except (ValueError, OSError, TypeError, KeyError) as exc:
            issues.append(_issue("KNOWLEDGE_CONTEXT", str(exc)))
    software = value.get("software")
    if not isinstance(software, dict):
        issues.append(_issue("SOFTWARE", "software metadata is required"))
        software = {}
    for field in ("name", "version", "completion_date"):
        if not isinstance(software.get(field), str) or not software[field].strip():
            issues.append(_issue("SOFTWARE_FIELD", f"software.{field} is required"))
    rights = value.get("rights_holder")
    if not isinstance(rights, dict) or not isinstance(rights.get("name"), str) or not rights["name"].strip():
        issues.append(_issue("RIGHTS_HOLDER", "rights_holder.name must be supplied by the user"))
    elif rights.get("ownership_confirmed") is not True:
        issues.append(_issue("RIGHTS_CONFIRMATION", "ownership must be explicitly confirmed; it cannot be inferred from source code"))
    if not isinstance(rights, dict) or not isinstance(rights.get("confirmation_note"), str) or not rights["confirmation_note"].strip():
        issues.append(_issue("RIGHTS_CONFIRMATION", "record the basis of the ownership declaration"))
    root = Path(source_root).expanduser().resolve() if source_root else None
    manifest, root, manifest_issues = _manifest(value, root)
    issues.extend(manifest_issues)
    manifest_files: dict[str, dict[str, Any]] = {}
    if manifest:
        for item in manifest.get("files", []):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                issues.append(_issue("SOURCE_ENTRY", "manifest files need a relative path"))
                continue
            rel = _normal_path(item["path"])
            if Path(item["path"]).is_absolute() or rel != item["path"] or rel.startswith("../") or "/../" in rel:
                issues.append(_issue("SOURCE_PATH", f"manifest path is not a normalized relative path: {item['path']}"))
                continue
            if rel in manifest_files:
                issues.append(_issue("SOURCE_ENTRY", f"duplicate manifest path: {rel}"))
            manifest_files[rel] = item
            if type(item.get("line_count")) is not int or item["line_count"] < 0:
                issues.append(_issue("SOURCE_ENTRY", f"{rel} needs a non-negative integer line_count"))
            if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
                issues.append(_issue("SOURCE_ENTRY", f"{rel} needs a SHA-256 hash"))
            if root:
                try:
                    path = root / rel
                    inside(root, rel)
                    reason = _skip_reason(path, root) if path.is_file() else "missing"
                    if not path.is_file() or reason is not None:
                        issues.append(_issue("SOURCE_ENTRY", f"{rel} is no longer an eligible source file"))
                    else:
                        text, _ = _read_source(path)
                        if b"\x00" in path.read_bytes() or _CREDENTIAL.search(text):
                            issues.append(_issue("SOURCE_SECRET", f"{rel} now contains binary or credential material"))
                        if sha256(path) != item.get("sha256"):
                            issues.append(_issue("SOURCE_CHANGED", f"{rel} no longer matches the manifest hash"))
                        if len(text.splitlines()) != item.get("line_count"):
                            issues.append(_issue("SOURCE_LINE_COUNT", f"{rel} line_count no longer matches the manifest"))
                except (ValueError, OSError, UnicodeError) as exc:
                    issues.append(_issue("SOURCE_ENTRY", f"{rel} cannot be revalidated: {exc}"))
    selected = value.get("code_material")
    if not isinstance(selected, dict):
        issues.append(_issue("CODE_MATERIAL", "code_material is required"))
        selected = {}
    if any(key in selected for key in ("page_count", "page_target", "estimated_pages", "characters_per_page")):
        issues.append(_issue("PAGE_FORGERY", "page counts or character-per-page estimates are not accepted as source evidence"))
    selections = selected.get("files")
    if not isinstance(selections, list) or not selections:
        issues.append(_issue("CODE_SELECTION", "code_material.files must list real source files and line ranges"))
        selections = []
    selected_lines = 0
    ranges: dict[str, list[tuple[int, int]]] = {}
    for index, item in enumerate(selections):
        location = f"code_material.files[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            issues.append(_issue("CODE_SELECTION", f"{location} needs a relative path"))
            continue
        rel = _normal_path(item["path"])
        if rel not in manifest_files:
            issues.append(_issue("CODE_SELECTION", f"{rel} is absent from the scanned source manifest", location=location))
            continue
        try:
            if type(item.get("line_start")) is not int or type(item.get("line_end")) is not int:
                raise ValueError("line positions must be integers")
            start, end = item["line_start"], item["line_end"]
        except (TypeError, ValueError):
            issues.append(_issue("CODE_RANGE", f"{rel} needs integer line_start/line_end", location=location))
            continue
        if start < 1 or end < start:
            issues.append(_issue("CODE_RANGE", f"{rel} has an invalid line range", location=location))
            continue
        entry = manifest_files[rel]
        entry_line_count = entry.get("line_count")
        if type(entry_line_count) is not int or end > entry_line_count:
            issues.append(_issue("CODE_RANGE", f"{rel} line range exceeds the scanned file", location=location))
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            issues.append(_issue("CODE_REASON", f"{rel} needs a selection reason", location=location))
        if item.get("sha256") != entry.get("sha256"):
            issues.append(_issue("CODE_HASH", f"{rel} selection hash does not match the scanned file", location=location))
        if root:
            try:
                path = inside(root, rel)
                if not path.is_file() or sha256(path) != entry.get("sha256"):
                    issues.append(_issue("SOURCE_CHANGED", f"{rel} no longer matches the scanned source", location=location))
            except (ValueError, OSError) as exc:
                issues.append(_issue("CODE_PATH", f"{rel} is not a safe source path: {exc}", location=location))
        if type(entry_line_count) is int and end <= entry_line_count:
            for earlier_start, earlier_end in ranges.setdefault(rel, []):
                if start <= earlier_end and earlier_start <= end:
                    issues.append(_issue("CODE_OVERLAP", f"{rel} selection overlaps an earlier range", location=location))
                    break
            ranges[rel].append((start, end))
            selected_lines += end - start + 1
    if selected.get("selected_line_count") is not None and type(selected.get("selected_line_count")) is not int:
        issues.append(_issue("CODE_LINE_TOTAL", "selected_line_count must be an integer"))
    elif selected_lines and selected.get("selected_line_count") not in (None, selected_lines):
        issues.append(_issue("CODE_LINE_TOTAL", f"selected_line_count does not match selected ranges ({selected_lines})"))
    application = value.get("application", {})
    manual = value.get("manual", {})
    if not isinstance(application, dict):
        issues.append(_issue("APPLICATION", "application must be an object"))
        application = {}
    if not isinstance(manual, dict):
        issues.append(_issue("MANUAL", "manual must be an object"))
        manual = {}
    for section, label in ((application, "application"), (manual, "manual")):
        for field in ("software_name", "software_version"):
            if not isinstance(section.get(field), str) or not section[field].strip():
                issues.append(_issue("IDENTITY_MISSING", f"{label}.{field} is required"))
            elif not _strings_equal(section[field], str(software.get("name" if field == "software_name" else "version", ""))):
                issues.append(_issue("IDENTITY_MISMATCH", f"{label}.{field} does not match software metadata"))
    if not isinstance(application.get("applicant"), str) or application.get("applicant") != (rights.get("name") if isinstance(rights, dict) else None):
        issues.append(_issue("APPLICANT_MISMATCH", "application.applicant must equal the declared rights holder"))
    if not isinstance(application.get("category"), str) or not application["category"].strip():
        issues.append(_issue("APPLICATION", "application.category is required"))
    manual_path = manual.get("path")
    if not isinstance(manual_path, str) or not manual_path.strip() or base_dir is None:
        issues.append(_issue("MANUAL_SOURCE", "manual.path must point to a real case-relative file"))
    else:
        try:
            if Path(manual_path).is_absolute():
                raise ValueError("absolute manual path")
            path = inside(base_dir, manual_path)
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".docx", ".pdf"}:
                raise ValueError("missing or unsupported manual")
            from .ingest import extract
            manual_text = extract(path)[0]
            if software.get("name") not in manual_text or software.get("version") not in manual_text:
                issues.append(_issue("MANUAL_IDENTITY", "manual content must mention the software name and version"))
        except (OSError, ValueError, TypeError) as exc:
            issues.append(_issue("MANUAL_SOURCE", f"manual cannot be inspected: {exc}"))
    if not isinstance(manual.get("verified_against"), str) or not manual["verified_against"].strip():
        issues.append(_issue("MANUAL_REVIEW", "record what running software/version was checked"))
    ui_type = value.get("ui_type")
    if ui_type not in ("visual", "headless"):
        issues.append(_issue("UI_TYPE", "ui_type must be visual or headless"))
    screenshots = value.get("screenshots")
    if not isinstance(screenshots, list) or (ui_type == "visual" and not screenshots):
        issues.append(_issue("SCREENSHOTS", "visual software needs real screenshots"))
    elif isinstance(screenshots, list):
        for item in screenshots:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip() or not isinstance(item.get("feature"), str) or not item["feature"].strip():
                issues.append(_issue("SCREENSHOTS", "screenshot needs path and feature"))
                continue
            try:
                if base_dir is None or Path(item["path"]).is_absolute() or not inside(base_dir, item["path"]).is_file():
                    raise ValueError("screenshot missing or outside case")
            except (ValueError, OSError):
                issues.append(_issue("SCREENSHOTS", "screenshot must exist inside the case directory"))
    ai_use = value.get("ai_use", {})
    if not isinstance(ai_use, dict):
        issues.append(_issue("AI_DISCLOSURE", "ai_use must be an object"))
        ai_use = {}
    if ai_use.get("used") and not ai_use.get("human_verified"):
        issues.append(_issue("AI_DISCLOSURE", "AI-assisted material needs human verification before handoff"))
    deferred = []
    if purpose == "preview":
        for issue in issues:
            if (issue["code"] in {"RIGHTS_HOLDER", "RIGHTS_CONFIRMATION", "AI_DISCLOSURE"}
                    or (issue["code"] == "SOFTWARE_FIELD" and issue["message"] == "software.completion_date is required")):
                issue["severity"] = "warning"
                issue["deferred"] = True
                deferred.append(issue["code"])
    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": purpose,
        "handoff_ready": purpose == "registration" and not any(item["severity"] == "error" for item in issues),
        "deferred_fields": deferred,
        "passed": not any(item["severity"] == "error" for item in issues),
        "checks": "source inventory, file hashes, line ranges, source exclusions, identity consistency, ownership confirmation",
        "selected_line_count": selected_lines,
        "issues": issues,
    }


def copyright_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "software": {"name": "", "version": "", "completion_date": ""},
        "rights_holder": {"name": "", "entity_type": "", "ownership_confirmed": False, "confirmation_note": ""},
        "source_root": "",
        "source_manifest": "",
        "code_material": {"files": [], "selected_line_count": 0, "selection_basis": ""},
        "application": {"software_name": "", "software_version": "", "applicant": "", "category": ""},
        "manual": {"path": "", "software_name": "", "software_version": "", "verified_against": ""},
        "ui_type": "headless",
        "screenshots": [],
        "ai_use": {"used": False, "human_verified": False, "disclosure": ""},
        "status": "draft",
    }


def scan(source_root: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    result = scan_sources(source_root)
    if out is not None:
        out_path = Path(out)
        if out_path.exists():
            raise ValueError("source manifest already exists")
        write_json(out_path, result)
        result = {"path": str(out_path), "files": len(result["files"]), "excluded": len(result["excluded"]), "state": "scanned"}
    return result


def lint(path: str | Path, *, source_root: str | Path | None = None) -> dict[str, Any]:
    case_path = Path(path).expanduser().resolve()
    value = read_json(case_path)
    if isinstance(value, dict) and isinstance(value.get("source_manifest"), str) and value["source_manifest"]:
        manifest_path = Path(value["source_manifest"])
        if not manifest_path.is_absolute():
            value["source_manifest"] = str((case_path.parent / manifest_path).resolve())
    return validate_copyright(value, source_root=source_root, base_dir=case_path.parent)


def write_template(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if target.exists():
        raise ValueError("copyright template already exists")
    write_json(target, copyright_template())
    return {"path": str(target), "state": "scaffold-not-deliverable"}


def extract_materials(path: str | Path, out: str | Path, *, source_root: str | Path | None = None) -> dict[str, Any]:
    """Write exact selected lines plus provenance; never estimate pagination."""
    case_path = Path(path).expanduser().resolve()
    value = read_json(case_path)
    if isinstance(value.get("source_manifest"), str) and value["source_manifest"]:
        manifest_path = Path(value["source_manifest"])
        if not manifest_path.is_absolute():
            value["source_manifest"] = str((case_path.parent / manifest_path).resolve())
    validation = validate_copyright(value, source_root=source_root, base_dir=case_path.parent)
    if not validation["passed"]:
        raise ValueError("copyright material lint failed; correct its findings before extraction")
    manifest, root, _ = _manifest(value, Path(source_root).expanduser().resolve() if source_root else None)
    assert manifest is not None and root is not None
    target = Path(out).expanduser().resolve()
    if target.exists():
        raise ValueError("material output already exists")
    if target.is_relative_to(root):
        raise ValueError("material output must be outside the source tree")
    # Prepare excerpts before creating output so source changes cannot leave a partial artifact.
    prepared = []
    for item in value["code_material"]["files"]:
        source = inside(root, _normal_path(item["path"]))
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("source changed after validation; scan again")
        text, _ = _decode_source(raw)
        prepared.append("".join(text.splitlines(keepends=True)[item["line_start"] - 1:item["line_end"]]))
    target.mkdir(parents=True)
    provenance: list[dict[str, Any]] = []
    for index, item in enumerate(value["code_material"]["files"], start=1):
        rel = _normal_path(item["path"])
        source = inside(root, rel)
        excerpt = prepared[index - 1]
        fence = "`" * max(3, max((len(match.group()) for match in re.finditer(r"`+", excerpt)), default=0) + 1)
        filename = f"material-{index:03d}.md"
        record = {
            "material": filename,
            "source_path": rel,
            "source_sha256": item["sha256"],
            "line_start": item["line_start"],
            "line_end": item["line_end"],
            "selection_reason": item["reason"],
        }
        body = "# 源码原文摘录\n\n" + json.dumps(record, ensure_ascii=False, indent=2) + "\n\n" + fence + "\n" + excerpt + ("" if excerpt.endswith("\n") else "\n") + fence + "\n"
        (target / filename).write_text(body, encoding="utf-8")
        provenance.append(record)
    write_json(target / "provenance.json", {"schema_version": 1, "software": value["software"], "materials": provenance,
                                            "note": "Exact source excerpts only; pagination and submission eligibility have not been checked."})
    return {"path": str(target), "materials": len(provenance), "selected_line_count": validation["selected_line_count"],
            "state": "source-excerpts-not-paginated"}


def build(path, out, *, source_root=None, soffice=None, pdftoppm=None, no_preview=False,
          purpose="registration", document="source"):
    """Produce auditable source Word/PDF through the shared renderer and review gate."""
    from tempfile import TemporaryDirectory
    from .ingest import ingest
    from .delivery import build as shared_build
    from .business import bind_business_audit
    if document not in {"source", "manual"}:
        raise ValueError("document must be source or manual")
    case_path = Path(path).resolve()
    source_bytes = case_path.read_bytes()
    value = json.loads(source_bytes.decode("utf-8-sig"))
    manifest_path = None
    manifest_bytes = None
    if isinstance(value.get("source_manifest"), str) and value["source_manifest"]:
        manifest_path = Path(value["source_manifest"])
        if not manifest_path.is_absolute():
            manifest_path = (case_path.parent / manifest_path).resolve()
        manifest_bytes = manifest_path.read_bytes()
        value["source_manifest"] = json.loads(manifest_bytes.decode("utf-8-sig"))
    manifest, root, manifest_issues = _manifest(value, Path(source_root).resolve() if source_root else None)
    if manifest is not None:
        value["source_manifest"] = manifest
    material_hashes = _material_hashes(value, case_path.parent)
    if manifest_path is not None:
        material_hashes[str(manifest_path)] = hashlib.sha256(manifest_bytes).hexdigest()
    result = validate_copyright(value, source_root=source_root, base_dir=case_path.parent, purpose=purpose)
    result["issues"].extend(manifest_issues)
    result["passed"] = not any(item["severity"] == "error" for item in result["issues"])
    if not result["passed"]:
        return {"state": "blocked", "validation": result}
    if any(not Path(p).is_file() or sha256(p) != h for p, h in material_hashes.items()):
        result["passed"] = False
        result["issues"].append(_issue("MATERIAL_CHANGED", "Manual, screenshot or source inventory changed during validation"))
        return {"state": "blocked", "validation": result}
    if root is None:
        return {"state": "blocked", "validation": result}
    target = Path(out).resolve()
    if target.is_relative_to(root):
        raise ValueError("material output must be outside the source tree")
    selected = value["code_material"]["files"]
    manual_path = inside(case_path.parent, value["manual"]["path"])
    manual_hash = material_hashes[str(manual_path)]
    with TemporaryDirectory(prefix="word-copyright-") as directory:
        temporary = Path(directory)
        case = temporary / "case"
        input_snapshot = temporary / "business-input.json"
        input_snapshot.write_bytes(source_bytes)
        paths = [input_snapshot, manual_path] + [inside(root, item["path"]) for item in selected]
        index = ingest(paths, case, text_inputs=[inside(root, item["path"]) for item in selected])
        if sha256(manual_path) != manual_hash:
            raise ValueError("manual changed during intake; revalidate")
        sources = {s["original_path"]: s for s in index["sources"]}
        identity = value["software"]
        rights = value.get("rights_holder") or {}
        if purpose == "preview":
            declaration = f"软件：{identity['name']}；版本：{identity['version']}。本件为材料草稿，完成日期、权属及正式申请字段尚待确认。"
        else:
            declaration = (f"申请人声明的软件：{identity['name']}；版本：{identity['version']}；"
                           f"完成日期：{identity['completion_date']}；权利人：{rights['name']}。"
                           f"权属声明依据：{rights['confirmation_note']}")
        captions = [f"文件：{item['path']}；原文件行段：{item['line_start']}—{item['line_end']}。" for item in selected]
        metadata = sources[str(input_snapshot)]
        segments = read_json(inside(case, metadata["segments"]))
        quote = "\n".join(segment["text"] for segment in segments)
        claims = [{
            "id": "input-transcription", "statement": declaration + "\n" + "\n".join(captions),
            "source_id": metadata["id"], "quote": quote,
            "locators": [s["locator"] for s in segments],
            "status": "verified", "verified_by": "literal input transcription; not ownership verification", "verified_at": _utc_now()}]
        code_blocks = []
        for number, item in enumerate(selected):
            source = sources.get(str(inside(root, item["path"])))
            if source is None or source["sha256"] != item["sha256"]:
                raise ValueError("selected source changed during intake; scan again")
            text, _ = _read_source(inside(case, source["snapshot"]))
            excerpt = "".join(text.splitlines(keepends=True)[item["line_start"] - 1:item["line_end"]])
            code_blocks += [
                {"id": f"caption-{number}", "type": "paragraph", "intent": "fact", "text": captions[number], "claim_ids": ["input-transcription"]},
                {"id": f"source-{number}", "type": "code", "intent": "fact", "text": excerpt,
                 "source_id": source["id"], "line_start": item["line_start"], "line_end": item["line_end"], "claim_ids": []}]
        draft = {"schema_version": 1, "mode": "copyright-source", "title": "软件源代码鉴别材料", "sections": [
            {"id": "identity", "title": "申请人声明与材料范围", "blocks": [
                {"id": "identity-body", "type": "paragraph", "intent": "fact", "text": declaration, "claim_ids": ["input-transcription"]},
                {"id": "limit", "type": "paragraph", "intent": "analysis", "text": "本材料记录提供的声明与源码选段；程序未确认权属、完整登记材料资格或受理条件。", "claim_ids": []}]},
            {"id": "source", "title": "原文源码选段", "blocks": code_blocks}]}
        if document == "manual":
            source = sources[str(manual_path)]
            manual_segments = read_json(inside(case, source["segments"]))
            quote = "\n".join(s["text"] for s in manual_segments)
            manual_text = inside(case, source["extracted"]).read_text(encoding="utf-8")
            claims.append({"id": "manual-transcription", "statement": manual_text,
                           "source_id": source["id"], "quote": quote,
                           "locators": [s["locator"] for s in manual_segments], "status": "verified",
                           "verified_by": "literal manual transcription; semantic review remains required", "verified_at": _utc_now()})
            from .copyright_manual import markdown_blocks
            blocks = markdown_blocks(manual_text, value["screenshots"], case_path.parent, case)
            draft = {"schema_version": 1, "mode": "copyright-manual", "title": "软件操作说明书",
                     "sections": [{"id": "identity", "title": "软件信息", "blocks": [
                         {"id": "software-identity", "type": "paragraph", "intent": "fact",
                          "text": f"{value['software']['name']} {value['software']['version']}",
                          "claim_ids": ["input-transcription"]}]},
                         {"id": "manual", "title": "功能与操作说明", "blocks": blocks}]}
        draft.update(software_name=value["software"]["name"], software_version=value["software"]["version"])
        write_json(case / "evidence.json", {"schema_version": 1, "claims": claims})
        if value.get("case_id"):
            draft.update(case_id=value["case_id"], document_id=f"copyright-{document}")
        draft_path = temporary / "draft.json"
        write_json(draft_path, draft)
        built = shared_build(draft_path, case, target, soffice=soffice, pdftoppm=pdftoppm, no_preview=no_preview, business_gate="copyright")
    if built["state"] in ("business-pending", "draft"):
        extras = [inside(case_path.parent, item["path"]) for item in value["screenshots"]]
        if manifest_path is not None:
            extras.append(manifest_path)
        extras.extend(Path(p) for p in _knowledge_materials(value, case_path.parent))
        bound = bind_business_audit(target, "copyright", case_path, result, extras,
                                    source_bytes=source_bytes, extra_hashes=material_hashes)
        if purpose == "preview" and bound["state"] in {"awaiting-review", "draft"}:
            bound.update(state="draft", preparation_only=True)
            write_json(target / "manifest.json", bound)
        return bound
    return built
