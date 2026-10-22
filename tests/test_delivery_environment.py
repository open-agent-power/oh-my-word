import importlib.util
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("delivery_preflight", Path(__file__).parents[1] / "tools/check_delivery_environment.py")
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def test_invalid_explicit_executable_never_falls_back(tmp_path):
    with patch.object(preflight.shutil, "which", return_value="another-tool") as find:
        result = preflight.tool_status(str(tmp_path / "missing.exe"), ("soffice",), "--version")
    assert not result["available"]
    find.assert_not_called()


def test_failed_or_timed_out_version_is_not_ready(tmp_path):
    executable = tmp_path / "tool.exe"
    executable.touch()
    for result in (CompletedProcess([], 1, "", "failed"), TimeoutExpired([], 10)):
        with patch.object(preflight.subprocess, "run", side_effect=result if isinstance(result, Exception) else None,
                          return_value=result):
            assert not preflight.tool_status(str(executable), (), "--version")["available"]


def test_version_on_stderr_is_recorded_without_claiming_client_compatibility(tmp_path):
    executable = tmp_path / "tool.exe"
    executable.touch()
    with patch.object(preflight.subprocess, "run", return_value=CompletedProcess([], 0, "", "tool version 1")):
        result = preflight.tool_status(str(executable), (), "-v")
    assert result["available"] and result["version"] == "tool version 1"
    assert preflight.registered_client("nonexistent-test-client.exe")["compatibility_tested"] is False
