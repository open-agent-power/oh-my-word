import hashlib
import json
from pathlib import Path

import pytest

from word_skills.knowledge import build_index, search, verify_index


def _pack(tmp_path, docs):
    root = tmp_path / "src"
    root.mkdir()
    entries = []
    for doc_id, text, kind, topics in docs:
        p = root / f"{doc_id}.md"
        p.write_text(text, encoding="utf-8")
        entries.append({"id": doc_id, "title": doc_id, "path": p.name,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "url": f"https://example.test/{doc_id}", "kind": kind,
                        "topics": topics, "revision": "2026-10", "retrieved_at": "2026-10-21"})
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "name": "test", "domain": "drafting",
                                    "documents": entries}, ensure_ascii=False), encoding="utf-8")
    return manifest, root


def test_chinese_search_metadata_and_no_hit(tmp_path):
    manifest, _ = _pack(tmp_path, [
        ("rule", "软件著作权登记应提交源程序鉴别材料。\n专利说明书应当充分公开。\n", "rule", ["copyright", "patent"]),
        ("project", "项目使用 Python 实现图像处理。\n", "project", ["copyright"]),
    ])
    source = json.loads(manifest.read_text(encoding="utf-8"))
    source["documents"][0]["publication_id"] = "CN-example"
    manifest.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    kb = build_index(manifest, tmp_path / "frozen")
    result = search(tmp_path / "frozen", "软件著作权 源程序", topic="copyright")
    assert result["state"] == "hits"
    hit = result["hits"][0]
    assert hit["source_id"] == "rule" and hit["line_start"] == 1
    assert hit["metadata"]["publication_id"] == "CN-example"
    assert hit["source_sha256"] == kb["documents"][0]["sha256"]
    assert search(tmp_path / "frozen", "量子鲸鱼", top_k=3)["state"] == "no_hits"
    assert search(tmp_path / "frozen", "Python", kind="rule")["hits"] == []


def test_deterministic_tie_and_index_identity(tmp_path):
    manifest, _ = _pack(tmp_path, [("b", "专利 创新\n", "reference", ["patent"]),
                                    ("a", "专利 创新\n", "rule", ["patent"])])
    dest = tmp_path / "frozen"
    build_index(manifest, dest)
    first = search(dest, "专利 创新", top_k=2)
    second = search(dest, "专利 创新", top_k=2)
    assert first == second
    assert [h["chunk_id"] for h in first["hits"]] == ["a:00001", "b:00001"]


def test_chunk_lines_overlap_and_oversized_line(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "短行\n" * 430 + "X" * 1600 + "\n尾行\n", "rule", ["patent"])])
    dest = tmp_path / "frozen"
    pack = build_index(manifest, dest)
    chunks = pack["chunks"]
    assert chunks[0]["line_start"] == 1
    assert any(c["oversized_line"] and len(c["text"]) > 1500 for c in chunks)
    assert all(c["text"] for c in chunks)
    original = (dest / pack["documents"][0]["snapshot"]).read_bytes().decode("utf-8").splitlines(keepends=True)
    for c in chunks:
        assert c["text"] == "".join(original[c["line_start"] - 1:c["line_end"]])


def test_adjacent_oversized_lines_are_individual_flagged_chunks(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "A" * 1600 + "\n" + "B" * 1700 + "\n尾\n", "rule", ["patent"])])
    pack = build_index(manifest, tmp_path / "frozen")
    oversized = [c for c in pack["chunks"] if c["oversized_line"]]
    assert len(oversized) == 2
    assert [(c["line_start"], c["line_end"]) for c in oversized] == [(1, 1), (2, 2)]


def test_license_snapshot_and_tamper_detection(tmp_path):
    manifest, root = _pack(tmp_path, [("d", "权利要求\n", "rule", ["patent"])])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    license_file = root / "LICENSE.txt"
    license_file.write_text("允许本地检索", encoding="utf-8")
    data["documents"][0]["license"] = {"path": "LICENSE.txt", "spdx": "CC-BY-4.0"}
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    dest = tmp_path / "frozen"
    pack = build_index(manifest, dest)
    assert any("/license." in p for p in pack["manifest"]["snapshots"])
    (dest / pack["documents"][0]["snapshot"]).write_text("被篡改", encoding="utf-8")
    with pytest.raises(ValueError, match="Snapshot hash mismatch"):
        verify_index(dest)


@pytest.mark.parametrize("path_value", ["../outside.txt", "sub/../../outside.txt", "C:/outside.txt"])
def test_invalid_source_path_and_sha_and_existing_output(tmp_path, path_value):
    manifest, _ = _pack(tmp_path, [("d", "内容", "rule", ["patent"])])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["documents"][0]["path"] = path_value
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        build_index(manifest, tmp_path / "bad")
    data["documents"][0]["path"] = "d.md"
    data["documents"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_index(manifest, tmp_path / "bad")
    with pytest.raises(FileExistsError):
        build_index(manifest, tmp_path / "src")


def test_index_manifest_tamper_rejected(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "规则文本", "rule", ["copyright"])])
    dest = tmp_path / "frozen"
    build_index(manifest, dest)
    index = dest / "chunks.json"
    index.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Chunk index hash mismatch"):
        verify_index(dest)


def test_forged_but_rehashed_chunks_and_snapshot_registry_rejected(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "专利规则\n第二行\n", "rule", ["patent"])])
    dest = tmp_path / "frozen"
    build_index(manifest, dest)
    chunks_path = dest / "chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks.pop()
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    km_path = dest / "kb-manifest.json"
    km = json.loads(km_path.read_text(encoding="utf-8"))
    km["chunks_sha256"] = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    basis = {k: km[k] for k in ("source_manifest_sha256", "source_manifest_snapshot_sha256", "snapshots", "chunks_sha256", "index_config")}
    km["kb_id"] = hashlib.sha256((json.dumps(basis, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()).hexdigest()
    km_path.write_text(json.dumps(km, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Chunk index does not match"):
        verify_index(dest)


def test_canonical_paths_empty_query_and_bool_top_k(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "检索文本\n", "rule", ["patent"])])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["documents"][0]["path"] = "folder/../d.md"
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="relative file path"):
        build_index(manifest, tmp_path / "bad")
    data["documents"][0]["path"] = "d.md"
    data["documents"][0]["retrieved_at"] = "2026-10-01"
    data["documents"][0]["effective_from"] = "2026-09-01"
    data["documents"][0]["rights_note"] = "公开文本"
    manifest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    dest = tmp_path / "frozen"
    pack = build_index(manifest, dest)
    assert pack["documents"][0]["retrieved_at"] == "2026-10-01"
    assert search(dest, "") ["state"] == "no_hits"
    with pytest.raises(ValueError, match="top_k"):
        search(dest, "文本", top_k=True)


def test_chunk_metadata_forgery_rejected_after_rehash(tmp_path):
    manifest, _ = _pack(tmp_path, [("d", "法律条文\n", "rule", ["patent"])])
    dest = tmp_path / "frozen"
    build_index(manifest, dest)
    chunks_path = dest / "chunks.json"
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    chunks[0]["kind"] = "project"
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    km_path = dest / "kb-manifest.json"
    km = json.loads(km_path.read_text(encoding="utf-8"))
    km["chunks_sha256"] = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    basis = {k: km[k] for k in ("source_manifest_sha256", "source_manifest_snapshot_sha256", "snapshots", "chunks_sha256", "index_config")}
    km["kb_id"] = hashlib.sha256((json.dumps(basis, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()).hexdigest()
    km_path.write_text(json.dumps(km, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Chunk index does not match"):
        verify_index(dest)
