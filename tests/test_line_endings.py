"""``tools/check_line_endings.py``：评测夹具依赖的文本必须是 LF。

Windows 上用 ``Path.write_text`` 会把 ``\\n`` 写成 CRLF；评测一边按文本读、一边按字节哈希，
CRLF 会让 frozen Skill 哈希对不上。这个检查只覆盖夹具真正读取的目录。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("check_line_endings", ROOT / "tools/check_line_endings.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_line_endings"] = module
    spec.loader.exec_module(module)
    return module


checker = _load()


class LineEndingTests(unittest.TestCase):
    def test_lf_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skills" / "a" / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"# a\n\nbody\n")
            result = checker.check(Path(tmp))
        self.assertTrue(result["ok"], result)

    def test_crlf_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "skills" / "a" / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"# a\r\n\r\nbody\r\n")
            result = checker.check(Path(tmp))
        self.assertFalse(result["ok"])
        self.assertEqual(result["offenders"][0]["file"], "skills/a/SKILL.md")
        self.assertEqual(result["offenders"][0]["crlf_lines"], 3)

    def test_crlf_outside_watched_dirs_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "docs" / "old.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"# old\r\n")
            result = checker.check(Path(tmp))
        self.assertTrue(result["ok"], result)

    def test_real_repo_is_lf(self):
        result = checker.check(ROOT)
        self.assertTrue(result["ok"], result["offenders"][:5])


if __name__ == "__main__":
    unittest.main()
