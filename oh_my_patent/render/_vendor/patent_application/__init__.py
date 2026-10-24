"""Vendored MIT 授权的专利 Markdown → Word 转换模块。

固定来源：``handsomestWei/patent-disclosure-skill`` 提交
``6935a14d342ed9c7a07440c999d1b7bf1852a701`` 的
``skills/patent-application/tools/``。文件与上游逐字节一致，SHA256 见同目录
``UPSTREAM.json``，由 :mod:`oh_my_patent.render.upstream` 在运行时校验；
本目录没有本地补丁。升级必须整体替换并重新核对哈希与行为。

上游代码按裸模块名互相 import（``md_to_docx`` 自己会把它所在目录加入
``sys.path``），因此这里沿用同样的加载方式，不改成包相对导入。
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from emit_application_docx import (  # noqa: E402
    DEFAULT_STEMS,
    LatexDelimError,
    emit_one,
)
from latex_delimiters import find_bare_paren_latex, format_hits_report  # noqa: E402
from md_to_docx import convert_md_to_docx, get_math_stats  # noqa: E402

__all__ = [
    "DEFAULT_STEMS",
    "LatexDelimError",
    "convert_md_to_docx",
    "emit_one",
    "find_bare_paren_latex",
    "format_hits_report",
    "get_math_stats",
]
