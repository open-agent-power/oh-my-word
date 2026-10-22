"""Opt-in content freeze and style-only formatting for v1 evidence-bound drafts.

This records reproducible input hashes. It is a mechanical integrity aid, not a
signature, semantic review, or operating-system isolation boundary.
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

from .common import digest, inside, read_json, sha256
from .evidence import contract, validate
from .models import validate_draft_v1

LOCK_NAME = "lock-manifest.json"
LOCK_SCHEMA = 1
_STYLE_FIELDS = {"widths", "style", "inline_format"}


def _semantic_draft(draft):
    """Drop only explicitly format-only keys, preserving all semantic data."""
    result = copy.deepcopy(draft)
    for section in result.get("sections", []):
        for block in section.get("blocks", []):
            for key in _STYLE_FIELDS:
                block.pop(key, None)
    return result


def _copy_stable(source: Path, target: Path, expected: str):
    before = sha256(source)
    if before != expected:
        raise ValueError(f"Input changed before freeze: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(source) != before or sha256(target) != before:
        raise ValueError(f"Input changed during freeze: {source}")


def _canonical_relative(value):
    """Require one canonical POSIX relative path on every host platform."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"Input path must be a canonical relative path: {value!r}")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (posix.is_absolute() or windows.is_absolute() or windows.drive or
            any(part in {"", ".", ".."} for part in value.split("/")) or posix.as_posix() != value):
        raise ValueError(f"Input path must be a canonical relative path: {value!r}")
    return value


def _registered_files(case: Path, draft: dict):
    """Yield only source-index records and draft-declared local image assets."""
    index_path = inside(case, "source-index.json")
    ledger_path = inside(case, "evidence.json")
    index = read_json(index_path)
    paths = ["source-index.json", "evidence.json"]
    for source in index["sources"]:
        for key in ("snapshot", "extracted", "segments"):
            rel = _canonical_relative(source[key])
            path = inside(case, rel)
            if not path.is_file():
                raise ValueError(f"Missing indexed source file: {rel}")
            paths.append(Path(rel).as_posix())
    image_paths = set()
    for section in draft["sections"]:
        for block in section["blocks"]:
            if block.get("type") == "image":
                rel = _canonical_relative(block["path"])
                path = inside(case, rel)
                if not path.is_file():
                    raise ValueError(f"Missing draft asset: {rel}")
                if rel not in image_paths:
                    paths.append(Path(rel).as_posix())
                    image_paths.add(rel)
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate registered case path")
    return paths


def _write_json_new(path, value):
    """Write JSON with exclusive creation so a concurrent file is never replaced."""
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _manifest_digest(manifest):
    value = copy.deepcopy(manifest)
    value.pop("manifest_digest", None)
    return digest(value)


def freeze_content(draft_path, case, output):
    """Validate, then copy draft and its registered evidence into a new bundle."""
    draft_path, case, output = Path(draft_path).resolve(), Path(case).resolve(), Path(output).resolve()
    if not draft_path.is_file() or not case.is_dir():
        raise ValueError("Draft file and case directory must exist")
    if output.exists():
        raise ValueError("Output directory already exists; choose a fresh path")
    if output.is_relative_to(case):
        raise ValueError("Lock bundle must be outside the source case")
    draft_bytes_hash = sha256(draft_path)
    draft = read_json(draft_path)
    validate_draft_v1(draft)
    if draft.get("mode") not in {"technical-report", "design-spec"}:
        raise ValueError("Content lock supports technical-report and design-spec drafts only")
    if contract(draft["mode"]).get("business_gate"):
        raise ValueError("Content lock cannot bypass a required business gate")
    # Snapshot the exact allow-listed case inputs before validation, then make
    # sure validation and copying observed this same state.
    paths = _registered_files(case, draft)
    input_hashes = {"draft.json": draft_bytes_hash}
    for rel in paths:
        input_hashes[f"case/{rel}"] = sha256(inside(case, rel))
    verdict = validate(draft, case)
    if not verdict["passed"]:
        raise ValueError("Cannot freeze: mechanical evidence validation failed")
    if sha256(draft_path) != draft_bytes_hash:
        raise ValueError("Draft changed during validation")
    for rel in paths:
        if sha256(inside(case, rel)) != input_hashes[f"case/{rel}"]:
            raise ValueError(f"Case input changed during validation: {rel}")
    semantic_digest = digest(_semantic_draft(draft))

    output.mkdir(parents=True)
    try:
        _copy_stable(draft_path, output / "draft.json", input_hashes["draft.json"])
        for rel in paths:
            _copy_stable(inside(case, rel), inside(output / "case", rel), input_hashes[f"case/{rel}"])
        copied_draft = read_json(output / "draft.json")
        if digest(_semantic_draft(copied_draft)) != semantic_digest:
            raise ValueError("Draft content changed during freeze")
        manifest = {
            "schema_version": LOCK_SCHEMA,
            "state": "content_locked",
            "mechanical_validation": verdict,
            "semantic_review": "not_performed",
            "semantic_content_digest": semantic_digest,
            "inputs": input_hashes,
            "draft_path": "draft.json",
            "case_path": "case",
            "formatting": None,
        }
        manifest["lock_id"] = digest({"inputs": input_hashes, "semantic": semantic_digest})
        manifest["manifest_digest"] = _manifest_digest(manifest)
        _write_json_new(output / LOCK_NAME, manifest)
    except Exception:
        # Keep a failed partial bundle for inspection; never recursively remove
        # a directory that another process or user may have populated.
        raise
    return {"bundle_path": str(output), "draft_path": str(output / "draft.json"),
            "case_path": str(output / "case"), "manifest_path": str(output / LOCK_NAME),
            "manifest": manifest, "bundle": str(output), "state": "content_locked",
            "lock_id": manifest["lock_id"]}


def verify_lock(bundle):
    """Check lock metadata and every allow-listed input hash in the bundle."""
    bundle = Path(bundle).resolve()
    manifest_path = inside(bundle, LOCK_NAME)
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != LOCK_SCHEMA or manifest.get("manifest_digest") != _manifest_digest(manifest):
        raise ValueError("Lock manifest is invalid or changed")
    expected_lock_id = digest({"inputs": manifest.get("inputs"), "semantic": manifest.get("semantic_content_digest")})
    if manifest.get("lock_id") != expected_lock_id:
        raise ValueError("Lock identity is invalid")
    if manifest.get("draft_path") != "draft.json" or manifest.get("case_path") != "case":
        raise ValueError("Lock manifest paths are invalid")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict) or not inputs or "draft.json" not in inputs:
        raise ValueError("Lock input registry is invalid")
    for rel, checksum in inputs.items():
        _canonical_relative(rel)
        path = inside(bundle, rel)
        if not path.is_file() or sha256(path) != checksum:
            raise ValueError(f"Locked input changed: {rel}")
    draft = read_json(inside(bundle, manifest["draft_path"]))
    validate_draft_v1(draft)
    expected_paths = {"draft.json"} | {f"case/{rel}" for rel in _registered_files(inside(bundle, "case"), draft)}
    if set(inputs) != expected_paths:
        raise ValueError("Lock input registry does not match the copied draft and source index")
    if digest(_semantic_draft(draft)) != manifest.get("semantic_content_digest"):
        raise ValueError("Locked semantic content changed")
    return {"bundle_path": str(bundle), "draft_path": str(inside(bundle, manifest["draft_path"])),
            "case_path": str(inside(bundle, manifest["case_path"])), "manifest_path": str(manifest_path),
            "manifest": manifest, "draft": draft, "lock_id": manifest["lock_id"],
            "inputs": manifest["inputs"]}


def _apply_patch(draft, patch):
    if not isinstance(patch, dict) or set(patch) != {"blocks"} or not isinstance(patch["blocks"], dict):
        raise ValueError("Patch must contain only a blocks object")
    blocks = {block["id"]: block for section in draft["sections"] for block in section["blocks"]}
    for block_id, changes in patch["blocks"].items():
        if block_id not in blocks:
            raise ValueError(f"Unknown block ID: {block_id}")
        if not isinstance(changes, dict) or not changes or set(changes) - _STYLE_FIELDS:
            raise ValueError(f"Invalid style patch for block: {block_id}")
        kind = blocks[block_id].get("type")
        allowed = {"widths", "style"} if kind == "table" else ({"inline_format"} if kind == "paragraph" else set())
        if set(changes) - allowed:
            raise ValueError(f"Style patch is not supported for {kind}: {block_id}")
        blocks[block_id].update(copy.deepcopy(changes))
    validate_draft_v1(draft)


def format_locked(bundle, patch_path, output):
    """Apply a constrained style patch to a new output draft; keep the lock intact."""
    locked = verify_lock(bundle)
    bundle = Path(bundle).resolve()
    patch_path, output = Path(patch_path).resolve(), Path(output).resolve()
    if output.is_relative_to(bundle):
        raise ValueError("Formatted draft must be outside the lock bundle")
    if not patch_path.is_file():
        raise ValueError("Patch file must exist")
    if output.exists():
        raise ValueError("Output file already exists; choose a fresh path")
    summary_path = output.with_name(output.stem + ".format-manifest.json")
    if summary_path.exists():
        raise ValueError("Formatting summary already exists; choose a fresh output name")
    patch_hash = sha256(patch_path)
    patch = read_json(patch_path)
    draft = copy.deepcopy(locked["draft"])
    _apply_patch(draft, patch)
    if digest(_semantic_draft(draft)) != locked["manifest"]["semantic_content_digest"]:
        raise ValueError("Formatting patch changed semantic content")
    output.parent.mkdir(parents=True, exist_ok=True)
    output_created = False
    output_created_hash = None
    try:
        _write_json_new(output, draft)
        output_created = True
        output_created_hash = sha256(output)
        if sha256(patch_path) != patch_hash:
            raise ValueError("Patch changed during formatting")
        if verify_lock(bundle)["lock_id"] != locked["lock_id"]:
            raise ValueError("Lock changed during formatting")
    except Exception:
        if output_created and output.is_file() and sha256(output) == output_created_hash:
            output.unlink(missing_ok=True)
        raise
    manifest_path = inside(bundle, LOCK_NAME)
    manifest = copy.deepcopy(locked["manifest"])
    manifest["state"] = "formatter_only_not_finalized"
    manifest["needs_semantic_review"] = True
    manifest["formatting"] = {"patch_sha256": patch_hash, "output_sha256": sha256(output),
                               "output_path": str(output)}
    manifest["manifest_digest"] = _manifest_digest(manifest)
    # Record the result in a companion summary; the frozen lock itself remains byte-for-byte unchanged.
    if summary_path.exists():
        if output.is_file() and sha256(output) == output_created_hash:
            output.unlink(missing_ok=True)
        raise ValueError("Formatting summary already exists; choose a fresh output name")
    if not output.is_file() or sha256(output) != output_created_hash:
        raise ValueError("Formatted output changed during formatting")
    _write_json_new(summary_path, manifest)
    return {"draft_path": str(output), "case_path": locked["case_path"],
            "bundle_path": str(bundle), "manifest_path": str(manifest_path),
            "format_manifest_path": str(summary_path), "manifest": manifest,
            "lock_id": manifest["lock_id"], "state": "content-locked-needs-review"}
