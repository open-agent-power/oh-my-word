"""``tools/check.py`` 统一检查入口。

只验证编排层：分组、退出码汇总、JSON 输出。真正的检查逻辑由各 check_*.py 自己的测试覆盖。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("check_runner", ROOT / "tools/check.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = _load()


class RunnerTests(unittest.TestCase):
    def test_list_shows_groups(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = runner.main(["--list"])
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        for group in ("skills", "rules", "manifest", "delivery"):
            self.assertIn(group, output)

    def test_all_runs_only_light_groups(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            outcome = runner.run(["skills", "rules"])
        self.assertTrue(outcome["ok"], outcome)
        self.assertEqual({item["group"] for item in outcome["results"]}, {"skills", "rules"})

    def test_all_flag_returns_zero(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--all"]), 0)

    def test_failure_is_summarized(self):
        class Failing:
            @staticmethod
            def main(argv=None):
                return 1

        original = runner._load
        runner._load = lambda filename: Failing
        try:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = runner.main(["--group", "rules"])
            self.assertEqual(code, 1)
            self.assertIn("FAIL", buffer.getvalue())
        finally:
            runner._load = original

    def test_unknown_group_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main(["--group", "nope"])

    def test_scripts_accept_argv(self):
        for name in ("check_skills.py", "check_word_skills.py", "check_rule_sources.py", "check_code_manifest.py"):
            spec = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "tools" / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(callable(module.main))
            self.assertIn("argv", module.main.__code__.co_varnames)


if __name__ == "__main__":
    unittest.main()
