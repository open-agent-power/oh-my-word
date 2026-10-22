from pathlib import Path

import pytest

from word_skills.cli import main
from word_skills.common import read_json, sha256, write_json
from word_skills.knowledge import build_index
from word_skills.knowledge_context import retrieve_context, verify_context, domain_context, binding_for
from word_skills import copyright
from word_skills.copyright_package import package
from test_copyright_workflow import manual_case


@pytest.fixture
def kb(tmp_path):
    source = tmp_path / "pack"
    source.mkdir()
    docs = []
    for ident, kind, text in (("rules", "rule", "软件著作权登记应提交程序和文档鉴别材料。\r\n专利说明书应当清楚完整，权利要求以说明书为依据。\r\n"),
                              ("other-patent", "reference", "公开专利提出数据分类方法。\n"),
                              ("project", "project", "项目实际采用本地索引。\n")):
        path = source / (ident + ".md")
        path.write_bytes(text.encode("utf-8"))
        docs.append({"id": ident, "title": ident, "path": path.name, "sha256": sha256(path),
            "kind": kind, "topics": ["copyright", "patent"], "url": "https://example.test/" + ident,
            "revision": "fixture-v1", "retrieved_at": "2026-10-21T00:00:00Z"})
    write_json(source / "manifest.json", {"schema_version": 1, "name": "fixture", "domain": "copyright-patent", "documents": docs})
    target = tmp_path / "kb"
    build_index(source / "manifest.json", target)
    return target


def test_context_keeps_kinds_and_unverified_evidence(tmp_path, kb):
    out = tmp_path / "context"
    result = retrieve_context(kb, ["软件著作权 程序 文档"], out, kind="rule", topic="copyright")
    assert result["hits"] and verify_context(out)["semantic_review"] == "not_performed"
    assert read_json(out / "case/evidence.json")["claims"] == []
    candidates = read_json(out / "evidence-candidates.json")["candidates"]
    assert all(c["status"] == "unverified" and not c["project_fact_eligible"] and not c["statement"] for c in candidates)
    for c in candidates:
        source = next(s for s in read_json(out / "case/source-index.json")["sources"] if s["id"] == c["source_id"])
        segments = read_json(out / "case" / source["segments"])
        assert c["quote"] in "\n".join(s["text"] for s in segments if s["locator"] in c["locators"])
    project = tmp_path / "project-context"
    retrieve_context(kb, ["本地索引"], project, kind="project")
    assert read_json(project / "evidence-candidates.json")["candidates"][0]["project_fact_eligible"] is True
    assert read_json(project / "case/evidence.json")["claims"] == []


def test_no_hit_and_non_overwrite(tmp_path, kb):
    out = tmp_path / "missing"
    result = retrieve_context(kb, ["量子鲸鱼"], out)
    assert result["state"] == "no-evidence" and result["hits"] == 0
    assert verify_context(out)["missing_queries"] == ["量子鲸鱼"]
    with pytest.raises(ValueError, match="fresh"):
        retrieve_context(kb, ["专利"], out)


def test_retriever_change_during_search_is_rejected(tmp_path, kb, monkeypatch):
    from word_skills import knowledge
    original = knowledge.search

    def changing_search(*args, **kwargs):
        result = original(*args, **kwargs)
        (kb / "ragflow.json").write_text("{}", encoding="utf-8")
        return result

    monkeypatch.setattr(knowledge, "search", changing_search)
    with pytest.raises(ValueError, match="retriever changed"):
        retrieve_context(kb, ["专利"], tmp_path / "changing")


def test_context_tamper_and_copyright_prepare_binding(tmp_path, kb, capsys):
    project = tmp_path / "software"
    project.mkdir()
    (project / "main.py").write_text("print('hello')\n", encoding="utf-8")
    out = tmp_path / "copyright"
    assert main(["copyright", "prepare", str(project), "--out", str(out), "--name", "真实流程测试", "--version", "V0.1", "--knowledge", str(kb)]) == 0
    draft = read_json(out / "copyright.json")
    assert draft["rights_holder"]["ownership_confirmed"] is False
    assert draft["knowledge_context"]["purpose"] == "reference-only-not-project-facts"
    (out / "knowledge/context.md").write_text("tampered", encoding="utf-8")
    assert any(i["code"] == "KNOWLEDGE_CONTEXT" for i in copyright.validate_copyright(draft, base_dir=out, purpose="preview")["issues"])
    with pytest.raises(ValueError, match="changed"):
        verify_context(out / "knowledge")


def test_copyright_package_copies_and_binds_context(manual_case, tmp_path, kb):
    domain_context(kb, "copyright", manual_case / "knowledge")
    draft = read_json(manual_case / "copyright.json")
    draft["knowledge_context"] = binding_for(manual_case / "knowledge", manual_case)
    write_json(manual_case / "copyright.json", draft)
    out = tmp_path / "package"
    result = package(manual_case / "copyright.json", out, draft=True, no_preview=True)
    assert result["state"] == "draft"
    assert "audit/knowledge/context-manifest.json" in result["inputs"]
    assert verify_context(out / "audit/knowledge")["kb_id"] == draft["knowledge_context"]["kb_id"]
    for name in ("source", "manual"):
        child = read_json(out / name / "manifest.json")
        assert draft["knowledge_context"]["sha256"] in child["inputs"].values()


def test_patent_template_build_and_tampered_context(tmp_path, kb, capsys):
    from oh_my_patent.cli import main as patent
    draft, output = tmp_path / "draft.md", tmp_path / "draft.docx"
    assert patent(["template", "invention", "-o", str(draft), "--knowledge", str(kb)]) == 0
    # A real parsed repository sample exercises generation, while the references
    # remain separate and do not supply invented application identity or facts.
    example = Path(__file__).resolve().parents[1] / "examples/invention-example.md"
    draft.write_bytes(example.read_bytes())
    assert patent(["build", str(draft), "-o", str(output)]) == 0
    receipt = read_json(Path(str(output) + ".knowledge.json"))
    assert receipt["state"] == "reference-bound-not-semantic-reviewed"
    assert receipt["draft_sha256"] == sha256(draft)
    folder = Path(str(draft) + ".knowledge")
    (folder / "context.md").write_text("modified", encoding="utf-8")
    blocked = tmp_path / "bad.docx"
    assert patent(["build", str(draft), "-o", str(blocked)]) != 0
    assert not blocked.exists()


def test_actual_kb_cli(tmp_path, kb, capsys):
    assert main(["kb", "verify", str(kb)]) == 0
    capsys.readouterr()
    assert main(["kb", "search", str(kb), "--query", "专利说明书", "--topic", "patent", "--kind", "rule"]) == 0
    assert read_json(kb / "source-manifest.json")["documents"]
    assert '"hits"' in capsys.readouterr().out


def test_patent_split_receipt_and_existing_output_preserved(tmp_path, kb):
    from oh_my_patent.cli import main as patent
    draft, output = tmp_path / "split.md", tmp_path / "split-output"
    assert patent(["template", "invention", "-o", str(draft), "--knowledge", str(kb)]) == 0
    draft.write_bytes((Path(__file__).resolve().parents[1] / "examples/invention-example.md").read_bytes())
    assert patent(["build", str(draft), "-o", str(output), "--split"]) == 0
    assert read_json(Path(str(output) + ".knowledge.json"))["outputs"]
    before = {p: sha256(p) for p in output.rglob("*") if p.is_file()}
    assert patent(["build", str(draft), "-o", str(output), "--split"]) != 0
    assert before == {p: sha256(p) for p in before}
