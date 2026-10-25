"""Check the monorepo Skill registry and all implemented Skill references."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from word_skills.registry import load_registry  # noqa: E402


def check(root: str | Path) -> tuple[list[str], dict]:
    root = Path(root).resolve()
    errors: list[str] = []
    try:
        rows = load_registry(root)
    except Exception as exc:  # the CLI should report malformed YAML as a finding
        return [f"registry: {exc}"], {"skills": 0, "implemented": 0, "planned": 0, "links": 0}
    links = 0
    docs = []
    for row in rows:
        if row["status"] == "implemented":
            docs.extend((root / row["path"]).parent.rglob("*.md"))
    docs.extend((root / "shared" / "references").rglob("*.md"))
    docs.extend((root / "docs").glob("*.md"))
    docs.append(root / "README.md")
    for path in sorted(set(docs)):
        body = path.read_text(encoding="utf-8")
        body_without_code = re.sub(r"```.*?```", "", body, flags=re.S)
        for target in re.findall(r"\]\(([^\s)]+)\)", body_without_code):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = unquote(target.split("#", 1)[0]).strip("<>")
            links += 1
            if not (path.parent / target).exists():
                errors.append(f"{path.relative_to(root)}: broken link {target}")
    return errors, {
        "skills": len(rows),
        "implemented": sum(row["status"] == "implemented" for row in rows),
        "planned": sum(row["status"] == "planned" for row in rows),
        "links": links,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    errors, counts = check(args.root)
    for error in errors:
        print(f"ERROR: {error}")
    print(("FAIL" if errors else "PASS") + " (structure only; model behavior not executed): " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
