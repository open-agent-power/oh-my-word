"""``tools/check_skill_duplication.py``：跨 skill 重复规则文本检查。"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_skill_duplication", ROOT / "tools/check_skill_duplication.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import sys

    sys.modules["check_skill_duplication"] = module
    spec.loader.exec_module(module)
    return module


checker = _load()
SHARED = "说明书不得添加任何形式的段落编号，XML 里的段号由系统按段落自动生成，手写的段号会在转换时被当成正文内容，务必在交付前清掉"


class DuplicationTests(unittest.TestCase):
    def _repo(self, base: Path, a: str, b: str) -> Path:
        for skill, body in (("skill-a", a), ("skill-b", b)):
            path = base / "skills" / skill / "references" / "rules.md"
            path.parent.mkdir(parents=True)
            path.write_text(body, encoding="utf-8")
        return base

    def test_shared_paragraph_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(Path(tmp), f"# A\n\n{SHARED}\n", f"# B\n\n{SHARED}\n")
            found = checker.find_duplicates(root)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["skills"], ["skill-a", "skill-b"])

    def test_unique_text_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(
                Path(tmp),
                "# A\n\n这一条只在 skill-a 里出现，讲的是权利要求单一性判断的边界。\n",
                "# B\n\n这一条只在 skill-b 里出现，讲的是外观设计视图提交的注意事项。\n",
            )
            self.assertEqual(checker.find_duplicates(root), [])

    def test_short_paragraph_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(Path(tmp), "# A\n\n不要编号\n", "# B\n\n不要编号\n")
            self.assertEqual(checker.find_duplicates(root), [])

    def test_default_is_warning_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(Path(tmp), f"# A\n\n{SHARED}\n", f"# B\n\n{SHARED}\n")
            self.assertEqual(checker.main(["--root", str(root)]), 0)
            self.assertEqual(checker.main(["--root", str(root), "--strict"]), 1)

    def test_json_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(Path(tmp), f"# A\n\n{SHARED}\n", f"# B\n\n{SHARED}\n")
            import contextlib
            import io

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                checker.main(["--root", str(root), "--json"])
            payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["count"], 1)
        self.assertIn("sample", payload["duplicates"][0])


if __name__ == "__main__":
    unittest.main()
