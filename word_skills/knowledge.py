"""Deterministic, local-only retrieval over a frozen knowledge pack.

Search results locate source text; they are not a claim that the text supports
any particular proposition. Packs provide integrity checks, not signatures.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path, PurePosixPath

_INDEX_CONFIG = {"algorithm": "bm25-v1", "k1": 1.5, "b": 0.75,
                 "chunk_chars": 1500, "overlap_lines": 2,
                 "tokenizer": "ascii-identifiers+han-bigrams-v1"}
_KINDS = {"rule", "reference", "project"}
_TOPICS = {"copyright", "patent"}


def _json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON file {path}: {exc}") from exc


def _canonical_relative(relative):
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or relative.startswith("/") or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError(f"Expected a relative file path: {relative!r}")
    posix = PurePosixPath(relative)
    if posix.is_absolute() or posix.as_posix() != relative:
        raise ValueError(f"Noncanonical relative file path: {relative!r}")
    return posix


def _safe_file(root, relative):
    posix = _canonical_relative(relative)
    p = (root / Path(*posix.parts)).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes source tree: {relative}") from exc
    if not p.is_file():
        raise ValueError(f"Source file does not exist: {relative}")
    return p


def _chunk(text):
    """Line-preserving chunks; an indivisible long line remains intact."""
    lines = text.splitlines(keepends=True)
    if not lines and text == "":
        return []
    rows, start = [], 0
    limit = _INDEX_CONFIG["chunk_chars"]
    while start < len(lines):
        if len(lines[start]) > limit:
            rows.append({"text": lines[start], "line_start": start + 1, "line_end": start + 1,
                         "oversized_line": True})
            start += 1
            continue
        end, size = start, 0
        while end < len(lines) and len(lines[end]) <= limit and size + len(lines[end]) <= limit:
            size += len(lines[end])
            end += 1
        val = "".join(lines[start:end])
        rows.append({"text": val, "line_start": start + 1, "line_end": end,
                     "oversized_line": False})
        if end == len(lines):
            break
        overlap, overlap_size = 0, 0
        allow_overlap = end < len(lines) and len(lines[end]) <= limit
        while allow_overlap and overlap < _INDEX_CONFIG["overlap_lines"] and end - overlap - 1 > start:
            candidate = lines[end - overlap - 1]
            if len(candidate) > limit or overlap_size + len(candidate) + (len(lines[end]) if len(lines[end]) <= limit else 0) > limit:
                break
            overlap_size += len(candidate)
            overlap += 1
        start = end - overlap
    return rows


def _tokens(text):
    out = re.findall(r"[a-z0-9_]+", text.lower())
    han = "".join(re.findall(r"[\u3400-\u9fff]", text))
    out.extend(han[i:i+2] for i in range(max(0, len(han)-1)))
    if len(han) == 1:
        out.append(han)
    return out


def _validate_pack(manifest):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported source manifest schema")
    docs = manifest.get("documents")
    if not isinstance(docs, list):
        raise ValueError("source manifest documents must be a list")
    seen = set()
    for d in docs:
        if not isinstance(d, dict):
            raise ValueError("Each document must be an object")
        ident = d.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", ident) or ident in seen:
            raise ValueError(f"Invalid or duplicate document id: {ident!r}")
        seen.add(ident)
        if d.get("kind") not in _KINDS or not isinstance(d.get("topics"), list) or not d["topics"] or any(x not in _TOPICS for x in d["topics"]):
            raise ValueError(f"Invalid kind/topics for document {ident}")
        if not isinstance(d.get("title"), str) or not isinstance(d.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", d["sha256"]):
            raise ValueError(f"Invalid title or SHA-256 for document {ident}")
        if (not isinstance(d.get("url"), str) or not isinstance(d.get("revision"), str)
                or not isinstance(d.get("retrieved_at"), str)):
            raise ValueError(f"Invalid url/revision/retrieved_at for document {ident}")
        if "license" in d:
            lic = d["license"]
            if (not isinstance(lic, dict) or not isinstance(lic.get("path"), str)
                    or ("spdx" in lic and not isinstance(lic["spdx"], str))
                    or ("url" in lic and not isinstance(lic["url"], str))):
                raise ValueError(f"Invalid license object for {ident}")
    return docs


def build_index(source_manifest, outputDIR):
    """Build a new immutable-by-convention pack at a fresh destination."""
    source_manifest = Path(source_manifest).resolve()
    source_root = source_manifest.parent
    dest = Path(outputDIR).resolve()
    if dest.exists():
        raise FileExistsError(f"Output already exists: {dest}")
    try:
        dest.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("Output directory must be outside the source tree")
    raw_manifest = source_manifest.read_bytes()
    source = json.loads(raw_manifest.decode("utf-8"))
    documents = _validate_pack(source)
    copied = []
    file_blobs = []
    for d in documents:
        path = _safe_file(source_root, d.get("path"))
        data = path.read_bytes()
        if _hash(data) != d["sha256"]:
            raise ValueError(f"SHA-256 mismatch for document {d['id']}")
        text = data.decode("utf-8")
        suffix = path.suffix.lower() or ".txt"
        snap_rel = f"sources/{d['id']}/original{suffix}"
        item = dict(d, snapshot_path=snap_rel)
        if "license" in d:
            lic = d["license"]
            if not isinstance(lic, dict):
                raise ValueError(f"Invalid license object for {d['id']}")
            lic_path = _safe_file(source_root, lic.get("path"))
            lic_data = lic_path.read_bytes()
            lic_rel = f"sources/{d['id']}/license{lic_path.suffix.lower() or '.txt'}"
            item["license"] = dict(lic, snapshot_path=lic_rel, sha256=_hash(lic_data))
            file_blobs.append((lic_rel, lic_data))
        file_blobs.append((snap_rel, data))
        item["path"] = d["path"]
        item["sha256"] = _hash(data)
        item["_text"] = text
        copied.append(item)
    chunks = []
    for d in copied:
        if not isinstance(d, dict):
            continue
        for n, ch in enumerate(_chunk(d.pop("_text")), 1):
            chunks.append({"chunk_id": f"{d['id']}:{n:05d}", "source_id": d["id"], **ch,
                           "source_sha256": d["sha256"], "url": d["url"], "kind": d["kind"],
                           "topics": d["topics"], "revision": d["revision"]})
    # Preserve source-provided additional fields as metadata, excluding path/hash internals.
    source_copy = dict(source)
    source_copy["documents"] = [{k: v for k, v in d.items() if k != "_text"} for d in copied if isinstance(d, dict)]
    try:
        dest.mkdir(parents=True)
        for rel, data in file_blobs:
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        index_data = _json_bytes(chunks)
        (dest / "chunks.json").write_bytes(index_data)
        source_manifest_data = _json_bytes(source_copy)
        (dest / "source-manifest.json").write_bytes(source_manifest_data)
        snapshots = {rel: _hash(data) for rel, data in file_blobs}
        identity_basis = {"source_manifest_sha256": _hash(raw_manifest),
                          "source_manifest_snapshot_sha256": _hash(source_manifest_data), "snapshots": snapshots,
                          "chunks_sha256": _hash(index_data), "index_config": _INDEX_CONFIG}
        kb_id = _hash(_json_bytes(identity_basis))
        km = {"schema_version": 1, "kb_id": kb_id, **identity_basis}
        (dest / "kb-manifest.json").write_bytes(_json_bytes(km))
    except Exception:
        # Retain failed output for diagnosis; absence of kb-manifest.json marks it incomplete.
        raise
    return verify_index(dest)


def verify_index(kbDIR):
    root = Path(kbDIR).resolve()
    km = _read_json(root / "kb-manifest.json")
    if not isinstance(km, dict) or km.get("schema_version") != 1 or km.get("index_config") != _INDEX_CONFIG:
        raise ValueError("Invalid KB manifest/configuration")
    expected_keys = {"schema_version", "kb_id", "source_manifest_sha256", "source_manifest_snapshot_sha256",
                     "snapshots", "chunks_sha256", "index_config"}
    if set(km) != expected_keys:
        raise ValueError("Invalid KB manifest shape")
    basis = {k: km[k] for k in ("source_manifest_sha256", "source_manifest_snapshot_sha256", "snapshots", "chunks_sha256", "index_config")}
    if km.get("kb_id") != _hash(_json_bytes(basis)):
        raise ValueError("KB identity mismatch")
    sm_path, ch_path = root / "source-manifest.json", root / "chunks.json"
    if not sm_path.is_file() or _hash(sm_path.read_bytes()) != km["source_manifest_snapshot_sha256"]:
        raise ValueError("Source manifest snapshot hash mismatch")
    if not ch_path.is_file() or _hash(ch_path.read_bytes()) != km["chunks_sha256"]:
        raise ValueError("Chunk index hash mismatch")
    snapshot_registry = km.get("snapshots")
    if not isinstance(snapshot_registry, dict):
        raise ValueError("Invalid snapshot registry")
    for rel, digest in snapshot_registry.items():
        _safe_file(root, rel)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid snapshot hash: {rel}")
        p = _safe_file(root, rel)
        if _hash(p.read_bytes()) != digest:
            raise ValueError(f"Snapshot hash mismatch: {rel}")
    source = _read_json(sm_path)
    docs = _validate_pack(source)
    chunks = _read_json(ch_path)
    if not isinstance(chunks, list):
        raise ValueError("Invalid chunk index")
    verified_docs = []
    expected_registry = {}
    source_texts = {}
    for d in docs:
        snapshot = d.get("snapshot_path")
        if not isinstance(snapshot, str):
            raise ValueError(f"Missing document snapshot for {d['id']}")
        source_path = _canonical_relative(d.get("path"))
        expected_doc_path = f"sources/{d['id']}/original{Path(source_path.name).suffix.lower() or '.txt'}"
        if snapshot != expected_doc_path:
            raise ValueError(f"Unexpected document snapshot path for {d['id']}")
        snap_path = _safe_file(root, snapshot)
        doc_bytes = snap_path.read_bytes()
        doc_sha = _hash(doc_bytes)
        if doc_sha != d["sha256"]:
            raise ValueError(f"Document snapshot hash mismatch: {d['id']}")
        expected_registry[snapshot] = doc_sha
        source_texts[d["id"]] = doc_bytes.decode("utf-8")
        license_data = d.get("license")
        if license_data is not None:
            license_snapshot = license_data.get("snapshot_path")
            if not isinstance(license_snapshot, str):
                raise ValueError(f"Missing license snapshot for {d['id']}")
            license_source_path = _canonical_relative(license_data.get("path"))
            expected_license_path = f"sources/{d['id']}/license{Path(license_source_path.name).suffix.lower() or '.txt'}"
            if license_snapshot != expected_license_path:
                raise ValueError(f"Unexpected license snapshot path for {d['id']}")
            lp = _safe_file(root, license_snapshot)
            license_sha = _hash(lp.read_bytes())
            if license_sha != license_data.get("sha256"):
                raise ValueError(f"License snapshot hash mismatch: {d['id']}")
            expected_registry[license_snapshot] = license_sha
        core = {"id", "title", "path", "snapshot_path", "sha256", "url", "kind", "topics", "revision", "retrieved_at", "effective_from", "rights_note", "license"}
        verified_docs.append({"id": d["id"], "title": d["title"], "snapshot": snapshot,
                              "sha256": d["sha256"], "source_sha256": d["sha256"],
                              "kind": d["kind"], "topics": d["topics"], "revision": d["revision"],
                              "url": d["url"], "retrieved_at": d.get("retrieved_at"),
                              "effective_from": d.get("effective_from"), "rights_note": d.get("rights_note"),
                              "metadata": {k: v for k, v in d.items() if k not in core}})
    if snapshot_registry != expected_registry:
        raise ValueError("Snapshot registry does not match documents and licenses")
    by_id = {d["id"]: d for d in verified_docs}
    expected_chunks = []
    for d in verified_docs:
        for n, ch in enumerate(_chunk(source_texts[d["id"]]), 1):
            expected_chunks.append({"chunk_id": f"{d['id']}:{n:05d}", "source_id": d["id"], **ch,
                                    "source_sha256": d["sha256"], "url": d["url"], "kind": d["kind"],
                                    "topics": d["topics"], "revision": d["revision"]})
    if chunks != expected_chunks:
        raise ValueError("Chunk index does not match source snapshots and metadata")
    return {"kb_id": km["kb_id"], "manifest": km, "documents": verified_docs, "chunks": chunks}


def search(kbDIR, query, top_k=5, *, kind=None, topic=None):
    """Search verified pack with deterministic BM25; zero-score hits are omitted."""
    verified = verify_index(kbDIR)
    if not isinstance(query, str) or isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("query must be text and top_k must be a positive integer")
    if kind is not None and kind not in _KINDS:
        raise ValueError(f"Unknown kind: {kind}")
    if topic is not None and topic not in _TOPICS:
        raise ValueError(f"Unknown topic: {topic}")
    journal_path = Path(kbDIR) / "ragflow-import-journal.json"
    if journal_path.exists():
        try:
            journal = _read_json(journal_path)
        except ValueError as exc:
            raise ValueError("Incomplete RAGFlow import journal; retrieval is disabled") from exc
        if not isinstance(journal, dict) or journal.get("state") != "complete" or not (Path(kbDIR) / "ragflow.json").is_file():
            raise ValueError("Incomplete RAGFlow import; retrieval is disabled")
    if (Path(kbDIR) / "ragflow.json").exists():
        from .ragflow import search as ragflow_search
        return ragflow_search(kbDIR, verified, query, top_k, kind=kind, topic=topic)
    chunks = [c for c in verified["chunks"] if (kind is None or c["kind"] == kind) and (topic is None or topic in c["topics"])]
    q = Counter(_tokens(query))
    tokens = [_tokens(c["text"]) for c in chunks]
    N = len(chunks)
    avgdl = sum(map(len, tokens)) / N if N else 0
    df = Counter(t for row in tokens for t in set(row))
    scored = []
    for c, row in zip(chunks, tokens):
        tf = Counter(row); dl = len(row); score = 0.0
        for term, qf in q.items():
            if tf[term]:
                idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * tf[term] * 2.5 / (tf[term] + 1.5 * (1 - 0.75 + 0.75 * dl / avgdl)) * qf
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))
    hits = []
    for score, c in scored[:top_k]:
        d = next(d for d in verified["documents"] if d["id"] == c["source_id"])
        hits.append({k: c[k] for k in ("source_id", "chunk_id", "text", "line_start", "line_end", "url", "kind", "topics", "revision", "source_sha256")}
                    | {"title": d["title"], "retrieved_at": d["retrieved_at"],
                       "effective_from": d["effective_from"], "rights_note": d["rights_note"],
                       "metadata": d["metadata"], "score": score})
    return {"state": "hits" if hits else "no_hits", "kb_id": verified["kb_id"],
            "manifest_sha256": _hash((Path(kbDIR) / "kb-manifest.json").read_bytes()),
            "query": query, "filters": {"kind": kind, "topic": topic}, "hits": hits}
