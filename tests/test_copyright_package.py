"""Real file preparation/bundling contracts; no mocked Office rendering claims."""
import pytest

from word_skills.common import read_json, write_json
from word_skills import copyright
from word_skills.copyright_package import prepare, apply_selection, package, finalize_package


@pytest.fixture
def case(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "main.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
    folder = tmp_path / "case"
    prepare(root, folder, name="示例工具", version="v1.0")
    selection = read_json(folder / "selection.json")
    selection["reviewed_by"] = "test source reviewer"
    selection["files"][0].update(selected=True, reason="真实入口")
    write_json(folder / "selection.json", selection)
    path = folder / "copyright.json"
    apply_selection(path)
    draft = read_json(path)
    draft["application"]["category"] = "命令行软件"
    draft["manual"]["verified_against"] = "executed greet in test fixture"
    write_json(path, draft)
    (folder / "manual.md").write_text("# 示例工具 v1.0\n运行 greet 返回 hello。\n", encoding="utf-8")
    return path, root


def test_prepare_never_selects_or_confirms_rights(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    (root / "main.py").write_text("print('hello')", encoding="utf-8")
    out = tmp_path / "case"
    prepare(root, out)
    assert not any(item["selected"] for item in read_json(out / "selection.json")["files"])
    assert read_json(out / "copyright.json")["rights_holder"]["ownership_confirmed"] is False
    with pytest.raises(ValueError, match="outside"):
        prepare(root, root / "output")


def test_selection_is_bound_to_inventory_and_original(case):
    path, root = case
    (root / "main.py").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        apply_selection(path)


def test_draft_bundle_exports_manual_code_and_auxiliary_fields(case, tmp_path):
    path, _ = case
    out = tmp_path / "bundle"
    result = package(path, out, draft=True, no_preview=True)
    assert result["state"] == "draft"
    assert result["ready_for_submission"] is False
    assert (out / "source/output.docx").is_file()
    assert (out / "manual/output.docx").is_file()
    assert "[未确认]" in (out / "application-info.txt").read_text(encoding="utf-8")
    assert read_json(out / "source/manifest.json")["preparation_only"]
    assert read_json(out / "manual/manifest.json")["preparation_only"]
    source_manifest = read_json(out / "source/manifest.json")
    manual_manifest = read_json(out / "manual/manifest.json")
    assert source_manifest["case_id"] == manual_manifest["case_id"]
    assert source_manifest["document_id"] != manual_manifest["document_id"]
    assert source_manifest["build_id"] != manual_manifest["build_id"]
    assert read_json(out / "pagination.json")["documents"]["source"]["actual_pages"] is None
    with pytest.raises(ValueError, match="registration"):
        finalize_package(out)


def test_registration_bundle_blocks_unknown_rights(case, tmp_path):
    path, _ = case
    out = tmp_path / "formal"
    result = package(path, out, no_preview=True)
    assert result["state"] == "blocked"
    assert not out.exists()


def test_preview_does_not_relax_source_or_software_identity(case, tmp_path):
    path, root = case
    draft = read_json(path)
    draft["software"]["name"] = ""
    write_json(path, draft)
    assert package(path, tmp_path / "missing-name", draft=True, no_preview=True)["state"] == "blocked"
    draft["software"]["name"] = "示例工具"
    write_json(path, draft)
    (root / "main.py").write_text("changed\n", encoding="utf-8")
    assert package(path, tmp_path / "stale", draft=True, no_preview=True)["state"] == "blocked"


def test_source_preview_cannot_enter_review(case, tmp_path):
    from word_skills.delivery import review_init
    path, _ = case
    out = tmp_path / "source-preview"
    assert copyright.build(path, out, purpose="preview", no_preview=True)["state"] == "draft"
    with pytest.raises(ValueError, match="successful"):
        review_init(out)


def test_finalize_package_rejects_stale_skill_identity(tmp_path, monkeypatch):
    from word_skills import delivery
    from word_skills.common import sha256

    out = tmp_path / "bundle"
    child_folder = out / "source"
    audit = child_folder / "audit"
    audit.mkdir(parents=True)
    business = audit / "business-copyright.json"
    business.write_text("{}", encoding="utf-8")
    review = audit / "review.json"
    write_json(review, {"reviewer": "test reviewer"})
    write_json(child_folder / "manifest.json", {
        "state": "reviewed",
        "build_id": "build-1",
        "code_identity": delivery.code_identity(),
        "skill_identity": "skill-fingerprint-at-review",
        "inputs": {"audit/business-copyright.json": sha256(business)},
        "outputs": {},
        "review": {"path": "audit/review.json", "sha256": sha256(review)},
    })
    write_json(out / "manifest.json", {
        "purpose": "registration",
        "state": "awaiting-review",
        "input_sha256": sha256(business),
        "inputs": {},
        "outputs": {},
        "deliveries": {"source": {"path": "source", "build_id": "build-1"}},
    })
    monkeypatch.setattr(delivery, "skill_identity", lambda: "current-skill-fingerprint")

    with pytest.raises(ValueError, match="Skill instructions changed"):
        finalize_package(out)


def test_manual_change_after_validation_cannot_be_transcribed(case, tmp_path, monkeypatch):
    path, _ = case
    original = copyright.validate_copyright
    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        (path.parent / "manual.md").write_text("替换后的不相关文本", encoding="utf-8")
        return result
    monkeypatch.setattr(copyright, "validate_copyright", changing)
    result = copyright.build(path, tmp_path / "changed-manual", purpose="preview", no_preview=True)
    assert result["state"] == "blocked"
    assert any(i["code"] == "MATERIAL_CHANGED" for i in result["validation"]["issues"])


def test_children_cannot_mix_distinct_business_inputs(case, tmp_path, monkeypatch):
    path, _ = case
    original_bytes = path.read_bytes()
    original = copyright.build
    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("document") == "source":
            changed = read_json(path)
            changed["application"]["category"] = "另一软件类别"
            write_json(path, changed)
        else:
            path.write_bytes(original_bytes)
        return result
    monkeypatch.setattr(copyright, "build", changing)
    result = package(path, tmp_path / "mixed", draft=True, no_preview=True)
    assert result["state"] == "failed"
    assert "snapshot" in result["reason"]


@pytest.mark.parametrize("operation", ["replace", "delete"])
def test_inventory_cannot_change_or_disappear_during_validation(case, tmp_path, monkeypatch, operation):
    path, _ = case
    original = copyright._manifest
    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        inventory = path.parent / "source-manifest.json"
        if inventory.exists():
            if operation == "delete":
                inventory.unlink()
            else:
                write_json(inventory, {"schema_version": 999, "files": []})
        return result
    monkeypatch.setattr(copyright, "_manifest", changing)
    result = copyright.build(path, tmp_path / operation, purpose="preview", no_preview=True)
    assert result["state"] == "blocked"
    assert any(i["code"] == "MATERIAL_CHANGED" for i in result["validation"]["issues"])
