from copy import deepcopy

import pytest

from word_skills.common import write_json
from word_skills.copyright import (build, copyright_template, extract_materials, scan_sources,
                                    validate_copyright)


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "core.py").write_text("def ping():\n    return 'ok'\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules/vendor.py").write_text("secret = 1", encoding="utf-8")
    (root / ".env.py").write_text("password = 'private'", encoding="utf-8")
    (root / "leak.py").write_text("GITHUB_TOKEN = 'abcdefghijklmnopqrstuvwxyz'", encoding="utf-8")
    manifest = scan_sources(root)
    manual = tmp_path / "manual.md"
    manual.write_text("# 示例工具 v1.0\n运行 ping 返回 ok。", encoding="utf-8")
    value = copyright_template()
    value["software"].update(name="示例工具", version="v1.0", completion_date="2026-10-16")
    value["rights_holder"].update(name="测试申请人", entity_type="个人", ownership_confirmed=True,
                                  confirmation_note="测试用申请人自述，非法律证明")
    value["source_manifest"] = manifest
    source = manifest["files"][0]
    value["code_material"].update(files=[{"path": source["path"], "line_start": 1, "line_end": 2,
                                           "sha256": source["sha256"], "reason": "真实入口函数"}],
                                  selected_line_count=2)
    value["application"].update(software_name="示例工具", software_version="v1.0",
                                applicant="测试申请人", category="应用软件")
    value["manual"].update(path="manual.md", software_name="示例工具", software_version="v1.0",
                           verified_against="测试脚本 ping()")
    path = tmp_path / "copyright.json"
    write_json(path, value)
    return value, root, path


def codes(result):
    return {issue["code"] for issue in result["issues"]}


def test_scan_excludes_dependencies_and_credentials(prepared):
    value, _, _ = prepared
    assert [item["path"] for item in value["source_manifest"]["files"]] == ["core.py"]
    assert any(item["reason"] == "credential-pattern" for item in value["source_manifest"]["excluded"])


def test_exact_extraction_and_unreviewed_word(prepared, tmp_path):
    value, root, path = prepared
    assert validate_copyright(value, source_root=root, base_dir=tmp_path)["passed"]
    result = extract_materials(path, tmp_path / "extract")
    assert result["materials"] == 1
    assert "def ping():" in (tmp_path / "extract/material-001.md").read_text(encoding="utf-8")
    result = build(path, tmp_path / "delivery", no_preview=True)
    assert result["state"] == "draft"
    assert (tmp_path / "delivery/output.docx").is_file()


def test_noncanonical_temporary_path_binds_to_ingested_source(prepared, tmp_path, monkeypatch):
    from contextlib import contextmanager
    from pathlib import Path
    import tempfile

    original = tempfile.TemporaryDirectory

    @contextmanager
    def aliased_directory(*args, **kwargs):
        with original(*args, **kwargs) as name:
            # Like Windows 8.3 names, this spells the same directory differently
            # from ingest's resolved original_path. No symlink permission needed.
            (Path(name) / "path-alias").mkdir()
            yield str(Path(name) / "path-alias" / "..")

    monkeypatch.setattr(tempfile, "TemporaryDirectory", aliased_directory)
    result = build(prepared[2], tmp_path / "aliased-delivery", no_preview=True)
    assert result["state"] == "draft"
    assert (tmp_path / "aliased-delivery/output.docx").is_file()


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["rights_holder"].update(ownership_confirmed=False), "RIGHTS_CONFIRMATION"),
    (lambda p: p["source_manifest"]["files"][0].update(line_count=999), "SOURCE_LINE_COUNT"),
    (lambda p: p["source_manifest"]["files"][0].update(path="../core.py"), "SOURCE_PATH"),
    (lambda p: p["code_material"]["files"][0].update(line_end=99), "CODE_RANGE"),
    (lambda p: p["code_material"]["files"][0].update(sha256="0"*64), "CODE_HASH"),
    (lambda p: p["manual"].update(software_version="other"), "IDENTITY_MISMATCH"),
    (lambda p: p["manual"].update(path="missing.md"), "MANUAL_SOURCE"),
    (lambda p: p.update(ui_type="visual"), "SCREENSHOTS"),
])
def test_copyright_failure_paths(prepared, tmp_path, mutation, code):
    value, root, _ = prepared
    changed = deepcopy(value)
    mutation(changed)
    assert code in codes(validate_copyright(changed, source_root=root, base_dir=tmp_path))


def test_source_change_and_overlap_are_rejected(prepared, tmp_path):
    value, root, _ = prepared
    second = deepcopy(value["code_material"]["files"][0])
    second.update(line_start=2, line_end=2)
    value["code_material"]["files"].append(second)
    assert "CODE_OVERLAP" in codes(validate_copyright(value, source_root=root, base_dir=tmp_path))
    (root / "core.py").write_text("def ping():\n    return 'changed'\n", encoding="utf-8")
    assert "SOURCE_CHANGED" in codes(validate_copyright(value, source_root=root, base_dir=tmp_path))


@pytest.mark.parametrize("filename,content", [
    ("keys.sh", "export GITHUB_TOKEN='abcdefghijklmnopqrstuvwxyz'"),
    ("keys.js", "const OPENAI_API_KEY = 'abcdefghijklmnopqrstuvwxyz';"),
    ("keys.py", "config = {'DATABASE_PASSWORD': 'abcdefghijklmnopqrstuvwxyz'}"),
])
def test_language_declarations_with_credentials_are_excluded(tmp_path, filename, content):
    (tmp_path / filename).write_text(content, encoding="utf-8")
    manifest = scan_sources(tmp_path)
    assert not manifest["files"]
    assert manifest["excluded"] == [{"path": filename, "reason": "credential-pattern"}]


def test_copyright_input_change_after_validation_fails(prepared, tmp_path, monkeypatch):
    from word_skills import delivery
    value, _, path = prepared
    original = delivery.build
    def changing_build(*args, **kwargs):
        result = original(*args, **kwargs)
        value["software"]["name"] = "changed after validation"
        write_json(path, value)
        return result
    monkeypatch.setattr(delivery, "build", changing_build)
    result = build(path, tmp_path / "delivery", no_preview=True)
    assert result["state"] == "failed"
