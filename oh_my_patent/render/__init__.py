"""渲染层：把 :class:`~oh_my_patent.schema.PatentDraft` 输出成文书。

当前提供两条 .docx 制作路径：

- 本地渲染器（:mod:`.docx`）：专利稿件模型直写 OOXML，默认路径；
- 上游复用适配（:mod:`.upstream`）：固定上游 handsomestWei 转换器 + 边界版式，
  通过 ``--renderer upstream`` 显式选用。

渲染器与模型之间只通过 :class:`~oh_my_patent.schema.PatentDraft` 交互。
"""

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
    "render_docx_upstream",
    "upstream_identity",
]
