import base64

import pytest

from word_skills.common import digest, read_json, sha256, write_json
from word_skills.content_lock import _manifest_digest, format_locked, freeze_content, verify_lock
from word_skills.evidence import contract
from word_skills.ingest import ingest


def setup_case(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("系统采用 Java 17。\n系统提供查询接口。\n", encoding="utf-8")
    case = tmp_path / "case"
    ingest([source], case)
    write_json(case / "evidence.json", {"schema_version": 1, "claims": [{
        "id": "C1", "statement": "系统采用 Java 17。", "source_id": "S001", "locators": ["L1"],
        "quote": "系统采用 Java 17。", "status": "verified", "verified_by": "fixture", "verified_at": "2026-10-20"}]})
    draft = {"schema_version": 1, "mode": "technical-report", "title": "系统技术报告", "version": "v1", "sections": [
        {"id": sid, "title": title, "blocks": [{"id": sid + "b", "type": "paragraph", "intent": "fact",
          "text": "系统采用 Java 17。", "claim_ids": ["C1"]}]}
        for sid, title in contract("technical-report")["required_sections"].items()]}
    path = tmp_path / "draft.json"
    write_json(path, draft)
    return source, case, draft, path


def test_freeze_and_style_format_roundtrip_preserves_inputs(tmp_path):
    source, case, draft, draft_path = setup_case(tmp_path)
    before = {str(p): p.read_bytes() for p in [draft_path, *case.rglob("*")] if p.is_file()}
    bundle = tmp_path / "lock"
    frozen = freeze_content(draft_path, case, bundle)
    assert frozen["state"] == "content_locked"
    patch_path = tmp_path / "patch.json"
    write_json(patch_path, {"blocks": {"backgroundb": {"inline_format": "markdown"}}})
    output = tmp_path / "formatted.json"
    formatted = format_locked(bundle, patch_path, output)
    result = read_json(output)
    assert result["sections"][0]["blocks"][0]["text"] == draft["sections"][0]["blocks"][0]["text"]
    assert result["sections"][0]["blocks"][0]["inline_format"] == "markdown"
    assert formatted["state"] == "content-locked-needs-review"
    assert formatted["manifest"]["needs_semantic_review"] is True
    assert "not_performed" == verify_lock(bundle)["manifest"]["semantic_review"]
    assert before == {str(p): p.read_bytes() for p in [draft_path, *case.rglob("*")] if p.is_file()}


def test_freeze_requires_passed_mechanical_validation(tmp_path):
    _, case, draft, path = setup_case(tmp_path)
    draft["sections"][0]["blocks"][0]["text"] = "采用未证实吞吐量 99999 QPS。"
    write_json(path, draft)
    with pytest.raises(ValueError, match="mechanical evidence validation"):
        freeze_content(path, case, tmp_path / "lock")


@pytest.mark.parametrize("tamper", ["draft", "source", "evidence", "lock"])
def test_verify_lock_rejects_modified_inputs(tmp_path, tamper):
    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    if tamper == "draft":
        data = read_json(bundle / "draft.json")
        data["sections"][0]["blocks"][0]["text"] += "变更"
        write_json(bundle / "draft.json", data)
    elif tamper == "source":
        (bundle / "case" / "sources" / "S001" / "original.txt").write_text("changed", encoding="utf-8")
    elif tamper == "evidence":
        data = read_json(bundle / "case" / "evidence.json")
        data["claims"][0]["statement"] += "变更"
        write_json(bundle / "case" / "evidence.json", data)
    else:
        data = read_json(bundle / "lock-manifest.json")
        data["semantic_review"] = "passed"
        write_json(bundle / "lock-manifest.json", data)
    with pytest.raises(ValueError):
        verify_lock(bundle)


@pytest.mark.parametrize("patch", [
    {"blocks": {"backgroundb": {"text": "rewritten"}}},
    {"blocks": {"unknown": {"style": "Table Grid"}}},
    {"blocks": {"backgroundb": {"style": "Normal"}}},
    {"blocks": {"backgroundb": {"claim_ids": []}}},
    {"blocks": {"backgroundb": {"inline_format": "html"}}},
    {"blocks": {"backgroundb": {"inline_format": "markdown", "title": "changed"}}},
])
def test_rejects_non_style_or_invalid_patch(tmp_path, patch):
    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    patch_path, output = tmp_path / "patch.json", tmp_path / "formatted.json"
    write_json(patch_path, patch)
    with pytest.raises(ValueError):
        format_locked(bundle, patch_path, output)
    assert not output.exists()


def test_path_escape_and_non_overwrite(tmp_path):
    _, case, _, path = setup_case(tmp_path)
    with pytest.raises(ValueError, match="outside the source case"):
        freeze_content(path, case, case / "bundle")
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    with pytest.raises(ValueError, match="already exists"):
        freeze_content(path, case, bundle)
    patch_path, output = tmp_path / "patch.json", tmp_path / "formatted.json"
    write_json(patch_path, {"blocks": {}})
    format_locked(bundle, patch_path, output)
    with pytest.raises(ValueError, match="already exists"):
        format_locked(bundle, patch_path, output)


def test_rejects_case_registry_path_escape(tmp_path):
    _, case, _, path = setup_case(tmp_path)
    index = read_json(case / "source-index.json")
    index["sources"][0]["snapshot"] = "../outside.txt"
    write_json(case / "source-index.json", index)
    with pytest.raises(ValueError, match="canonical relative path"):
        freeze_content(path, case, tmp_path / "lock")


@pytest.mark.parametrize("bad_path", [
    "C:/outside.txt", "C:\\outside.txt", "/outside.txt", "../outside.txt",
    "sources/../outside.txt", "./sources/S001/original.txt", "sources//S001/original.txt",
])
def test_rejects_noncanonical_index_paths(tmp_path, bad_path):
    _, case, _, path = setup_case(tmp_path)
    index = read_json(case / "source-index.json")
    index["sources"][0]["snapshot"] = bad_path
    write_json(case / "source-index.json", index)
    with pytest.raises(ValueError, match="canonical relative path"):
        freeze_content(path, case, tmp_path / "lock")


@pytest.mark.parametrize("tamper", ["omit_case_input", "redirect_draft"])
def test_verify_lock_rejects_rehashed_registry_tampering(tmp_path, tamper):
    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    manifest_path = bundle / "lock-manifest.json"
    manifest = read_json(manifest_path)
    if tamper == "omit_case_input":
        manifest["inputs"].pop("case/sources/S001/segments.json")
        manifest["lock_id"] = digest({"inputs": manifest["inputs"], "semantic": manifest["semantic_content_digest"]})
    else:
        manifest["draft_path"] = "case/evidence.json"
    manifest["manifest_digest"] = _manifest_digest(manifest)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError):
        verify_lock(bundle)


def test_failed_freeze_leaves_partial_bundle_without_lock(tmp_path, monkeypatch):
    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"

    def fail_copy(*_args, **_kwargs):
        raise RuntimeError("simulated copy failure")

    monkeypatch.setattr("word_skills.content_lock._copy_stable", fail_copy)
    with pytest.raises(RuntimeError, match="simulated copy failure"):
        freeze_content(path, case, bundle)
    assert bundle.is_dir()
    assert not (bundle / "lock-manifest.json").exists()


def test_existing_companion_summary_prevents_output_creation(tmp_path):
    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    patch_path, output = tmp_path / "patch.json", tmp_path / "formatted.json"
    write_json(patch_path, {"blocks": {}})
    summary = tmp_path / "formatted.format-manifest.json"
    summary.write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="summary already exists"):
        format_locked(bundle, patch_path, output)
    assert not output.exists()
    assert summary.read_text(encoding="utf-8") == "preserve"


def test_same_image_asset_can_be_referenced_by_multiple_blocks(tmp_path):
    _, case, draft, path = setup_case(tmp_path)
    asset = case / "assets" / "pixel.png"
    asset.parent.mkdir()
    asset.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j60QAAAAASUVORK5CYII="))
    image = {"id": "figure", "type": "image", "intent": "gap", "text": "示意图",
             "claim_ids": [], "path": "assets/pixel.png", "sha256": sha256(asset)}
    draft["sections"][0]["blocks"].append(dict(image))
    second = dict(image, id="figure-copy")
    draft["sections"][1]["blocks"].append(second)
    write_json(path, draft)
    frozen = freeze_content(path, case, tmp_path / "lock")
    assert list(frozen["manifest"]["inputs"]).count("case/assets/pixel.png") == 1


def test_concurrent_output_created_during_exclusive_open_is_preserved(tmp_path, monkeypatch):
    import word_skills.content_lock as module

    _, case, _, path = setup_case(tmp_path)
    bundle = tmp_path / "lock"
    freeze_content(path, case, bundle)
    patch_path, output = tmp_path / "patch.json", tmp_path / "formatted.json"
    write_json(patch_path, {"blocks": {}})
    real_write = module._write_json_new

    def simulate_race(target, value):
        if target == output:
            output.write_text("other writer's file", encoding="utf-8")
            raise FileExistsError(str(output))
        real_write(target, value)

    monkeypatch.setattr(module, "_write_json_new", simulate_race)
    with pytest.raises(FileExistsError):
        format_locked(bundle, patch_path, output)
    assert output.read_text(encoding="utf-8") == "other writer's file"
