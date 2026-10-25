"""Read-only local delivery preflight; no install, downloads or Office activation."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def tool_status(explicit, names, version_arg):
    # An invalid explicitly requested tool must not silently select another tool.
    candidate = explicit or next((p for name in names if (p := shutil.which(name))), None)
    if not candidate:
        return {"available": False, "reason": "not found; provide an executable path"}
    path = Path(candidate).resolve()
    if not path.is_file():
        return {"available": False, "path": str(path), "reason": "not a file"}
    try:
        executable = path
        if sys.platform == "win32" and path.name.lower() == "soffice.exe" and path.with_suffix(".com").is_file():
            executable = path.with_suffix(".com")  # Same installation's console launcher.
        with tempfile.TemporaryDirectory(prefix="word-skills-preflight-") as temp:
            flags = ["-env:UserInstallation=" + Path(temp).as_uri(), "--headless"] if path.stem.lower() == "soffice" else []
            result = subprocess.run([str(executable), *flags, version_arg], capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=10)
        version = (result.stdout + result.stderr).strip()
        return {"available": result.returncode == 0 and bool(version), "path": str(path),
                "version_executable": str(executable),
                "exit_code": result.returncode, "version": version[:500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": str(path), "reason": type(exc).__name__}


def registered_client(name):
    """Presence is diagnostic data, never a compatibility test."""
    found = shutil.which(name)
    if sys.platform == "win32" and not found:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(root, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + name,
                                        0, winreg.KEY_READ | view) as key:
                        value = winreg.QueryValue(key, None).strip('"')
                        if Path(value).is_file():
                            found = value
                except OSError:
                    pass
    return {"detected": bool(found), "path": found, "compatibility_tested": False}


def inspect_environment(soffice=None, pdftoppm=None):
    packages = {}
    for name in ("python-docx", "PyYAML", "pdfplumber", "pypdf", "defusedxml", "markdown-it-py"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    tools = {"soffice": tool_status(soffice, ("soffice", "soffice.exe"), "--version"),
             "pdftoppm": tool_status(pdftoppm, ("pdftoppm", "pdftoppm.exe"), "-v")}
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    return {"python": {"executable": sys.executable, "version": sys.version}, "packages": packages,
            "tools": tools, "ready_for_preview": all(packages.values()) and all(t["available"] for t in tools.values()),
            "clients": {"Word": registered_client("WINWORD.EXE"), "WPS": registered_client("wps.exe")},
            "font_files": {name: (fonts / name).is_file() for name in ("simsun.ttc", "simhei.ttf", "times.ttf")},
            "limits": "Preflight only. Tool or font presence does not prove rendered fidelity or Word/WPS compatibility. Pass --soffice and --pdftoppm explicitly when absent from PATH."}


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soffice")
    parser.add_argument("--pdftoppm")
    args = parser.parse_args(argv)
    result = inspect_environment(args.soffice, args.pdftoppm)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready_for_preview"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
