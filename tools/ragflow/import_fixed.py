#!/usr/bin/env python3
"""Upload a verified local frozen KB and its exact chunks to loopback RAGFlow."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from word_skills.knowledge import verify_index  # noqa: E402


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


class Client:
    def __init__(self, base_url, key):
        parts = urlsplit(base_url)
        try:
            loopback = parts.hostname == "localhost" or ipaddress.ip_address(parts.hostname).is_loopback
        except ValueError:
            loopback = False
        if parts.scheme != "http" or not loopback or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("RAGFlow URL must be loopback HTTP")
        self.base = base_url.rstrip("/") + "/api/v1"
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def request(self, method, path, payload=None, *, content_type="application/json", timeout=25):
        data = payload
        if content_type == "application/json" and payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Authorization": f"Bearer {self.key}",
                                              "Content-Type": content_type}, method=method)
        try:
            with self.opener.open(req, timeout=min(timeout, 30)) as response:
                body = response.read(16_000_000)
        except Exception as exc:
            raise ValueError(f"RAGFlow request failed ({type(exc).__name__})") from None
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("RAGFlow returned invalid JSON") from None
        if not isinstance(result, dict) or result.get("code") != 0:
            code = result.get("code") if isinstance(result, dict) else None
            message = result.get("message", "") if isinstance(result, dict) else ""
            message = str(message).replace(self.key, "[redacted]")[:300]
            raise ValueError(f"RAGFlow returned an unsuccessful response (code={code!r}, message={message!r})")
        return result.get("data")

    def upload(self, path, filename, content):
        boundary = "----word-skills-" + uuid.uuid4().hex
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.request("POST", path, data, content_type=f"multipart/form-data; boundary={boundary}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def import_fixed(index, url, embedding_model, name, out):
    index, out = Path(index).resolve(), Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"Output already exists: {out}")
    if out == index or index in out.parents:
        raise ValueError("Output must not be inside the input index")
    verified = verify_index(index)
    key = os.environ.get("WORD_SKILLS_RAGFLOW_API_KEY")
    if not key:
        raise ValueError("Set WORD_SKILLS_RAGFLOW_API_KEY in the environment")
    client = Client(url, key)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(index, out)
    (out / "ragflow.json").unlink(missing_ok=True)
    journal_path = out / "ragflow-import-journal.json"
    journal = {"schema_version": 1, "kb_id": verified["kb_id"], "dataset_id": None,
               "document_ids": {}, "chunk_ids": {}}

    def checkpoint():
        journal_path.write_bytes(_json_bytes(journal))

    checkpoint()
    result = client.request("POST", "/datasets", {"name": name, "language": "Chinese",
                              "embedding_model": embedding_model, "parse_type": 1, "parser_id": "general"})
    if not isinstance(result, dict) or not isinstance(result.get("id"), str):
        raise ValueError("RAGFlow dataset response has no ID")
    dataset_id = result["id"]
    journal["dataset_id"] = dataset_id
    checkpoint()

    documents = {}
    for doc in verified["documents"]:
        snapshot = index / doc["snapshot"]
        suffix = snapshot.suffix or ".txt"
        filename = doc["id"] + suffix
        uploaded = client.upload(f"/datasets/{dataset_id}/documents", filename, snapshot.read_bytes())
        if not isinstance(uploaded, list) or len(uploaded) != 1 or not isinstance(uploaded[0], dict) or not isinstance(uploaded[0].get("id"), str):
            raise ValueError(f"RAGFlow upload response is invalid for source {doc['id']}")
        documents[doc["id"]] = uploaded[0]["id"]
        journal["document_ids"] = dict(documents)
        checkpoint()

    for chunk in verified["chunks"]:
        document_id = documents[chunk["source_id"]]
        created = client.request("POST", f"/datasets/{dataset_id}/documents/{document_id}/chunks", {"content": chunk["text"]})
        if not isinstance(created, dict) or not isinstance(created.get("chunk"), dict) or not isinstance(created["chunk"].get("id"), str):
            raise ValueError(f"RAGFlow chunk response is invalid for {chunk['chunk_id']}")
        journal["chunk_ids"][created["chunk"]["id"]] = chunk["chunk_id"]
        checkpoint()

    expected_chunk_ids = {chunk["chunk_id"] for chunk in verified["chunks"]}
    if (set(documents) != {doc["id"] for doc in verified["documents"]}
            or len(set(documents.values())) != len(documents)
            or set(journal["chunk_ids"].values()) != expected_chunk_ids
            or len(set(journal["chunk_ids"].values())) != len(journal["chunk_ids"])):
        raise ValueError("RAGFlow import mappings do not match the verified frozen KB")
    config = {"schema_version": 1, "kb_id": verified["kb_id"], "base_url": url.rstrip("/"),
              "dataset_id": dataset_id, "document_ids": documents, "chunk_ids": journal["chunk_ids"]}
    (out / "ragflow.json").write_bytes(_json_bytes(config))
    journal["state"] = "complete"
    checkpoint()
    return dataset_id, len(documents), len(journal["chunk_ids"]), out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, help="verified frozen knowledge pack")
    parser.add_argument("--url", required=True, help="loopback RAGFlow base URL, e.g. http://127.0.0.1:9380")
    parser.add_argument("--embedding-model", required=True, help="configured model ID, e.g. bge-m3@Ollama")
    parser.add_argument("--name", required=True, help="unique new dataset name")
    parser.add_argument("--out", required=True, help="fresh output folder for copied pack/config")
    args = parser.parse_args(argv)
    try:
        dataset_id, docs, chunks, out = import_fixed(args.index, args.url, args.embedding_model, args.name, args.out)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print(f"Imported dataset {dataset_id}: {docs} documents, {chunks} fixed chunks; pack: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
