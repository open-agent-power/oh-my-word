"""Build a reviewable document from frozen content and a constrained style patch."""
from __future__ import annotations

import shutil
from pathlib import Path

from .common import digest, read_json, sha256, write_json
from .content_lock import format_locked, verify_lock
from .delivery import build


def build_locked(bundle, patch, output, template=None, template_mode="style",
                 soffice=None, pdftoppm=None, no_preview=False):
    bundle, patch, output = Path(bundle).resolve(), Path(patch).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output directory already exists; choose a fresh path")
    if output.is_relative_to(bundle):
        raise ValueError("Delivery must be outside the lock bundle")
    locked = verify_lock(bundle)
    formatted = format_locked(bundle, patch, output / "draft.json")
    format_manifest = read_json(formatted["format_manifest_path"])
    expected_patch = format_manifest["formatting"]["patch_sha256"]
    expected_draft = format_manifest["formatting"]["output_sha256"]
    record = {"schema_version": 1, "record_kind": "build_time_snapshot",
              "review_state_authority": "delivery/manifest.json",
              "lock_id": locked["lock_id"],
              "state": "failed", "semantic_review": "not_performed", "finalized": False,
              "patch_sha256": expected_patch, "draft_sha256": expected_draft,
              "lock_manifest_sha256": sha256(locked["manifest_path"])}
    child_path = output / "delivery" / "manifest.json"
    try:
        # Keep the submitted patch with this delivery; never read arbitrary paths
        # from it or use it to supply replacement content.
        if sha256(patch) != expected_patch:
            raise ValueError("Patch changed before build")
        shutil.copyfile(patch, output / "layout-patch.json")
        if sha256(output / "layout-patch.json") != expected_patch or sha256(patch) != expected_patch:
            raise ValueError("Patch changed during build")
        child = build(formatted["draft_path"], locked["case_path"], output / "delivery",
                      template, template_mode, soffice, pdftoppm, no_preview)
        if verify_lock(bundle)["lock_id"] != locked["lock_id"]:
            raise ValueError("Lock changed during build")
        if sha256(locked["manifest_path"]) != record["lock_manifest_sha256"]:
            raise ValueError("Lock metadata changed during build")
        if sha256(formatted["draft_path"]) != expected_draft:
            raise ValueError("Formatted draft changed during build")
        audit = output / "delivery" / "audit"
        if sha256(audit / "draft.json") != expected_draft:
            raise ValueError("Build consumed a different draft")
        for rel, checksum in locked["inputs"].items():
            if rel.startswith("case/"):
                if sha256(audit / rel.removeprefix("case/")) != checksum:
                    raise ValueError(f"Build consumed a changed case input: {rel}")
        record.update(state=child["state"], build_id=child.get("build_id"),
                      delivery="delivery", delivery_manifest_sha256=sha256(child_path),
                      format_manifest_sha256=sha256(formatted["format_manifest_path"]))
        record["record_digest"] = digest(record)
        write_json(output / "locked-build-manifest.json", record)
    except Exception as exc:
        # A successful child preview must not retain an approvable state if the
        # enclosing integrity check fails. Preserve artifacts for diagnosis.
        if child_path.is_file():
            child = read_json(child_path)
            child["state"] = "failed"
            child["locked_content_error"] = str(exc)
            write_json(child_path, child)
        record["error"] = str(exc)
        write_json(output / "locked-build-manifest.json", record)
        raise
    return record
