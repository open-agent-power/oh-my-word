"""``oh_my_patent.cnipa_convert`` 的纯逻辑部分（不启动 Word）。

UI Automation 那一段只能在装了 Word + 官方插件的 Windows 上跑，不进单测；
这里保证：文书编码识别、产物定位、DTD 校验的“不知道就说不」不会变成假成功。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from oh_my_patent import cnipa_convert as convert


class NamingTests(unittest.TestCase):
    def test_clean_name_removes_zero_width(self):
        self.assertEqual(convert.clean_name("一键\u200b添加标记"), "一键添加标记")
        self.assertEqual(convert.clean_name("  单书XML转换  "), "单书XML转换")

    def test_code_from_filename(self):
        self.assertEqual(convert.code_from_filename(Path("100001-权利要求书.docx")), "100001")
        self.assertEqual(convert.code_from_filename(Path("100003-说明书附图.docx")), "100003")
        self.assertIsNone(convert.code_from_filename(Path("说明书.docx")))
        self.assertIsNone(convert.code_from_filename(Path("100009-别的.docx")))

    def test_code_from_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            for tag, code in (
                ("<cn-claims>", "100001"),
                ("<cn-description>", "100002"),
                ("<cn-drawings>", "100003"),
                ("<cn-abstract>", "100004"),
            ):
                path = Path(tmp) / f"{code}.xml"
                path.write_text(f'<?xml version="1.0"?><cn-application-body>{tag}</cn-application-body>', encoding="utf-8")
                self.assertEqual(convert.code_from_xml(path), code)
            unknown = Path(tmp) / "x.xml"
            unknown.write_text("<cn-application-body/>", encoding="utf-8")
            self.assertIsNone(convert.code_from_xml(unknown))

    def test_output_root_matches_tool_layout(self):
        self.assertEqual(convert.output_root(Path("a/b/100001-权利要求书.docx")), Path("a/b/100001-权利要求书"))


class LocateTests(unittest.TestCase):
    def test_find_outputs_returns_fresh_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "100001-权利要求书.docx"
            docx.write_bytes(b"x")
            produced = Path(tmp) / "100001-权利要求书" / "100001" / "100001.xml"
            produced.parent.mkdir(parents=True)
            produced.write_text("<x/>", encoding="utf-8")
            found = convert.find_outputs(docx, since=0, timeout=0)
            self.assertEqual(found, [produced])

    def test_find_outputs_empty_when_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "a.docx"
            docx.write_bytes(b"x")
            self.assertEqual(convert.find_outputs(docx, since=0, timeout=0), [])


class DtdLocationTests(unittest.TestCase):
    def test_dtd_found_next_to_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dtd = base / "dtdandxsl" / "cn-application-body-20080416.dtd"
            dtd.parent.mkdir(parents=True)
            dtd.write_text("<!ELEMENT x EMPTY>", encoding="utf-8")
            xml = base / "book" / "100001" / "100001.xml"
            xml.parent.mkdir(parents=True)
            xml.write_text("<x/>", encoding="utf-8")
            original = convert.dtd_path
            try:
                self.assertEqual(convert.dtd_path(xml), dtd)
            finally:
                convert.dtd_path = original


class ValidateTests(unittest.TestCase):
    def test_missing_dtd_is_reported_not_passed(self):
        original = convert.dtd_path
        convert.dtd_path = lambda *args, **kwargs: None
        try:
            result = convert.validate(Path("whatever.xml"))
        finally:
            convert.dtd_path = original
        self.assertFalse(result["validated"])
        self.assertIn("DTD", result["reason"])


if __name__ == "__main__":
    unittest.main()
