"""Run all tests and record interpreter, dependencies, and skipped coverage."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = {
    "python-docx": "docx",
    "PyYAML": "yaml",
    "pdfplumber": "pdfplumber",
    "pypdf": "pypdf",
    "defusedxml": "defusedxml",
    "markitdown": "markitdown",
    "mammoth": "mammoth",
    "markdownify": "markdownify",
    "python-pptx": "pptx",
    "Pillow": "PIL",
    "docxtpl": "docxtpl",
    "docxcompose": "docxcompose",
}


class TestSummary:
    def __init__(self) -> None:
        self.collected = 0
        self.outcomes: dict[str, int] = {}

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        self.collected = session.testscollected
        if reporter is not None:
            self.outcomes = {key: len(value) for key, value in reporter.stats.items()}


def git_output(*args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def dependency_versions() -> dict[str, dict[str, object]]:
    dependencies = {}
    for distribution, module in DEPENDENCIES.items():
        version = None
        try:
            version = importlib.metadata.version(distribution)
            importlib.import_module(module)
            dependencies[distribution] = {"version": version, "importable": True}
        except (importlib.metadata.PackageNotFoundError, ImportError, OSError) as exc:
            dependencies[distribution] = {
                "version": version,
                "importable": False,
                "error": str(exc),
            }
    return dependencies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/acceptance/full-dependencies.json"),
        help="JSON evidence path (relative paths are rooted at the repository)",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output

    dependencies = dependency_versions()
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    summary = TestSummary()
    exit_code = pytest.main(["tests", "evals", "-q"], plugins=[summary])
    tests = {
        "collected": summary.collected,
        "exit_code": int(exit_code),
        "outcomes": summary.outcomes,
    }
    complete = all(item["importable"] for item in dependencies.values())
    passed = (
        complete
        and exit_code == 0
        and not any(summary.outcomes.get(key, 0) for key in ("skipped", "xfailed", "xpassed"))
    )
    git_status = git_output("status", "--porcelain")
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(ROOT),
        "git_head": git_output("rev-parse", "HEAD"),
        "git_dirty": None if git_status is None else bool(git_status),
        "interpreter": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "dependencies": dependencies,
        "tests": tests,
        "status": "pass" if passed else "fail",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
