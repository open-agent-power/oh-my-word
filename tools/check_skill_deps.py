"""检查每个 skill 声明的跨 skill 依赖：存在、无环、与正文链接一致。

背景：六个业务 skill 共用 ``word-document`` 的排版能力与 ``word_skills`` 的转换实现，
但依赖关系原先只藏在正文链接里——改共享文档时不知道影响谁，也不知道谁在偷偷引用别人。
2026-10-25 起约定：跨 skill 依赖写在 ``SKILL.md`` frontmatter 的 ``depends_on`` 里：

    depends_on: [word-document]

本脚本检查三件事：

1. ``depends_on`` 里的名字必须存在；
2. 依赖图不能成环；
3. 正文里链接到别的 skill 目录（``../<skill>/``）却没声明依赖的，给出告警。

``--reverse`` 输出反向影响面：改某个 skill 时哪些 skill 可能受影响。

用法::

    python tools/check_skill_deps.py
    python tools/check_skill_deps.py --reverse
    python tools/check_skill_deps.py --strict      # 告警也当失败
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER = re.compile(r"^---\s*$(.*?)^---\s*$", re.MULTILINE | re.DOTALL)
DEPENDS = re.compile(r"^depends_on:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
SEE_ALSO = re.compile(r"^see_also:\s*\[([^\]]*)\]\s*$", re.MULTILINE)
NAME = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
CROSS_LINK = re.compile(r"\]\(\.\./([a-z0-9-]+)/")


def skill_dirs(root: Path | None = None) -> dict[str, Path]:
    root = root or ROOT
    base = root / "skills"
    return {p.name: p for p in sorted(base.iterdir()) if p.is_dir()} if base.exists() else {}


def _list_field(pattern: re.Pattern[str], body: str) -> list[str]:
    match = pattern.search(body)
    if not match:
        return []
    return [item.strip().strip("'\"") for item in match.group(1).split(",") if item.strip()]


def declared(skill_md: Path) -> list[str]:
    """硬依赖：必须存在且不能成环。"""
    text = skill_md.read_text(encoding="utf-8")
    match = FRONTMATTER.search(text)
    return _list_field(DEPENDS, match.group(1) if match else "")


def see_also(skill_md: Path) -> list[str]:
    """软引用：互相引用是正常的，不参与成环判断。"""
    text = skill_md.read_text(encoding="utf-8")
    match = FRONTMATTER.search(text)
    return _list_field(SEE_ALSO, match.group(1) if match else "")


def linked_skills(skill_md: Path) -> set[str]:
    text = skill_md.read_text(encoding="utf-8")
    return {name for name in CROSS_LINK.findall(text) if name != skill_md.parent.name}


def build_graph(root: Path | None = None) -> dict[str, list[str]]:
    dirs = skill_dirs(root)
    graph: dict[str, list[str]] = {}
    for name, directory in dirs.items():
        skill_md = directory / "SKILL.md"
        graph[name] = declared(skill_md) if skill_md.exists() else []
    return graph


def build_soft(root: Path | None = None) -> dict[str, list[str]]:
    dirs = skill_dirs(root)
    return {
        name: (see_also(directory / "SKILL.md") if (directory / "SKILL.md").exists() else [])
        for name, directory in dirs.items()
    }


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: list[str] = []
    done: set[str] = set()

    def walk(node: str) -> None:
        if node in done:
            return
        if node in visiting:
            cycle = visiting[visiting.index(node) :] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        visiting.append(node)
        for neighbour in graph.get(node, []):
            walk(neighbour)
        visiting.pop()
        done.add(node)

    for node in graph:
        walk(node)
    return cycles


def check(root: Path | None = None, strict: bool = False) -> dict:
    root = root or ROOT
    dirs = skill_dirs(root)
    graph = build_graph(root)
    soft = build_soft(root)
    errors: list[dict] = []
    warnings: list[dict] = []

    for name, deps in graph.items():
        for dep in deps:
            if dep not in dirs:
                errors.append({"skill": name, "issue": "unknown-dep", "detail": dep})
        for dep in soft.get(name, []):
            if dep not in dirs:
                errors.append({"skill": name, "issue": "unknown-see-also", "detail": dep})
        skill_md = dirs[name] / "SKILL.md"
        if skill_md.exists():
            covered = set(deps) | set(soft.get(name, []))
            for linked in sorted(linked_skills(skill_md) - covered):
                if linked in dirs:
                    warnings.append({"skill": name, "issue": "undeclared-link", "detail": linked})

    for cycle in find_cycles(graph):
        errors.append({"skill": " -> ".join(cycle), "issue": "cycle", "detail": "依赖成环"})

    return {
        "skills": {name: graph[name] for name in graph},
        "see_also": soft,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors and (not warnings or not strict),
    }


def reverse(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {name: [] for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            result.setdefault(dep, []).append(name)
    return {name: sorted(users) for name, users in sorted(result.items()) if users}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="检查 skill 依赖声明、成环与未声明链接")
    parser.add_argument("--strict", action="store_true", help="把「未声明链接」告警也算失败")
    parser.add_argument("--reverse", action="store_true", help="输出反向影响面")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录（测试用）")
    args = parser.parse_args(argv)

    result = check(args.root, args.strict)
    graph = result["skills"]
    if args.reverse:
        result["reverse"] = reverse(graph)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for name, deps in graph.items():
            print(f"  {name:18s} -> {', '.join(deps) or '（无跨 skill 依赖）'}")
        if args.reverse:
            print("\n反向影响面：")
            for name, users in reverse(graph).items():
                print(f"  {name:18s} ← {', '.join(users)}")
        for item in result["errors"]:
            print(f"ERROR {item['skill']}：{item['issue']}（{item['detail']}）")
        for item in result["warnings"]:
            print(f"WARN  {item['skill']}：链接了 {item['detail']} 但未在 depends_on 声明")
        print(("PASS " if result["ok"] else "FAIL ") + f"skill 依赖：{len(graph)} 个 skill")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
