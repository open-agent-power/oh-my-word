import pytest

from oh_my_patent.lint import check_reference_numerals
from oh_my_patent.parser import parse_markdown


@pytest.mark.parametrize("text,should_flag", [
    ("以BM25计算得分，其中k1取1.5，b取0.75。", False),
    ("参数取1．5，阈值取0.25。", False),
    ("装置包括壳体1.其内部设置处理器2。", True),
])
def test_decimal_parameters_are_not_integer_drawing_labels(text, should_flag):
    draft = parse_markdown("---\ntitle: 一种处理方法\ntype: invention\n---\n# 说明书\n## 具体实施方式\n" + text)
    assert any(i.code == "REF-001" for i in check_reference_numerals(draft)) is should_flag
