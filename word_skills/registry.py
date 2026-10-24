"""Validate the repository-level Skill registry.

The registry is deliberately small and declarative.  It reports what is
implemented or planned; it never upgrades a planned skill because a path was
created accidentally.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_STATES = {"implemented", "planned", "deprecated"}
_KINDS = {"router", "business", "production"}
_MODE_SCOPES = {"focused", "baseline"}


def registry_path(root: str | Path | None = None) -> Path:
    if root is None:
        root = Path(__file__).resolve().parents[1]
    candidate = Path(root).resolve() / "registry" / "skills.yaml"
    if candidate.is_file():
        return candidate
    # Wheels intentionally contain the Python tooling and its schema data, but
    # do not pretend that all repository Skill prose has been installed.  Keep
    # a packaged registry snapshot so the CLI can still list and route the
    # declared capabilities from outside a source checkout.
    packaged = Path(__file__).resolve().parent / "data" / "skills.yaml"
    if packaged.is_file() and Path(root).resolve() == Path(__file__).resolve().parents[1]:
        return packaged
    return candidate


def load_registry(root: str | Path | None = None) -> list[dict]:
    path = registry_path(root)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("skills registry requires schema_version=1")
    rows = data.get("skills")
    if not isinstance(rows, list) or not rows:
        raise ValueError("skills registry requires a nonempty skills array")
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid skill registry entry")
        name = row.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate skill name: {name!r}")
        names.add(name)
        if row.get("status") not in _STATES:
            raise ValueError(f"{name}: invalid lifecycle status")
        if row.get("kind") not in _KINDS:
            raise ValueError(f"{name}: invalid kind")
        if not isinstance(row.get("modes"), list) or not row["modes"] or any(not isinstance(x, str) for x in row["modes"]):
            raise ValueError(f"{name}: modes must be a nonempty string list")
        scope = row.get("mode_scope")
        if scope is not None and (
            not isinstance(scope, dict)
            or set(scope) != set(row["modes"])
            or any(value not in _MODE_SCOPES for value in scope.values())
        ):
            raise ValueError(f"{name}: mode_scope must classify every mode as focused or baseline")
        for field in ("dependencies", "optional_dependencies"):
            deps = row.get(field, [])
            if not isinstance(deps, list) or any(not isinstance(x, str) for x in deps):
                raise ValueError(f"{name}: {field} must be a string list")
            if name in deps:
                raise ValueError(f"{name}: {field} cannot depend on itself")
            if len(deps) != len(set(deps)):
                raise ValueError(f"{name}: duplicate {field}")
        if set(row.get("dependencies", [])) & set(row.get("optional_dependencies", [])):
            raise ValueError(f"{name}: required and optional dependencies must not overlap")
        evidence = row.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence):
            raise ValueError(f"{name}: evidence must be a string list")
        skill_path = row.get("path")
        if row["status"] == "implemented":
            if not isinstance(skill_path, str) or not skill_path:
                raise ValueError(f"{name}: implemented skills require a path")
            target = (path.parent.parent / skill_path).resolve()
            if not target.is_file():
                # The packaged wheel has registry metadata but deliberately
                # omits the repository's prose Skill bundle.  Source-tree
                # checks remain strict; installed metadata remains routable.
                if path.parent.name != "data":
                    raise ValueError(f"{name}: missing skill file {skill_path}")
                continue
            frontmatter = _frontmatter(target.read_text(encoding="utf-8"))
            if frontmatter.get("name") != name:
                raise ValueError(f"{name}: skill frontmatter/name mismatch")
        elif skill_path is not None:
            raise ValueError(f"{name}: planned skills must not advertise an implementation path")
    known = set(names)
    for row in rows:
        for field in ("dependencies", "optional_dependencies"):
            for dep in row.get(field, []):
                if dep not in known:
                    raise ValueError(f"{row['name']}: unknown {field} dependency {dep}")
    return rows


def _frontmatter(text: str) -> dict:
    match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.S)
    if not match:
        raise ValueError("missing skill frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("skill frontmatter must be a mapping")
    return data


def skill_by_name(name: str, root: str | Path | None = None) -> dict:
    for row in load_registry(root):
        if row["name"] == name:
            return row
    raise KeyError(f"unknown skill: {name}")
