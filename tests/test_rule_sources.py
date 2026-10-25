"""``tools/check_rule_sources.py`` 的规则出处检查。

约定：版面数字只在 ``skills/oh-my-patent/references/cnipa-2026.md`` 与
``docs/format-spec.md`` 里维护，其它文件必须链接而不是复述。
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("check_rule_sources", ROOT / "tools/check_rule_sources.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = _load()


class RuleSourceTests(unittest.TestCase):
    def _make_repo(self, base: Path, extra_prompt: str, link: bool) -> Path:
        canonical = base / "skills/oh-my-patent/references/cnipa-2026.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text(
            "# 规则\n\n## 版面硬规则\n\n| 行距 | 2.5~3.5mm |\n",
            encoding="utf-8",
        )
        implementation = base / "docs/format-spec.md"
        implementation.parent.mkdir(parents=True)
        implementation.write_text("# 实现\n\n字高 3.5~4.5mm。\n", encoding="utf-8")
        prompt = base / "skills/oh-my-patent/prompts/06.md"
        prompt.parent.mkdir(parents=True)
        body = extra_prompt
        if link:
            body += "\n判据见 [版面硬规则](../references/cnipa-2026.md#版面硬规则)。\n"
        prompt.write_text(body, encoding="utf-8")
        return base

    def test_number_without_link_fails(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp), "行距 2.5~3.5mm 就对了。", link=False)
            result = checker.check(root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["violations"][0]["file"], "skills/oh-my-patent/prompts/06.md")
            self.assertIn("2.5~3.5mm", result["violations"][0]["tokens"])

    def test_number_with_link_passes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_repo(Path(tmp), "行距 2.5~3.5mm 就对了。", link=True)
            result = checker.check(root)
            self.assertTrue(result["ok"], result["violations"])

    def test_missing_canonical_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            result = checker.check(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any("唯一事实源缺失" in item["fix"] for item in result["violations"]))

    def test_real_repo_has_no_orphan_numbers(self):
        result = checker.check(ROOT)
        self.assertTrue(result["ok"], result["violations"])
        self.assertGreater(result["checked"], 50)


if __name__ == "__main__":
    unittest.main()
