import json

import pytest

from word_skills.cli import main
from word_skills.common import read_json, sha256, write_json
from word_skills.content_lock import freeze_content
from word_skills.evidence import contract
from word_skills.ingest import ingest
from word_skills.locked_delivery import build_locked


def fixture(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("系统采用 Java 17。\n", encoding="utf-8")
    case = tmp_path / "case"
    ingest([source], case)
    write_json(case / "evidence.json", {"schema_version": 1, "claims": [{
        "id": "C1", "statement": "系统采用 Java 17。", "source_id": "S001", "locators": ["L1"],
        "quote": "系统采用 Java 17。", "status": "verified", "verified_by": "integration-fixture",
        "verified_at": "2026-10-21"}]})
    draft = {"schema_version": 1, "mode": "technical-report", "title": "锁定链路集成测试", "sections": [
        {"id": sid, "title": title, "blocks": [{"id": sid + "b", "type": "paragraph", "intent": "fact",
            "text": "系统采用 Java 17。", "claim_ids": ["C1"]}]}
        for sid, title in contract("technical-report")["required_sections"].items()]}
    path, patch = tmp_path / "draft.json", tmp_path / "patch.json"
    write_json(path, draft)
    write_json(patch, {"blocks": {"backgroundb": {"inline_format": "markdown"}}})
    return path, case, patch


def test_actual_cli_freeze_format_build_preserves_inputs(tmp_path, capsys):
    path, case, patch = fixture(tmp_path)
    before = {p: sha256(p) for p in [path, *case.rglob("*")] if p.is_file()}
    bundle = tmp_path / "lock"
    assert main(["freeze-content", str(path), "--case", str(case), "--out", str(bundle)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "content_locked"
    assert main(["format-content", str(bundle), "--patch", str(patch), "--out", str(tmp_path / "formatted.json")]) == 0
    capsys.readouterr()
    output = tmp_path / "build"
    assert main(["build-locked", str(bundle), "--patch", str(patch), "--out", str(output), "--no-preview"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "draft" and result["finalized"] is False
    assert result["semantic_review"] == "not_performed"
    assert (output / "delivery/output.docx").is_file()
    assert before == {p: sha256(p) for p in before}
    assert result["draft_sha256"] == sha256(output / "delivery/audit/draft.json")


@pytest.mark.parametrize("kind", ["source", "ledger", "text-patch", "business-mode"])
def test_cli_rejects_tampering_without_docx(tmp_path, capsys, kind):
    path, case, patch = fixture(tmp_path)
    bundle, output = tmp_path / "lock", tmp_path / "build"
    if kind == "business-mode":
        data = read_json(path)
        data["mode"] = "project-proposal"
        write_json(path, data)
        assert main(["freeze-content", str(path), "--case", str(case), "--out", str(bundle)]) == 2
        return
    freeze_content(path, case, bundle)
    if kind == "source":
        index = read_json(bundle / "case/source-index.json")
        (bundle / "case" / index["sources"][0]["snapshot"]).write_text("changed", encoding="utf-8")
    elif kind == "ledger":
        write_json(bundle / "case/evidence.json", {"claims": []})
    else:
        write_json(patch, {"blocks": {"backgroundb": {"text": "changed"}}})
    assert main(["build-locked", str(bundle), "--patch", str(patch), "--out", str(output), "--no-preview"]) == 2
    assert not list(output.rglob("*.docx"))


def test_post_build_integrity_failure_invalidates_child(tmp_path, monkeypatch):
    import word_skills.locked_delivery as module
    path, case, patch = fixture(tmp_path)
    bundle, output = tmp_path / "lock", tmp_path / "build"
    freeze_content(path, case, bundle)
    original = module.build

    def changed_audit(*args, **kwargs):
        result = original(*args, **kwargs)
        (output / "delivery/audit/evidence.json").write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(module, "build", changed_audit)
    with pytest.raises(ValueError, match="changed case input"):
        build_locked(bundle, patch, output, no_preview=True)
    assert read_json(output / "delivery/manifest.json")["state"] == "failed"
    assert read_json(output / "locked-build-manifest.json")["state"] == "failed"


def test_cli_existing_output_preserved(tmp_path, capsys):
    path, case, patch = fixture(tmp_path)
    bundle, output = tmp_path / "lock", tmp_path / "build"
    freeze_content(path, case, bundle)
    output.mkdir()
    marker = output / "owner.txt"
    marker.write_text("preserve", encoding="utf-8")
    assert main(["build-locked", str(bundle), "--patch", str(patch), "--out", str(output), "--no-preview"]) == 2
    assert marker.read_text(encoding="utf-8") == "preserve"
