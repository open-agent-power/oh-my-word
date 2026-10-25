"""检查仓库文本文件是否统一为 LF 行尾。

为什么单独查一件事：``.gitattributes`` 声明了 ``* text=auto eol=lf``，但 Windows 上
用 ``Path.write_text()`` 会按 ``os.linesep`` 把 ``\\n`` 写成 CRLF。CRLF 在 Python 里读出来
会变成 ``\\n``，而按字节算哈希仍是 CRLF——评测夹具（``evals/public_runner``）正好一边读文本
一边算字节哈希，于是「只改了一行」就会让 frozen Skill 哈希对不上。

本检查扫常见文本扩展名，发现 CRLF 即失败；二进制、构建产物和忽略目录跳过。

用法::

    python tools/check_line_endings.py
    python tools/check_line_endings.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".txt", ".cfg", ".ini"}
# 只查评测夹具真正依赖的目录：skills/ registry/ shared/ word_skills/schemas/
# （整个工作区在 Windows 检出时是 CRLF 的，全量查会淹没在历史遗留里）
WATCHED = (Path("skills"), Path("registry"), Path("shared"), Path("word_skills/schemas"))
SKIP_DIRS = {
    ".git", ".venv", "venv", "build", "dist", "outputs", ".agent", "__pycache__",
    "node_modules", ".pytest_cache", "third_party", ".archive", ".workbuddy",
}


def _files(root: Path) -> list[Path]:
    found: list[Path] = []
    for watched in WATCHED:
        base = root / watched
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            found.append(path)
    return sorted(found)


def check(root: Path | None = None) -> dict:
    root = root or ROOT
    offenders = []
    checked = 0
    for path in _files(root):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        checked += 1
        if b"\r\n" in data:
            offenders.append({"file": path.relative_to(root).as_posix(), "crlf_lines": data.count(b"\r\n")})
    return {"checked": checked, "offenders": offenders, "ok": not offenders}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="检查文本文件行尾是否为 LF")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根目录（测试用）")
    args = parser.parse_args(argv)

    result = check(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"PASS 行尾：{result['checked']} 个文本文件全部 LF")
    else:
        print(f"FAIL 行尾：{len(result['offenders'])} 个文件是 CRLF（项目约定 LF）")
        for item in result["offenders"][:20]:
            print(f"  - {item['file']}（{item['crlf_lines']} 行）")
        if len(result["offenders"]) > 20:
            print(f"  …另有 {len(result['offenders']) - 20} 个")
        print("  修法：python 里用 Path.write_bytes(text.encode()) 或 open(newline='\\n')")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
