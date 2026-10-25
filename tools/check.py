"""统一检查入口：把散落的 check_*.py 收成一条命令。

以前 CI 里逐个调用 ``tools/check_skills.py``、``check_word_skills.py``、
``check_rule_sources.py``…，名字相近、参数各异、失败信息格式不统一。这个入口只做三件事：

1. 按组（group）加载现有检查脚本，**不重写检查逻辑**；
2. 依序执行、汇总退出码，并打印统一的结果行；
3. 支持 ``--list`` 与 ``--json``，便于本地和 CI 共用。

原有脚本继续可用（它们仍是各自检查的唯一实现）；这里只是编排层。

用法::

    python tools/check.py --list
    python tools/check.py --group skills --group rules
    python tools/check.py --all
    python tools/check.py --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

# 轻量、无参数、任何时候都能跑：--all 默认只跑这两组
GROUPS: dict[str, list[tuple[str, list[str]]]] = {
    "skills": [
        ("check_skills.py", []),
        ("check_word_skills.py", []),
    ],
    "rules": [("check_rule_sources.py", [])],
}

# 需要本机上下文或产物参数的检查：必须显式 --group 调用，--all 不会带上，
# 避免在没有 .agent 清单、没有索引或没有预览工具时制造假失败。
OPTIONAL: dict[str, list[tuple[str, list[str]]]] = {
    "manifest": [("check_code_manifest.py", [])],
    "env": [("check_delivery_environment.py", [])],
    "knowledge": [("check_knowledge_pack.py", [])],
    "deps": [("check_full_dependencies.py", [])],
    "delivery": [("check_installed_delivery.py", ["--out", "outputs/acceptance/installed-smoke"])],
}

ALL_GROUPS = list(GROUPS) + list(OPTIONAL)


def _load(filename: str):
    path = TOOLS / filename
    if not path.exists():
        raise SystemExit(f"缺少检查脚本：{path}")
    module_name = f"checks_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_failure(name: str) -> int:
    """只在测试里替换：模拟某个检查失败。"""
    print(f"FAIL {name}：模拟失败")
    return 1


def run(groups: list[str], only: str | None = None) -> dict:
    results = []
    for group in groups:
        entries = GROUPS.get(group) or OPTIONAL.get(group) or []
        if not entries:
            results.append({"group": group, "script": None, "code": 2, "skipped": "unknown group"})
            continue
        for filename, argv in entries:
            if only and only not in filename:
                continue
            print(f"── {group}: {filename}")
            try:
                module = _load(filename)
                code = int(module.main(argv))
            except SystemExit as exc:
                code = int(exc.code) if isinstance(exc.code, int) else 1
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR {filename}: {type(exc).__name__}: {exc}")
                code = 1
            results.append({"group": group, "script": filename, "code": code})
            print(("PASS " if code == 0 else "FAIL ") + f"{filename} (exit {code})")
    return {"results": results, "ok": all(r["code"] == 0 for r in results)}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="统一运行 tools/check_*.py")
    parser.add_argument("--group", action="append", choices=ALL_GROUPS, help="只跑某组，可重复")
    parser.add_argument("--all", action="store_true", help="跑轻量组（skills + rules）；重型组需显式 --group")
    parser.add_argument("--list", action="store_true", help="列出组与脚本后退出")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    parser.add_argument("--only", help="只跑文件名包含该子串的检查（调试用）")
    args = parser.parse_args(argv)

    if args.list:
        for group in ALL_GROUPS:
            entries = GROUPS.get(group) or OPTIONAL.get(group) or []
            scripts = ", ".join(name for name, _ in entries)
            print(f"{group:10s} {scripts}")
        return 0

    groups = args.group or (list(GROUPS) if args.all else [])
    if not groups:
        parser.error("指定 --group 或 --all（或 --list 查看）")

    print(f"检查组：{', '.join(groups)}")
    outcome = run(groups, only=args.only)
    if args.json:
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
    else:
        passed = sum(1 for r in outcome["results"] if r["code"] == 0)
        print(f"\n结果：{passed}/{len(outcome['results'])} 通过")
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
