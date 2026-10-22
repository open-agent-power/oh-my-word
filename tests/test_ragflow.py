import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from word_skills.knowledge import build_index, search
from test_knowledge import _pack


@pytest.fixture
def setup_kb(tmp_path, monkeypatch):
    manifest, _ = _pack(tmp_path, [("rule", "法律规则专利\n", "rule", ["patent"]),
                                   ("project", "项目经验文本\n", "project", ["copyright"])])
    root = tmp_path / "frozen"
    pack = build_index(manifest, root)
    state = {"payload": None, "response": None, "auth": None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state["auth"] = self.headers.get("Authorization")
            state["payload"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body = json.dumps(state["response"] or {"code": 0, "data": {"chunks": []}}, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    docs = {d["id"]: f"remote-{d['id']}" for d in pack["documents"]}
    chunks = {f"remote-{c['chunk_id']}": c["chunk_id"] for c in pack["chunks"]}
    config = {"schema_version": 1, "kb_id": pack["kb_id"], "base_url": f"http://127.0.0.1:{server.server_port}",
              "dataset_id": "dataset-1", "document_ids": docs, "chunk_ids": chunks}
    (root / "ragflow.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("WORD_SKILLS_RAGFLOW_API_KEY", "test-secret")
    yield root, pack, state, server
    server.shutdown()
    thread.join()


def _response(pack, doc="rule", chunk_index=0, **overrides):
    chunk = next(c for c in pack["chunks"] if c["source_id"] == doc)
    row = {"id": f"remote-{chunk['chunk_id']}", "document_id": f"remote-{doc}", "content": chunk["text"], "similarity": 0.91}
    row.update(overrides)
    return {"code": 0, "data": {"chunks": [row]}}


def test_search_uses_filtered_remote_candidates_and_local_metadata(setup_kb):
    root, pack, state, _ = setup_kb
    state["response"] = _response(pack)
    result = search(root, "专利规则", kind="rule", topic="patent")
    assert result["backend"] == "ragflow" and result["state"] == "hits"
    assert result["hits"][0]["source_id"] == "rule"
    assert result["hits"][0]["text"] == pack["chunks"][0]["text"]
    assert state["payload"]["document_ids"] == ["remote-rule"]
    assert state["payload"]["dataset_ids"] == ["dataset-1"]
    assert state["payload"]["question"] == "专利规则"
    assert state["payload"]["keywords_similarity_weight"] == 0.7
    assert "keyword_similarity_weight" not in state["payload"]
    assert state["payload"]["include_knowledge_compilation"] is False
    assert state["auth"] == "Bearer test-secret"
    assert "test-secret" not in json.dumps(result)


def test_empty_filter_does_not_query_ragflow(setup_kb):
    root, _, state, _ = setup_kb
    result = search(root, "anything", kind="reference")
    assert result["state"] == "no_hits" and state["payload"] is None


@pytest.mark.parametrize("response, message", [
    ({"code": 0, "data": {"chunks": [{"id": "unknown"}]}}, "unknown chunk"),
    (None, "text does not match"),
])
def test_remote_results_must_match_frozen_chunk(setup_kb, response, message):
    root, pack, state, _ = setup_kb
    state["response"] = response if response is not None else _response(pack, content="tampered")
    with pytest.raises(ValueError, match=message):
        search(root, "专利", kind="rule")


def test_remote_document_mismatch_rejected(setup_kb):
    root, pack, state, _ = setup_kb
    state["response"] = _response(pack, document_id="remote-project")
    with pytest.raises(ValueError, match="wrong document"):
        search(root, "专利", kind="rule")


def test_noninjective_mappings_and_nonfinite_values_rejected(setup_kb):
    root, pack, state, _ = setup_kb
    path = root / "ragflow.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["document_ids"]["project"] = cfg["document_ids"]["rule"]
    path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings"):
        search(root, "query")
    cfg["document_ids"]["project"] = "remote-project"
    cfg["vector_similarity_weight"] = float("nan")
    path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="vector_similarity_weight"):
        search(root, "query")
    cfg.pop("vector_similarity_weight")
    path.write_text(json.dumps(cfg), encoding="utf-8")
    row = _response(pack)["data"]["chunks"][0]
    row["similarity"] = float("inf")
    state["response"] = {"code": 0, "data": {"chunks": [row]}}
    with pytest.raises(ValueError, match="invalid similarity"):
        search(root, "query", kind="rule")


def test_kb_binding_and_api_errors_do_not_expose_secret(setup_kb):
    root, _, state, _ = setup_kb
    cfg_path = root / "ragflow.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["kb_id"] = "0" * 64
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="KB binding"):
        search(root, "query")
    cfg["kb_id"] = json.loads((root / "kb-manifest.json").read_text())["kb_id"]
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    state["response"] = {"code": 100, "message": "private token should not leak"}
    with pytest.raises(ValueError, match="unsuccessful response") as exc:
        search(root, "query")
    assert "test-secret" not in str(exc.value) and "private token" not in str(exc.value)


def test_no_config_keeps_local_search(tmp_path):
    manifest, _ = _pack(tmp_path, [("rule", "法律规则专利\n", "rule", ["patent"])])
    root = tmp_path / "frozen"
    build_index(manifest, root)
    result = search(root, "专利规则")
    assert result["state"] == "hits" and "backend" not in result


def test_incomplete_import_journal_disables_bm25_fallback(tmp_path):
    manifest, _ = _pack(tmp_path, [("rule", "法律规则专利\n", "rule", ["patent"])])
    root = tmp_path / "frozen"
    build_index(manifest, root)
    (root / "ragflow-import-journal.json").write_text(
        json.dumps({"schema_version": 1, "state": "uploading"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Incomplete RAGFlow import"):
        search(root, "专利规则")
