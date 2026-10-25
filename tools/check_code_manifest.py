"""Check or refresh the local source-file SHA256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / ".agent/current-code-manifest.json"


def digest(relative_path: str) -> str:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must stay relative to workspace: {relative_path}")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"missing or outside workspace: {relative_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--refresh", action="store_true", help="rewrite hashes for listed files")
    parser.add_argument("--include", action="append", default=[], help="add a source file when refreshing")
    args = parser.parse_args(argv)
    if args.include and not args.refresh:
        parser.error("--include requires --refresh")

    try:
        manifest = (
            json.loads(args.manifest.read_text(encoding="utf-8"))
            if args.manifest.exists() else {} if args.refresh else None
        )
        if not isinstance(manifest, dict) or not all(
            isinstance(path, str) and isinstance(expected, str)
            for path, expected in manifest.items()
        ):
            raise ValueError("manifest must map file paths to SHA256 strings")
        paths = list(dict.fromkeys([*manifest, *args.include]))
        actual = {path: digest(path) for path in paths}
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.refresh:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"REFRESHED {len(actual)} files: {args.manifest}")
        return 0

    stale = [path for path, current in actual.items() if manifest[path] != current]
    for path in stale:
        print(f"STALE {path}: expected={manifest[path]} actual={actual[path]}")
    print(f"{'FAIL' if stale else 'PASS'}: {len(actual)} files, {len(stale)} stale")
    return int(bool(stale))


if __name__ == "__main__":
    sys.exit(main())
