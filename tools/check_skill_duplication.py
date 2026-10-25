"""检查同一段规则文本是否被两个 skill 各复制了一份。

架构评估第 5 条：六个 skill 各自维护 references/prompts，容易把同一条规则抄两遍，
之后改一处漏一处。这个检查默认**只告警不阻断**（不同 skill 共用措辞有时是合理的），
加 ``--strict`` 才会以非零退出。

用法::

    python tools/check_skill_duplication.py
    python tools/check_skill_duplication.py --strict
    python tools/check_skill_duplication.py --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_CHARS = 40  # 太短的句子（标题、术语）不算重复


@dataclass
class Block:
    skill: str
    file: str
    line: int
    text: str


def _skills(root: Path) -> list[Path]:
    base = root / "skills"
    return sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []


def _normalize(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # 去掉链接目标
    text = re.sub(r"[`*_>#]", "", text)
    return re.sub(r"\s+", "", text)


def _blocks(path: Path, skill: str) -> list[Block]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    blocks: list[Block] = []
    buffer: list[str] = []
    start = 0
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("---") and not buffer:
            continue
        if not stripped:
            if buffer:
                blocks.append(Block(skill, str(path), start, " ".join(buffer)))
                buffer = []
            continue
        if not buffer:
            start = number
        buffer.append(stripped)
    if buffer:
        blocks.append(Block(skill, str(path), start, " ".join(buffer)))
    return blocks


def find_duplicates(root: Path | None = None, min_chars: int = MIN_CHARS) -> list[dict]:
    root = root or ROOT
    index: dict[str, list[Block]] = {}
    for skill_dir in _skills(root):
        for path in sorted(skill_dir.rglob("*.md")):
            for block in _blocks(path, skill_dir.name):
                normalized = _normalize(block.text)
                if len(normalized) < min_chars:
                    continue
                if normalized.startswith("|"):  # 表格行多为结构噪声
                    continue
                if normalized.count("](") > 2:  # 纯链接列表
                    continue
                key = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
                index.setdefault(key, []).append(block)

    duplicates = []
    for key, blocks in index.items():
        skills = {b.skill for b in blocks}
        if len(skills) < 2:
            continue
        duplicates.append(
            {
                "skills": sorted(skills),
                "chars": len(_normalize(blocks[0].text)),
                "locations": [f"{Path(b.file).relative_to(root).as_posix()}:{b.line}" for b in blocks],
                "sample": blocks[0].text[:80],
                "sha1": key[:12],
            }
        )
    return sorted(duplicates, key=lambda d: (-d["chars"], d["skills"]))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="检查跨 skill 的重复规则文本")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--strict", action="store_true", help="发现重复时以非零退出（默认只告警）")
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS, help="判为重复的最短字符数")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录（测试用）")
    args = parser.parse_args(argv)

    duplicates = find_duplicates(args.root, args.min_chars)
    if args.json:
        print(json.dumps({"duplicates": duplicates, "count": len(duplicates)}, ensure_ascii=False, indent=2))
    elif not duplicates:
        print("PASS 跨 skill 文本：没有发现重复规则段落")
    else:
        print(f"WARN 跨 skill 文本：{len(duplicates)} 段规则被两个以上 skill 复制")
        for item in duplicates:
            print(f"  - {' / '.join(item['skills'])}（{item['chars']} 字）")
            print(f"    {item['locations'][0]} ↔ {item['locations'][1]}")
            print(f"    样例：{item['sample']}…")
        print("  建议：保留一处、另一处改成链接；确属共用措辞可忽略（本检查默认不阻断）")
    return 1 if (duplicates and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
