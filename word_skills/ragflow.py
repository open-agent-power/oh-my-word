"""Opt-in RAGFlow retrieval over a locally verified frozen knowledge pack."""
from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def _digest(data):
    return hashlib.sha256(data).hexdigest()


class RagflowClient:
    """Small stdlib client; credentials are read only from the environment."""
    def __init__(self, base_url, api_key, timeout=20):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname not in ("localhost", "127.0.0.1", "::1")
                or parts.username or parts.password or parts.query or parts.fragment):
            raise ValueError("RAGFlow base_url must be a loopback HTTP URL")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = min(max(float(timeout), 1), 30)

    def request(self, path, payload):
        url = self.base_url + path
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                                     method="POST")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(req, timeout=self.timeout) as response:
                body = response.read(8_000_000)
        except Exception as exc:
            # Avoid echoing request headers, URL credentials, or server bodies.
            raise ValueError(f"RAGFlow request failed ({type(exc).__name__})") from None
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("RAGFlow returned invalid JSON") from None
        if not isinstance(result, dict) or result.get("code") != 0 or not isinstance(result.get("data"), dict):
            raise ValueError("RAGFlow returned an unsuccessful response")
        return result["data"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _load_config(root, verified):
    path = Path(root) / "ragflow.json"
    raw = path.read_bytes()
    cfg = json.loads(raw.decode("utf-8"))
    if not isinstance(cfg, dict) or cfg.get("schema_version") != 1 or cfg.get("kb_id") != verified["kb_id"]:
        raise ValueError("Invalid RAGFlow configuration or KB binding")
    required = {"schema_version", "kb_id", "base_url", "dataset_id", "document_ids", "chunk_ids"}
    allowed = required | {"api_key_env", "similarity_threshold", "vector_similarity_weight", "keywords_similarity_weight"}
    if not required <= set(cfg) or set(cfg) - allowed:
        raise ValueError("Invalid RAGFlow configuration fields")
    if not isinstance(cfg["dataset_id"], str) or not cfg["dataset_id"]:
        raise ValueError("Invalid RAGFlow dataset_id")
    if not isinstance(cfg["document_ids"], dict) or not isinstance(cfg["chunk_ids"], dict):
        raise ValueError("Invalid RAGFlow ID mappings")
    local_docs = {d["id"] for d in verified["documents"]}
    local_chunks = {c["chunk_id"] for c in verified["chunks"]}
    if (set(cfg["document_ids"]) != local_docs or any(not isinstance(v, str) or not v for v in cfg["document_ids"].values())
            or len(set(cfg["document_ids"].values())) != len(cfg["document_ids"])
            or set(cfg["chunk_ids"].values()) != local_chunks
            or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in cfg["chunk_ids"].items())
            or len(set(cfg["chunk_ids"].values())) != len(cfg["chunk_ids"])):
        raise ValueError("RAGFlow mappings do not match the verified KB")
    for key, default in (("similarity_threshold", 0.2), ("vector_similarity_weight", 0.3), ("keywords_similarity_weight", 0.7)):
        val = cfg.get(key, default)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not 0 <= val <= 1:
            raise ValueError(f"Invalid RAGFlow {key}")
    env_name = cfg.get("api_key_env", "WORD_SKILLS_RAGFLOW_API_KEY")
    if not isinstance(env_name, str) or not env_name or not os.environ.get(env_name):
        raise ValueError("RAGFlow API key environment variable is not set")
    return cfg, _digest(raw), os.environ[env_name]


def search(kbDIR, verified, query, top_k, *, kind=None, topic=None):
    """Retrieve remote-ranked chunks and validate their identity/text locally."""
    cfg, config_hash, key = _load_config(kbDIR, verified)
    selected = [d for d in verified["documents"] if (kind is None or d["kind"] == kind)
                and (topic is None or topic in d["topics"])]
    remote_docs = [cfg["document_ids"][d["id"]] for d in selected]
    base = {"state": "no_hits", "kb_id": verified["kb_id"],
            "manifest_sha256": _digest((Path(kbDIR) / "kb-manifest.json").read_bytes()),
            "query": query, "filters": {"kind": kind, "topic": topic}, "hits": [],
            "backend": "ragflow", "retrieval": {"config_sha256": config_hash, "dataset_id": cfg["dataset_id"], "remote_document_ids": remote_docs}}
    if not remote_docs:
        return base
    payload = {"dataset_ids": [cfg["dataset_id"]], "document_ids": remote_docs, "question": query,
               "page_size": top_k, "similarity_threshold": cfg.get("similarity_threshold", 0.2),
               "vector_similarity_weight": cfg.get("vector_similarity_weight", 0.3),
               "keywords_similarity_weight": cfg.get("keywords_similarity_weight", 0.7),
               "include_knowledge_compilation": False}
    data = RagflowClient(cfg["base_url"], key).request("/api/v1/retrieval", payload)
    rows = data.get("chunks")
    if not isinstance(rows, list):
        raise ValueError("RAGFlow response has no chunks list")
    chunks = {c["chunk_id"]: c for c in verified["chunks"]}
    docs = {d["id"]: d for d in verified["documents"]}
    hits = []
    for row in rows:
        if not isinstance(row, dict) or row.get("id") not in cfg["chunk_ids"]:
            raise ValueError("RAGFlow returned an unknown chunk")
        local_id = cfg["chunk_ids"][row["id"]]
        chunk = chunks[local_id]
        local_source = chunk["source_id"]
        if (row.get("document_id") != cfg["document_ids"][local_source]
                or local_source not in {d["id"] for d in selected}):
            raise ValueError("RAGFlow returned a chunk for the wrong document")
        content = row.get("content")
        if not isinstance(content, str) or content.replace("\r\n", "\n") != chunk["text"].replace("\r\n", "\n"):
            raise ValueError("RAGFlow chunk text does not match the frozen KB")
        doc = docs[local_source]
        score = row.get("similarity", 0.0)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError("RAGFlow returned an invalid similarity")
        hits.append({k: chunk[k] for k in ("source_id", "chunk_id", "text", "line_start", "line_end", "url", "kind", "topics", "revision", "source_sha256")}
                     | {"title": doc["title"], "retrieved_at": doc["retrieved_at"], "effective_from": doc["effective_from"],
                        "rights_note": doc["rights_note"], "metadata": doc["metadata"], "score": score})
    base["hits"] = hits[:top_k]
    base["state"] = "hits" if base["hits"] else "no_hits"
    return base
