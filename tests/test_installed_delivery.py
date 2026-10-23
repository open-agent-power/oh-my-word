"""Failure behavior for the installed-wheel acceptance driver."""
import importlib.util
from pathlib import Path
import sys

import pytest


spec = importlib.util.spec_from_file_location("installed_check", Path(__file__).parents[1] / "tools/check_installed_delivery.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def test_checkout_cannot_pass_as_installed_package():
    with pytest.raises(ValueError, match="outside"):
        check.require_outside(check.ROOT / "word_skills/__init__.py")


def test_command_failure_retains_actual_output(tmp_path):
    records = []
    with pytest.raises(RuntimeError, match="Unexpected exit 3"):
        check.command([sys.executable, "-c", "print('fixture failure'); raise SystemExit(3)"], tmp_path, records)
    assert records[0]["exit_code"] == 3
    assert "fixture failure" in records[0]["stdout"]
