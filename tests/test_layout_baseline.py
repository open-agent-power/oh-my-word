"""版面合规基线的回归测试。

这里的数值不是随手定的默认值，而是「官方毫米口径 + 渲染后墨迹实测」的结论：
字高 3.5~4.5mm、行距 2.5~3.5mm、页码下沿距纸底 15mm、页边距 25/25/15/15。

把它们钉死，是为了让「标题调大一点好看」这类改动立刻失败——字号与行距
只能渲染后量墨迹，不能按 pt 或倍数折算（12pt≈3.9mm、13pt≈4.3mm、
14pt≈4.7mm 已超上限；1.5 倍行距实测 4.32mm 超 3.5mm）。
"""

from __future__ import annotations

import unittest

from oh_my_patent import spec


class LayoutBaselineTest(unittest.TestCase):
    def test_glyph_heights_stay_within_filing_range(self) -> None:
        # 宋体实测：13pt 墨迹约 4.3mm，是 4.5mm 上限内可用的最大常用字号。
        self.assertLessEqual(spec.TITLE_FONT_SIZE_PT, 13.0)
        self.assertLessEqual(spec.HEADING_NAME_FONT_SIZE_PT, 13.0)
        self.assertLessEqual(spec.SECTION_FONT_SIZE_PT, 13.0)

    def test_body_size_stays_readable_and_in_range(self) -> None:
        self.assertGreaterEqual(spec.BODY_FONT_SIZE_PT, 12.0)
        self.assertLessEqual(spec.BODY_FONT_SIZE_PT, 13.0)

    def test_line_spacing_stays_within_filing_range(self) -> None:
        # 1.25 倍 → 行间空白 2.96mm（合规）；1.5 倍 → 4.32mm（超 3.5mm 上限）。
        self.assertAlmostEqual(spec.LINE_SPACING, 1.25)
        self.assertLess(spec.LINE_SPACING, 1.5)

    def test_page_numbers_on_by_default(self) -> None:
        # 缺页码不是「朴素排版」，不符合审查指南第五部分第一章 4.3/5.6。
        self.assertTrue(spec.PAGE_NUMBER_REQUIRED)

    def test_margins_match_official_values(self) -> None:
        self.assertEqual(
            (
                spec.MARGIN_TOP_MM,
                spec.MARGIN_LEFT_MM,
                spec.MARGIN_RIGHT_MM,
                spec.MARGIN_BOTTOM_MM,
            ),
            (25.0, 25.0, 15.0, 15.0),
        )


if __name__ == "__main__":
    unittest.main()
