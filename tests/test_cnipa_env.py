"""``oh_my_patent.cnipa_env`` 的检测与信任项逻辑。

真实环境相关的探测（注册表、文件、Word COM）不在这里断言；测试注入假的探测结果，
验证「结论/退出码/动作建议」这一层判断是否正确。实机结论记录在
``docs/cnipa-format-lessons.md`` 第七节。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from oh_my_patent import cnipa_env
from oh_my_patent import cli


def _fake_office(installed=True, runtime="10.0.60917"):
    return {
        "installed": installed,
        "version": "16.0.20527.20088",
        "edition": "O365ProPlusRetail",
        "platform": "x64",
        "exe": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        "vsto_runtime": runtime,
    }


def _fake_tool(installed=True, vsto=True, dtd=True):
    base = r"C:\Users\u\AppData\Local\CNIPR\PatentTool_20240717"
    return {
        "installed": installed,
        "arp": {"WORD转XML编辑器": "1.0.0"} if installed else {},
        "dirs": [base] if installed else [],
        "vsto": f"{base}\\PatentTool.vsto" if (installed and vsto) else None,
        "dtdandxsl": r"C:\ProgramData\PatentTool\dtdandxsl" if (installed and dtd) else None,
    }


class DetectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = {
            name: getattr(cnipa_env, name)
            for name in (
                "detect_office",
                "detect_wps",
                "detect_tool",
                "detect_addin",
                "detect_vsto_inclusion",
                "detect_signature",
                "probe_word_com",
            )
        }
        self._platform = cnipa_env.platform
        cnipa_env.detect_wps = lambda: {"installed": False, "versions": {}, "exe": None}
        cnipa_env.detect_signature = lambda vsto: {"available": False}
        cnipa_env.detect_vsto_inclusion = lambda: []
        cnipa_env.probe_word_com = lambda: {"available": False, "error": "跳过"}

    def tearDown(self) -> None:
        for name, value in self._orig.items():
            setattr(cnipa_env, name, value)
        cnipa_env.platform = self._platform

    def _windows(self):
        class FakePlatform:
            @staticmethod
            def system():
                return "Windows"

            @staticmethod
            def release():
                return "11"

            @staticmethod
            def version():
                return "10.0.22631"

        cnipa_env.platform = FakePlatform

    def test_non_windows_is_unsupported(self):
        class FakePlatform:
            @staticmethod
            def system():
                return "Linux"

            @staticmethod
            def release():
                return "6.1"

            @staticmethod
            def version():
                return "6.1.0"

        cnipa_env.platform = FakePlatform
        report = cnipa_env.detect()
        self.assertEqual(report.status, "unsupported")
        self.assertTrue(report.actions)

    def test_missing_everything_is_not_ready(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office(False)
        cnipa_env.detect_tool = lambda: _fake_tool(False)
        cnipa_env.detect_addin = lambda: {"registered": False}
        report = cnipa_env.detect()
        self.assertEqual(report.status, "not-ready")
        self.assertTrue(any("cnipa_install" in action for action in report.actions))

    def test_installed_and_trusted_is_ready(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office()
        cnipa_env.detect_tool = lambda: _fake_tool()
        cnipa_env.detect_addin = lambda: {"registered": True, "hive": "HKEY_CURRENT_USER", "load_behavior": 3}
        cnipa_env.detect_vsto_inclusion = lambda: [
            {"guid": "{x}", "url": "file:///C:/.../PatentTool.vsto", "name": "PatentTool", "public_key": True}
        ]
        report = cnipa_env.detect()
        self.assertEqual(report.status, "ready")

    def test_expired_signature_without_trust_is_degraded(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office()
        cnipa_env.detect_tool = lambda: _fake_tool()
        cnipa_env.detect_addin = lambda: {"registered": True, "hive": "HKEY_CURRENT_USER", "load_behavior": 3}
        cnipa_env.detect_signature = lambda vsto: {
            "available": True,
            "signed": True,
            "expired": True,
            "has_timestamp": False,
        }
        report = cnipa_env.detect()
        self.assertEqual(report.status, "degraded")
        self.assertTrue(any("--fix-trust" in action for action in report.actions))

    def test_expired_signature_with_trust_is_ready(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office()
        cnipa_env.detect_tool = lambda: _fake_tool()
        cnipa_env.detect_addin = lambda: {"registered": True, "hive": "HKEY_CURRENT_USER", "load_behavior": 3}
        cnipa_env.detect_signature = lambda vsto: {
            "available": True,
            "signed": True,
            "expired": True,
            "has_timestamp": False,
        }
        cnipa_env.detect_vsto_inclusion = lambda: [
            {"guid": "{x}", "url": "file:///C:/.../PatentTool.vsto", "name": "PatentTool", "public_key": True}
        ]
        report = cnipa_env.detect()
        self.assertEqual(report.status, "ready")
        signature = next(c for c in report.checks if c.key == "signature")
        self.assertIn("信任项", signature.detail)

    def test_trust_entry_pointing_at_directory_is_not_trusted(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office()
        cnipa_env.detect_tool = lambda: _fake_tool()
        cnipa_env.detect_addin = lambda: {"registered": True, "hive": "HKEY_CURRENT_USER", "load_behavior": 3}
        cnipa_env.detect_vsto_inclusion = lambda: [
            {"guid": "{x}", "url": "file:///C:/.../PatentTool_20240717/", "name": "PatentTool", "public_key": True}
        ]
        report = cnipa_env.detect()
        trust = next(c for c in report.checks if c.key == "trust")
        self.assertEqual(trust.status, cnipa_env.WARN)

    def test_dtd_missing_warns(self):
        self._windows()
        cnipa_env.detect_office = lambda: _fake_office()
        cnipa_env.detect_tool = lambda: _fake_tool(dtd=False)
        cnipa_env.detect_addin = lambda: {"registered": True, "hive": "HKEY_CURRENT_USER", "load_behavior": 3}
        cnipa_env.detect_vsto_inclusion = lambda: [
            {"guid": "{x}", "url": "file:///C:/.../PatentTool.vsto", "name": "PatentTool", "public_key": True}
        ]
        report = cnipa_env.detect()
        dtd = next(c for c in report.checks if c.key == "dtdandxsl")
        self.assertEqual(dtd.status, cnipa_env.WARN)


class InclusionKeyTests(unittest.TestCase):
    def test_key_is_rsakeyvalue_xml(self):
        manifest = Path(__file__).with_name("_vsto_sample.vsto")
        manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<asmv1:assembly xmlns:asmv1="urn:schemas-microsoft-com:asm.v1" '
            'xmlns:d="http://www.w3.org/2000/09/xmldsig#">'
            "<d:Signature><d:KeyInfo><d:KeyValue><d:RSAKeyValue>"
            "<d:Modulus>ABC=</d:Modulus><d:Exponent>AQAB</d:Exponent>"
            "</d:RSAKeyValue></d:KeyValue></d:KeyInfo></d:Signature>"
            "</asmv1:assembly>",
            encoding="utf-8",
        )
        try:
            key = cnipa_env.inclusion_key(str(manifest))
            self.assertEqual(
                key,
                "<RSAKeyValue><Modulus>ABC=</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>",
            )
        finally:
            manifest.unlink(missing_ok=True)

    def test_key_missing_returns_none(self):
        manifest = Path(__file__).with_name("_vsto_nokey.vsto")
        manifest.write_text('<?xml version="1.0"?><assembly/>', encoding="utf-8")
        try:
            self.assertIsNone(cnipa_env.inclusion_key(str(manifest)))
        finally:
            manifest.unlink(missing_ok=True)

    def test_fix_trust_writes_url_and_key(self):
        manifest = Path(__file__).with_name("_vsto_fix.vsto")
        manifest.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<asmv1:assembly xmlns:asmv1="urn:schemas-microsoft-com:asm.v1" '
            'xmlns:d="http://www.w3.org/2000/09/xmldsig#">'
            "<d:Signature><d:KeyInfo><d:KeyValue><d:RSAKeyValue>"
            "<d:Modulus>ABC=</d:Modulus><d:Exponent>AQAB</d:Exponent>"
            "</d:RSAKeyValue></d:KeyValue></d:KeyInfo></d:Signature>"
            "</asmv1:assembly>",
            encoding="utf-8",
        )
        written = {}

        def fake_write(root_name, path, values):
            written["root"] = root_name
            written["path"] = path
            written["values"] = values

        original = cnipa_env._write_reg
        cnipa_env._write_reg = fake_write
        try:
            result = cnipa_env.fix_trust({"installed": True, "vsto": str(manifest)})
        finally:
            cnipa_env._write_reg = original
            manifest.unlink(missing_ok=True)
        self.assertTrue(result["fixed"])
        self.assertTrue(written["values"]["Url"].endswith(".vsto"))
        self.assertIn("<RSAKeyValue>", written["values"]["PublicKey"])
        self.assertEqual(written["values"]["Name"], "PatentTool")


class CliEnvTests(unittest.TestCase):
    def test_env_json_returns_report(self):
        original = cnipa_env.detect
        cnipa_env.detect = lambda with_com=False: cnipa_env.Report(
            os="Windows 11", checks=[cnipa_env.Check("os", "操作系统", cnipa_env.OK)], status="ready"
        )
        try:
            import contextlib
            import io

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = cli.main(["env", "--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            self.assertEqual(payload["status"], "ready")
        finally:
            cnipa_env.detect = original

    def test_env_command_is_registered(self):
        self.assertIn("env", cli._COMMANDS)


if __name__ == "__main__":
    unittest.main()
