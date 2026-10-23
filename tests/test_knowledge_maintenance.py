import hashlib
import json
from datetime import date

import pytest

from tools.check_knowledge_pack import audit
from word_skills.knowledge import build_index


def pack(tmp_path, retrieved_at="2026-10-20"):
    source = tmp_path / "source"
    source.mkdir()
    entries = []
    for ident, text in (("wanted", "源程序鉴别材料需要真实原文。\n"), ("other", "摘要文字需要清楚。\n")):
        path = source / (ident + ".txt")
        path.write_text(text, encoding="utf-8")
        entries.append({"id": ident, "title": ident, "path": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "url": "https://example.test/" + ident,
                        "kind": "rule", "topics": ["copyright"], "revision": "synthetic", "retrieved_at": retrieved_at})
    manifest = source / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "documents": entries}), encoding="utf-8")
    build_index(manifest, tmp_path / "index")
    return tmp_path / "index"


QUERIES = [{"id": "source", "query": "源程序鉴别材料", "expected_sources": ["wanted"]}]


def test_integrity_and_recall_do_not_certify_legal_currency(tmp_path):
    report = audit(pack(tmp_path), as_of=date(2026, 10, 23), queries=QUERIES)
    assert report["status"] == "pass"
    assert report["legal_currency"] == "not verified"
    assert report["semantic_support"] == "not automatically evaluated"


@pytest.mark.parametrize("collected,status", [("2026-01-01", "review-due"), ("2027-01-01", "future-date"), ("unknown", "invalid-date")])
def test_old_future_and_missing_dates_cannot_pass(tmp_path, collected, status):
    report = audit(pack(tmp_path, collected), as_of=date(2026, 10, 23), queries=QUERIES)
    assert report["status"] == "needs-review"
    assert report["sources"][0]["status"] == status


def test_missing_expected_source_is_not_hidden(tmp_path):
    report = audit(pack(tmp_path), as_of=date(2026, 10, 23), queries=[
        {"id": "miss", "query": "摘要文字", "expected_sources": ["wanted"], "top_k": 1}])
    assert report["status"] == "needs-review"
    assert report["queries"][0]["missing_sources"] == ["wanted"]


def test_no_query_suite_cannot_pass_admission(tmp_path):
    report = audit(pack(tmp_path), as_of=date(2026, 10, 23))
    assert report["retrieval_regression"] == "not-executed"
    assert report["status"] == "needs-review"


def test_changed_snapshot_is_rejected(tmp_path):
    index = pack(tmp_path)
    (index / "sources/wanted/original.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        audit(index, as_of=date(2026, 10, 23), queries=QUERIES)


def test_backend_failure_does_not_switch_to_local_search(tmp_path, monkeypatch):
    index = pack(tmp_path)
    def unavailable(*args, **kwargs):
        raise RuntimeError("configured service unavailable")
    monkeypatch.setattr("tools.check_knowledge_pack.search", unavailable)
    report = audit(index, as_of=date(2026, 10, 23), queries=QUERIES)
    assert report["status"] == "needs-review"
    assert report["queries"][0]["error"] == "RuntimeError: configured service unavailable"


def test_retriever_change_during_audit_is_rejected(tmp_path, monkeypatch):
    index = pack(tmp_path)
    from tools import check_knowledge_pack
    original = check_knowledge_pack.search
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        (index / "ragflow.json").write_text("{}", encoding="utf-8")
        return result
    monkeypatch.setattr(check_knowledge_pack, "search", changed)
    with pytest.raises(ValueError, match="configuration changed"):
        audit(index, as_of=date(2026, 10, 23), queries=QUERIES)
