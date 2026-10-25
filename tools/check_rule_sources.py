"""检查“规则数字”只在唯一事实源里出现，其它文件只链接不复述。

背景：版面规则（字高 3.5~4.5mm、行距 2.5~3.5mm、页码下沿距底 15mm、默认行距 1.25 倍…）
一度同时写在 ``docs/format-spec.md``、``docs/cnipa-format-lessons.md``、
``skills/oh-my-patent/references/cnipa-2026.md`` 和 prompts 里，改一处漏一处。
2026-10-25 起约定：

- **唯一事实源**：``skills/oh-my-patent/references/cnipa-2026.md``（规则数字）
- **实现对照**：``docs/format-spec.md``（工具怎么对上这些数字）
- 其它文件（prompts、SKILL.md、README、其它 docs）可以提规则，但**必须链接**上述文件，
  不得只写数字。

这个脚本把约定变成可执行检查，避免下次又分叉。

用法::

    python tools/check_rule_sources.py
    python tools/check_rule_sources.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CANONICAL = Path("skills/oh-my-patent/references/cnipa-2026.md")
IMPLEMENTATION = Path("docs/format-spec.md")
SOURCES = (CANONICAL, IMPLEMENTATION)

# 只挑“一旦出现就应当有出处的规则数字”，不追求覆盖全部量词。
TOKENS = (
    "3.5~4.5mm",
    "2.5~3.5mm",
    "下沿距底 15mm",
    "下沿距纸底 15mm",
    "1.25 倍",
    "4.5mm",
)

LINK_HINTS = ("cnipa-2026.md", "format-spec.md")

SCAN_DIRS = (Path("skills"), Path("docs"))
SCAN_FILES = (Path("README.md"), Path("THIRD_PARTY.md"))


def _files(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory in SCAN_DIRS:
        base = root / directory
        if base.exists():
            found.extend(sorted(base.rglob("*.md")))
    for name in SCAN_FILES:
        path = root / name
        if path.exists():
            found.append(path)
    return found


def check(root: Path | None = None, sources: tuple[Path, ...] = SOURCES) -> dict:
    root = root or ROOT
    canonical = sources[0]
    source_paths = {root / p for p in sources}
    violations: list[dict] = []
    checked = 0

    for path in _files(root):
        if path in source_paths:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        checked += 1
        hits = sorted({token for token in TOKENS if token in text})
        if not hits:
            continue
        if any(hint in text for hint in LINK_HINTS):
            continue
        violations.append(
            {
                "file": path.relative_to(root).as_posix(),
                "tokens": hits,
                "fix": f"链接 {canonical.as_posix()}（或 format-spec.md），不要复述数字",
            }
        )

    canonical_path = root / canonical
    if not canonical_path.exists():
        violations.append({"file": canonical.as_posix(), "tokens": [], "fix": "唯一事实源缺失"})
    elif "版面硬规则" not in canonical_path.read_text(encoding="utf-8"):
        violations.append({"file": canonical.as_posix(), "tokens": [], "fix": "缺少「版面硬规则」小节"})

    return {
        "checked": checked,
        "sources": [p.as_posix() for p in sources],
        "tokens": list(TOKENS),
        "violations": violations,
        "ok": not violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查规则数字是否有唯一出处")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录（测试用）")
    args = parser.parse_args(argv)

    result = check(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"PASS 规则出处：{result['checked']} 个文件，未发现孤立规则数字")
    else:
        print(f"FAIL 规则出处：{len(result['violations'])} 处复述了数字却没有链接唯一事实源")
        for item in result["violations"]:
            tokens = "、".join(item["tokens"])
            print(f"  - {item['file']}" + (f"（命中 {tokens}）" if tokens else "") + f" → {item['fix']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
