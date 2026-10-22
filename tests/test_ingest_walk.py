"""Intake must skip dependency trees without visiting them or changing source order."""
import os
from pathlib import Path

import pytest

from word_skills.ingest import ingest


def test_excluded_directories_are_never_visited(tmp_path, monkeypatch):
    source = tmp_path / "source"
    forbidden = []
    for directory in ("node_modules", ".venv", ".git", "nested/outputs"):
        folder = source / directory
        folder.mkdir(parents=True)
        (folder / "dependency.txt").write_text("must not be scanned", encoding="utf-8")
        forbidden.append(folder)
    (source / "main.txt").write_text("actual source", encoding="utf-8")
    original = os.scandir

    def guarded(directory):
        assert not any(Path(directory).is_relative_to(folder) for folder in forbidden)
        return original(directory)

    monkeypatch.setattr(os, "scandir", guarded)
    result = ingest([source], tmp_path / "case")
    assert [Path(s["original_path"]).name for s in result["sources"]] == ["main.txt"]


def test_pruned_intake_preserves_global_path_order_and_deduplication(tmp_path):
    source = tmp_path / "source"
    for name in ("z.txt", "a/z.txt", "a.txt", "a/a.txt"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    case = tmp_path / "case"
    result = ingest([source, source / "a.txt"], case)
    expected = sorted(source.rglob("*.txt"))
    assert [Path(s["original_path"]) for s in result["sources"]] == expected
    assert [s["id"] for s in result["sources"]] == ["S001", "S002", "S003", "S004"]
    for item in result["sources"]:
        assert (case / item["extracted"]).read_text(encoding="utf-8") == Path(item["original_path"]).read_text(encoding="utf-8")


def test_intake_still_excludes_credentials_and_rejects_nested_output(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in (".env", "private.key", "main.txt"):
        (source / name).write_text("fixture", encoding="utf-8")
    result = ingest([source], tmp_path / "case")
    assert [Path(s["original_path"]).name for s in result["sources"]] == ["main.txt"]
    assert {Path(s["path"]).name for s in result["skipped"]} == {".env", "private.key"}
    with pytest.raises(ValueError, match="outside"):
        ingest([source], source / "nested-case")
