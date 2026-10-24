"""Deterministic intent routing for the repository entry point."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .registry import load_registry


_RULES = (
    ("oh-my-patent", ("专利", "权利要求", "实用新型", "外观设计", "发明专利", "交底书", "查新"), None),
    ("oh-my-proposal", ("项目申报", "申报书", "可研", "预算说明", "指南"), None),
    ("oh-my-copyright", ("软著", "软件著作权", "著作权申请", "源码材料"), None),
    ("word-document", ("word", "docx", "排版", "页眉", "页脚", "页码", "模板样式", "版面"), "docx-layout"),
    ("oh-my-technology", ("技术报告", "设计说明", "需求说明", "需求规格", "接口说明", "接口规范", "测试报告", "用户手册", "运维手册"), None),
)

_TECH_MODE_TERMS = (
    ("design-spec", ("设计说明",)),
    ("requirements-spec", ("需求说明", "需求规格")),
    ("interface-spec", ("接口说明", "接口规范")),
    ("test-report", ("测试报告",)),
    ("user-manual", ("用户手册",)),
    ("operations-manual", ("运维手册",)),
    ("technical-report", ("技术报告",)),
)


def route(request: str, root: str | Path | None = None) -> dict:
    if not isinstance(request, str) or not request.strip():
        raise ValueError("request must be a nonempty string")
    rows = {row["name"]: row for row in load_registry(root)}
    matches: list[dict] = []
    for name, terms, forced_mode in _RULES:
        hits = [term for term in terms if term.lower() in request.lower()]
        if not hits:
            continue
        row = rows[name]
        mode_scope = row.get("mode_scope") or {}
        mode = forced_mode
        if name == "oh-my-technology":
            mode = next((
                candidate for candidate, terms in _TECH_MODE_TERMS
                if any(term in request for term in terms)
            ), None)
        mode_status = "implemented" if mode is None or mode in row["modes"] else "planned"
        matches.append({
            "skill": name,
            "status": row["status"] if row["status"] != "implemented" else mode_status,
            "skill_status": row["status"],
            "mode": mode,
            "mode_scope": mode_scope.get(mode),
            "dependencies": row.get("dependencies", []),
            "optional_dependencies": row.get("optional_dependencies", []),
            "matched_terms": hits,
            "rationale": f"请求包含与 {name} 责任范围相符的词语。",
        })
    if not matches:
        selected = "word-skills"
        needs_clarification = True
        reason = "未能从请求确定业务文档类型；请说明文档目标或只使用 skills list 查看已实现能力。"
    else:
        selected = matches[0]["skill"] if len(matches) == 1 else "word-skills"
        needs_clarification = any(m["status"] != "implemented" for m in matches)
        reason = "请求涉及尚未实现的能力；需明确说明当前支持范围。" if needs_clarification else "已匹配能力；多项匹配时按职责组合。路由未执行写作、工具或验收。"
    return {
        "schema_version": 1,
        "request": request,
        "selected": selected,
        "needs_clarification": needs_clarification,
        "reason": reason,
        "matches": matches,
    }


def list_skills(root: str | Path | None = None) -> list[dict]:
    return [
        {**{key: row[key] for key in ("name", "path", "kind", "status", "modes", "mode_scope") if key in row},
         "dependencies": row.get("dependencies", []),
         "optional_dependencies": row.get("optional_dependencies", [])}
        for row in load_registry(root)
    ]
