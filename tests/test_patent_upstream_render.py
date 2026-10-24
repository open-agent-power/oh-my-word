"""上游专利 Word 转换模块复用的验收测试。

断言分四类，避免把「生成成功」当成「可交付」：

1. 固定身份：vendored 原件与 ``UPSTREAM.json``、第三方许可逐字节一致；
2. 投影：稿件 → 上游四类 Markdown 的章节顺序和内容；
3. 边界版面：A4、黑色标题、宋体、字号、行距、首行缩进、纯文本编号；
4. 失败门禁：坏公式回退、缺图、普通括号 LaTeX、外观设计均明确失败。
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from oh_my_patent.cli import main as cli_main
from oh_my_patent.render import (
    UpstreamRenderError,
    markdown_parts,
    render_docx_upstream,
    upstream_identity,
)
from oh_my_patent.schema import Claim, Drawing, PatentDraft, PatentType
from oh_my_patent.spec import HEADING_NAME_FONT_SIZE_PT, RenderOptions, TITLE_FONT_SIZE_PT

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR = REPO_ROOT / "oh_my_patent" / "render" / "_vendor" / "patent_application"
M_OMML = "{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"

#: 最小合法 PNG（1×1），避免测试依赖 Pillow。
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _image(root: Path) -> Path:
    path = root / "figure-1.png"
    path.write_bytes(PNG_BYTES)
    return path


def _draft(root: Path, *, math: bool = False, drawings: bool = False) -> PatentDraft:
    embodiments = "步骤S101，接收带序号的记录。\n\n步骤S102，写入缓冲队列，标记END_D。"
    if math:
        embodiments += (
            "\n\n内联均值为 $\\bar{x}=\\frac{1}{n}\\sum_{i=1}^{n}x_i$，单位为毫秒。"
            "\n\n$$\nE=\\sum_{i=1}^{n}(x_i-\\mu)^2\n$$"
        )
    drawing_list = []
    if drawings:
        drawing_list = [Drawing(number=1, caption="队列处理结构图", path=str(_image(root)))]
    return PatentDraft(
        title="一种缓冲队列处理方法",
        patent_type=PatentType.INVENTION,
        technical_field="本发明涉及数据处理领域，标记FIELD_A。",
        background="输入记录经队列暂存后按既定顺序读取，标记BACKGROUND_B。",
        problems="读取顺序不稳定。",
        solution="接收模块读取记录，缓冲模块保存记录，输出模块返回记录。",
        effects="读取顺序可复现。",
        embodiments=embodiments,
        claims=[
            Claim(
                number=1,
                text="一种缓冲队列处理方法，其特征在于，包括接收记录、保存记录和按序号输出记录。",
            )
        ],
        abstract="本合成示例包括接收模块、缓冲模块和输出模块，标记ABSTRACT_E。",
        drawings=drawing_list,
    )


class IdentityTests(unittest.TestCase):
    def test_vendor_bytes_match_manifest(self) -> None:
        manifest = upstream_identity(verify=True)
        self.assertEqual(manifest["commit"], "6935a14d342ed9c7a07440c999d1b7bf1852a701")
        self.assertEqual(manifest["license"], "MIT")
        self.assertEqual(manifest["modifications"], [])
        for name, expected in manifest["files"].items():
            actual = hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, name)

    def test_vendored_license_matches_third_party_record(self) -> None:
        vendored = (VENDOR / "LICENSE").read_bytes()
        recorded = (REPO_ROOT / "third_party" / "licenses" / "patent-disclosure-MIT.txt").read_bytes()
        self.assertEqual(vendored, recorded)

    def test_full_module_is_present(self) -> None:
        from oh_my_patent.render._vendor.patent_application import DEFAULT_STEMS

        self.assertIn("说明书", DEFAULT_STEMS)
        for name in ("md_to_docx.py", "math_to_omml.py", "latex_delimiters.py", "stdio_utf8.py"):
            self.assertTrue((VENDOR / name).is_file(), name)


class ProjectionTests(unittest.TestCase):
    def test_parts_and_section_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parts = markdown_parts(_draft(Path(tmp), drawings=True), RenderOptions())
        self.assertEqual(
            set(parts), {"claims", "description", "abstract", "drawings"}
        )
        description = parts["description"]
        positions = [
            description.index(f"【{title}】")
            for title in ("技术领域", "背景技术", "发明内容", "附图说明", "具体实施方式")
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("## 一种缓冲队列处理方法", description)
        self.assertTrue(parts["claims"].startswith("# 权利要求书\n\n1. 一种缓冲队列"))
        self.assertIn("标记ABSTRACT_E", parts["abstract"])
        self.assertIn("![图1](", parts["drawings"])
        self.assertIn("图1", parts["drawings"])

    def test_split_projection_includes_abstract_drawing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parts = markdown_parts(_draft(Path(tmp), drawings=True), RenderOptions(), split=True)
        self.assertIn("abstract_drawing", parts)
        self.assertIn("摘要附图", parts["abstract_drawing"])
        self.assertNotIn("![摘要附图]", parts["abstract"])


class RenderTests(unittest.TestCase):
    def test_boundary_layout_and_numbering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "out.docx"
            render_docx_upstream(_draft(root), target, RenderOptions())

            document = Document(str(target))
            section = document.sections[0]
            self.assertAlmostEqual(section.page_width.mm, 210, delta=0.5)
            self.assertAlmostEqual(section.page_height.mm, 297, delta=0.5)
            self.assertAlmostEqual(section.top_margin.mm, 25, delta=0.5)
            self.assertAlmostEqual(section.left_margin.mm, 25, delta=0.5)
            self.assertAlmostEqual(section.right_margin.mm, 15, delta=0.5)
            self.assertAlmostEqual(section.bottom_margin.mm, 15, delta=0.5)

            heading1 = document.styles["Heading 1"]
            self.assertAlmostEqual(heading1.font.size.pt, TITLE_FONT_SIZE_PT)
            self.assertEqual(str(heading1.font.color.rgb), "000000")
            heading2 = document.styles["Heading 2"]
            self.assertAlmostEqual(heading2.font.size.pt, HEADING_NAME_FONT_SIZE_PT)
            self.assertEqual(str(heading2.font.color.rgb), "000000")

            normal = document.styles["Normal"]
            self.assertAlmostEqual(normal.font.size.pt, 12)
            rfonts = normal.element.rPr.rFonts
            self.assertEqual(rfonts.get(qn("w:eastAsia")), "宋体")
            self.assertEqual(rfonts.get(qn("w:hint")), "eastAsia")

            claim_paragraphs = [p for p in document.paragraphs if p.text.startswith("1. 一种")]
            self.assertEqual(len(claim_paragraphs), 1)
            claim = claim_paragraphs[0]
            self.assertEqual(claim.style.name, "Normal")
            self.assertIsNone(claim._element.find(".//" + qn("w:numPr")))

            body = next(p for p in document.paragraphs if "标记FIELD_A" in p.text)
            self.assertGreaterEqual(body.paragraph_format.first_line_indent.pt, 23.5)
            self.assertAlmostEqual(body.paragraph_format.line_spacing, 1.5)

    def test_markdown_table_keeps_data_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.embodiments += (
                "\n\n| 参数 | 定义 | 单位 |\n| --- | --- | --- |\n"
                "| $n$ | 样本数量PARAM_N | 个 |\n| $x_i$ | 第i次时延PARAM_X | ms |"
            )
            target = root / "table.docx"
            render_docx_upstream(draft, target, RenderOptions())
            document = Document(str(target))
            self.assertEqual(len(document.tables), 1)
            self.assertEqual(len(document.tables[0].rows), 3)
            cells = [cell.text for row in document.tables[0].rows for cell in row.cells]
            self.assertIn("样本数量PARAM_N", cells)
            self.assertIn("第i次时延PARAM_X", cells)
            self.assertFalse(
                any(p.text.strip().startswith("|") for p in document.paragraphs),
                "表格数据行不应退化成带竖线的正文段落",
            )

    def test_math_becomes_native_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "math.docx"
            render_docx_upstream(_draft(root, math=True), target, RenderOptions())
            document = Document(str(target))
            equations = document.element.body.findall(".//" + M_OMML)
            self.assertGreaterEqual(len(equations), 2)
            self.assertNotIn("$", "".join(p.text for p in document.paragraphs))

    def test_single_output_contains_all_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "all.docx"
            render_docx_upstream(_draft(root, drawings=True), target, RenderOptions())
            document = Document(str(target))
            titles = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
            self.assertEqual(titles, ["权利要求书", "说明书", "说明书摘要", "说明书附图"])

    def test_split_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "split"
            written = render_docx_upstream(_draft(root, drawings=True), out, RenderOptions(), split=True)
            names = {path.name for path in written}
            self.assertEqual(
                names,
                {
                    "一种缓冲队列处理方法_权利要求书.docx",
                    "一种缓冲队列处理方法_说明书.docx",
                    "一种缓冲队列处理方法_说明书摘要.docx",
                    "一种缓冲队列处理方法_说明书附图.docx",
                    "一种缓冲队列处理方法_摘要附图.docx",
                },
            )
            for path in written:
                self.assertGreater(path.stat().st_size, 0)


class FailureGateTests(unittest.TestCase):
    def test_math_fallback_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.technical_field = "含无法转换的公式 $\\begin{cases}$。"
            with self.assertRaises(UpstreamRenderError) as ctx:
                render_docx_upstream(draft, root / "bad.docx", RenderOptions())
            self.assertIn("公式", str(ctx.exception))

    def test_bare_dollar_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.technical_field = "行内写成 $$x +$$ 时不会被转换。"
            with self.assertRaises(UpstreamRenderError):
                render_docx_upstream(draft, root / "bad.docx", RenderOptions())

    def test_missing_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.drawings = [Drawing(number=1, caption="缺失图", path=str(root / "no-such.png"))]
            with self.assertRaises(UpstreamRenderError) as ctx:
                render_docx_upstream(draft, root / "bad.docx", RenderOptions())
            self.assertIn("图片", str(ctx.exception))

    def test_bare_paren_latex_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.technical_field = "均值 (M_{\\mathrm{total}}) 按普通括号书写。"
            with self.assertRaises(UpstreamRenderError) as ctx:
                render_docx_upstream(draft, root / "bad.docx", RenderOptions())
            self.assertIn("LaTeX", str(ctx.exception))

    def test_design_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = PatentDraft(title="一种外观", patent_type=PatentType.DESIGN)
            with self.assertRaises(UpstreamRenderError) as ctx:
                render_docx_upstream(draft, root / "design.docx", RenderOptions())
            self.assertIn("外观设计", str(ctx.exception))


class CliTests(unittest.TestCase):
    DRAFT = """---
title: 一种测试方法
type: invention
---

# 权利要求书

1. 一种测试方法，其特征在于，包括接收记录、保存记录和输出记录。

# 说明书

本发明涉及数据处理领域，标记FIELD_A。

【技术领域】

本发明涉及数据处理领域，标记FIELD_A。

【背景技术】

输入记录按既定顺序读取，标记BACKGROUND_B。

【发明内容】

接收模块读取记录，缓冲模块保存记录。

【具体实施方式】

步骤S101，接收带序号的记录，标记END_D。

# 摘要

本合成示例仅用于测试，标记ABSTRACT_E。
"""

    def test_cli_build_with_upstream_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path = root / "draft.md"
            draft_path.write_text(self.DRAFT, encoding="utf-8")
            output = root / "out.docx"
            code = cli_main(
                ["build", str(draft_path), "-o", str(output), "--renderer", "upstream"]
            )
            self.assertEqual(code, 0)
            self.assertTrue(output.is_file())
            document = Document(str(output))
            titles = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
            self.assertEqual(titles, ["权利要求书", "说明书", "说明书摘要"])


COMPLETE_DRAFT = """---
title: 一种安装验收装置
type: invention
drawings:
  - {{number: 1, caption: 结构图, path: {image}}}
---

# 权利要求书

1. 一种安装验收装置，其特征在于，包括采集模块和存储模块。

# 说明书

【技术领域】

本合成材料仅用于测试，标记AUTO_FIELD。

【具体实施方式】

采集模块读取记录，存储模块保存记录，标记AUTO_END。

# 摘要

本合成材料仅用于测试，标记AUTO_ABS。
"""

DESIGN_DRAFT = """---
title: 水杯
type: design
---

# 简要说明

本外观设计产品用于盛装饮用水。
"""

MISSING_FIGURE_DRAFT = """---
title: 一种缺图装置
type: invention
drawings:
  - {number: 1, caption: 结构图, path: no-such-figure.png}
---

# 权利要求书

1. 一种缺图装置，其特征在于，包括采集模块。

# 说明书

【技术领域】

本合成材料仅用于测试，标记MISS_FIELD。

# 摘要

本合成材料仅用于测试，标记MISS_ABS。
"""


class DefaultRendererTests(unittest.TestCase):
    """默认 auto：发明/实用新型走上游，外观设计走本地；不可用稿明确失败。"""

    def _build(self, draft_path: Path, output: Path, *extra: str):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_main(["build", str(draft_path), "-o", str(output), *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_default_uses_upstream_for_invention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "figure-1.png"
            image.write_bytes(PNG_BYTES)
            draft = root / "complete.md"
            draft.write_text(COMPLETE_DRAFT.format(image=str(image).replace("\\", "/")), encoding="utf-8")
            output = root / "out.docx"
            code, stdout, _ = self._build(draft, output)
            self.assertEqual(code, 0)
            self.assertIn("上游制作器", stdout)
            document = Document(str(output))
            titles = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
            self.assertEqual(titles, ["权利要求书", "说明书", "说明书摘要", "说明书附图"])

    def test_default_uses_local_for_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "design.md"
            draft.write_text(DESIGN_DRAFT, encoding="utf-8")
            output = root / "design.docx"
            code, stdout, _ = self._build(draft, output)
            self.assertEqual(code, 0)
            self.assertIn("本地制作器", stdout)
            document = Document(str(output))
            self.assertFalse(
                [p for p in document.paragraphs if p.style.name == "Heading 1"],
                "本地排版不应出现上游的 Heading 1 文书标题",
            )

    def test_default_fails_on_missing_figure_and_points_to_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "missing.md"
            draft.write_text(MISSING_FIGURE_DRAFT, encoding="utf-8")
            output = root / "missing.docx"
            code, _, stderr = self._build(draft, output)
            self.assertEqual(code, 2)
            self.assertIn("--renderer local", stderr)
            self.assertFalse(output.exists())

            local = root / "missing-local.docx"
            code, stdout, _ = self._build(draft, local, "--renderer", "local")
            self.assertEqual(code, 0)
            self.assertIn("本地制作器", stdout)
            self.assertTrue(local.is_file())
            body = "\n".join(p.text for p in Document(str(local)).paragraphs)
            self.assertIn("缺失", body)


JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD06iiigD//2Q=="
)


class RendererOptionTests(unittest.TestCase):
    """默认 auto 路径下的选项矩阵与边界输入。"""

    def _build(self, draft_path: Path, output: Path, *extra: str):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli_main(["build", str(draft_path), "-o", str(output), *extra])
        return code, stdout.getvalue(), stderr.getvalue()

    def _complete_draft(self, root: Path) -> Path:
        image = _image(root)
        draft = root / "complete.md"
        draft.write_text(
            COMPLETE_DRAFT.format(image=str(image).replace("\\", "/")), encoding="utf-8"
        )
        return draft

    def test_json_stdout_is_pure_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self._complete_draft(root)
            output = root / "out.docx"
            code, stdout, stderr = self._build(draft, output, "--json")
            self.assertEqual(code, 0)
            payload = json.loads(stdout)  # 必须能整体解析，不能夹带人类可读行
            self.assertTrue(payload["ok"])
            self.assertIn("上游制作器", stderr)

    def test_font_size_spacing_and_page_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self._complete_draft(root)
            output = root / "styled.docx"
            code, _, _ = self._build(
                draft,
                output,
                "--font",
                "仿宋",
                "--font-size",
                "10",
                "--line-spacing",
                "2",
                "--page-numbers",
            )
            self.assertEqual(code, 0)
            document = Document(str(output))
            normal = document.styles["Normal"]
            self.assertAlmostEqual(normal.font.size.pt, 10)
            self.assertEqual(normal.element.rPr.rFonts.get(qn("w:eastAsia")), "仿宋")
            body = next(p for p in document.paragraphs if "AUTO_FIELD" in p.text)
            self.assertAlmostEqual(body.paragraph_format.line_spacing, 2)
            footer = document.sections[0].footer
            self.assertTrue(
                footer.paragraphs
                and footer.paragraphs[0]._element.findall(".//" + qn("w:fldChar"))
            )

    def test_no_part_titles_and_no_page_breaks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = self._complete_draft(root)
            output = root / "flat.docx"
            code, _, _ = self._build(draft, output, "--no-part-titles", "--no-page-breaks")
            self.assertEqual(code, 0)
            document = Document(str(output))
            self.assertFalse([p for p in document.paragraphs if p.style.name == "Heading 1"])
            self.assertEqual(
                len(document.element.body.findall(".//" + qn("w:pageBreakBefore"))), 0
            )

    def test_subsection_keep_creates_level_four_headings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "keep.md"
            draft.write_text(
                """---
title: 一种保留小标题方法
type: invention
---

# 说明书

【发明内容】

【要解决的技术问题】

顺序不稳定。

【技术方案】

采集模块读取记录。

【有益效果】

顺序可复现。
""",
                encoding="utf-8",
            )
            output = root / "keep.docx"
            code, _, _ = self._build(draft, output, "--subsection-style", "keep")
            self.assertEqual(code, 0)
            document = Document(str(output))
            headings = [(p.text, p.style.name) for p in document.paragraphs if p.style.name.startswith("Heading")]
            self.assertIn(("技术方案", "Heading 4"), headings)
            self.assertIn(("有益效果", "Heading 4"), headings)

    def test_type_override_switches_section_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "full.md"
            draft.write_text(
                """---
title: 一种完整方法
type: invention
---

# 权利要求书

1. 一种完整方法，其特征在于，包括采集记录。

# 说明书

## 技术领域

本合成材料仅用于测试。

## 背景技术

现有方式存在遗漏。

## 发明内容

### 要解决的技术问题

减少遗漏。

### 技术方案

采集模块读取记录。

### 有益效果

减少遗漏。

## 具体实施方式

步骤S101，采集记录。
""",
                encoding="utf-8",
            )
            output = root / "utility.docx"
            code, _, _ = self._build(draft, output, "--type", "utility")
            self.assertEqual(code, 0)
            text = "\n".join(p.text for p in Document(str(output)).paragraphs)
            self.assertIn("【实用新型内容】", text)
            self.assertNotIn("【发明内容】", text)

    def test_table_escaped_pipe_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = _draft(root)
            draft.embodiments += (
                "\n\n| 参数 | 说明 |\n| --- | --- |\n| $n$ | 转义 a \\| b 单元格 |"
            )
            target = root / "pipe.docx"
            render_docx_upstream(draft, target, RenderOptions())
            cells = [
                cell.text
                for table in Document(str(target)).tables
                for row in table.rows
                for cell in row.cells
            ]
            self.assertIn("转义 a | b 单元格", cells)
            self.assertFalse(any("\\|" in cell for cell in cells))

    def test_jpeg_figure_embeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jpeg = root / "figure.jpg"
            jpeg.write_bytes(JPEG_BYTES)
            draft = _draft(root)
            draft.drawings = [Drawing(number=1, caption="JPEG 结构图", path=str(jpeg))]
            target = root / "jpeg.docx"
            render_docx_upstream(draft, target, RenderOptions())
            with zipfile.ZipFile(target) as archive:
                media = [n for n in archive.namelist() if n.startswith("word/media/")]
            self.assertTrue(media)

    def test_svg_figure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = root / "figure.svg"
            svg.write_text(
                "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/>",
                encoding="utf-8",
            )
            draft = _draft(root)
            draft.drawings = [Drawing(number=1, caption="SVG 结构图", path=str(svg))]
            with self.assertRaises(UpstreamRenderError) as ctx:
                render_docx_upstream(draft, root / "svg.docx", RenderOptions())
            self.assertIn("图片", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
