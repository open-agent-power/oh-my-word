"""渲染层：把 :class:`~oh_my_patent.schema.PatentDraft` 输出成文书。

当前提供两条 .docx 制作路径：

- 本地渲染器（:mod:`.docx`）：专利稿件模型直写 OOXML；
- 上游复用适配（:mod:`.upstream`）：固定上游 handsomestWei 转换器 + 边界版式。

:func:`render_docx_selected` 是 ``build`` 与 ``handoff`` 共用的选择入口：
``auto`` 对发明/实用新型使用固定上游、对外观设计使用本地；显式 ``local`` /
``upstream`` 覆盖自动选择。两条路径与模型之间只通过
:class:`~oh_my_patent.schema.PatentDraft` 交互。
"""

from ..schema import PatentType
from .docx import DocxRenderer, render_docx
from .upstream import (
    UpstreamRenderError,
    build_upstream_documents,
    markdown_parts,
    render_docx_upstream,
    upstream_identity,
)

__all__ = [
    "DocxRenderer",
    "UpstreamRenderError",
    "build_upstream_documents",
    "markdown_parts",
    "render_docx",
    "render_docx_selected",
    "render_docx_upstream",
    "resolve_renderer",
    "upstream_identity",
]


def resolve_renderer(draft, renderer: str = "auto") -> str:
    """把 ``auto`` 解析为具体制作器；外观设计没有上游四文书模型。"""
    if renderer == "auto":
        return "local" if draft.patent_type is PatentType.DESIGN else "upstream"
    if renderer in {"local", "upstream"}:
        return renderer
    raise ValueError(f"未知制作器：{renderer}")


def render_docx_selected(
    draft,
    output,
    options=None,
    *,
    split: bool = False,
    renderer: str = "auto",
):
    """按统一选择规则制作 DOCX，返回 ``(写出的文件, 实际使用的制作器)``。"""
    used = resolve_renderer(draft, renderer)
    if used == "upstream":
        written = render_docx_upstream(draft, output, options=options, split=split)
    else:
        written = render_docx(draft, output, options=options, split=split)
    return written, used
