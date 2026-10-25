"""``tools/check_skill_deps.py``：skill 依赖声明、成环与未声明链接。"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("check_skill_deps", ROOT / "tools/check_skill_deps.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_skill_deps"] = module
    spec.loader.exec_module(module)
    return module


checker = _load()


def _skill(base: Path, name: str, body: str, frontmatter_extra: str = "") -> None:
    path = base / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nname: {name}\n{frontmatter_extra}---\n\n{body}\n", encoding="utf-8")


class DepsTests(unittest.TestCase):
    def test_declared_dependency_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "word-document", "# wd\n")
            _skill(base, "oh-my-patent", "见 [Word](../word-document/SKILL.md)\n", "depends_on: [word-document]\n")
            result = checker.check(base)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["skills"]["oh-my-patent"], ["word-document"])

    def test_unknown_dependency_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "a", "# a\n", "depends_on: [nope]\n")
            result = checker.check(base)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["issue"], "unknown-dep")

    def test_cycle_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "a", "# a\n", "depends_on: [b]\n")
            _skill(base, "b", "# b\n", "depends_on: [a]\n")
            result = checker.check(base)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["issue"] == "cycle" for item in result["errors"]))

    def test_undeclared_link_warns_only_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "word-document", "# wd\n")
            _skill(base, "a", "见 [Word](../word-document/SKILL.md)\n")
            relaxed = checker.check(base)
            strict = checker.check(base, strict=True)
        self.assertTrue(relaxed["ok"])
        self.assertFalse(strict["ok"])
        self.assertEqual(relaxed["warnings"][0]["issue"], "undeclared-link")

    def test_see_also_covers_link_without_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "a", "# a\n", "depends_on: [b]\n")
            _skill(base, "b", "见 [a 的流程](../a/x.md)\n", "see_also: [a]\n")
            result = checker.check(base, strict=True)
        self.assertTrue(result["ok"], result)

    def test_reverse_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _skill(base, "word-document", "# wd\n")
            _skill(base, "a", "# a\n", "depends_on: [word-document]\n")
            _skill(base, "b", "# b\n", "depends_on: [word-document]\n")
            graph = checker.build_graph(base)
        self.assertEqual(checker.reverse(graph)["word-document"], ["a", "b"])

    def test_real_repo_is_clean(self):
        result = checker.check(ROOT, strict=True)
        self.assertTrue(result["ok"], result)
        self.assertIn("word-document", result["skills"]["oh-my-patent"])


if __name__ == "__main__":
    unittest.main()
