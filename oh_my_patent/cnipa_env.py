"""检测本机能否跑官方「WORD 转 XML 编辑器」，并给出可执行的处置建议。

这一层只回答一个问题：**现在这台机器能不能把 DOCX 转成国知局 XML**。
专利文本的合规性由 ``lint``/``final`` 管，转换结果由官方工具管，这里不重复判断。

检查项与本次实机踩坑的对应关系（见 ``docs/cnipa-format-lessons.md`` 第七节）：

=========================  ===================================================
检查                       对应的真实故障
=========================  ===================================================
Windows 版本               官方要求 Windows 10 及以上
Office / WPS 宿主          工具是 VSTO 加载项，没有 Word 2013+ 或 WPS 专业版就无从加载
插件安装                   MSI 启动条件 ``SETUPEXEDIR OR REMOVE="ALL"``，直装必失败
插件注册                   ``HKCU\\...\\Word\\Addins\\CNIPR.PatentTool``
签名证书                  发行方证书 2026-07-14 到期且无时间戳 → 全新安装默认不信任
VSTO 信任项                ``HKCU\\...\\VSTO\\Security\\Inclusion``（Url 必须指到 .vsto）
DTD/XSL 资源              预览依赖文档旁的 ``dtdandxsl``
=========================  ===================================================

用法::

    python tools/patent.py env              # 人类可读
    python tools/patent.py env --json       # 机器可读
    python tools/patent.py env --com        # additionally launch Word and check the add-in connects
    python tools/patent.py env --fix-trust  # write the inclusion entry (current user, no elevation)
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

OK = "ok"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

_DSIG = {"d": "http://www.w3.org/2000/09/xmldsig#"}
_VSTO_INCLUSION = r"SOFTWARE\Microsoft\VSTO\Security\Inclusion"
_INCLUSION_GUID = "{B7E4C2A1-6F3D-4C9E-9A21-5D7B8C4E2F60}"
_ADDIN = r"SOFTWARE\Microsoft\Office\Word\Addins\CNIPR.PatentTool"
_ADDIN_PROGID = "CNIPR.PatentTool"


def _winreg():
    import winreg  # noqa: PLC0415  (only exists on Windows)

    return winreg


def _read_reg(root_name: str, path: str, value: str | None = None):
    try:
        winreg = _winreg()
        root = getattr(winreg, root_name)
        with winreg.OpenKey(root, path) as handle:
            return winreg.QueryValueEx(handle, value)[0] if value else _enum_values(handle, winreg)
    except (ImportError, OSError):
        return None


def _enum_values(handle, winreg) -> dict:
    values = {}
    index = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(handle, index)
        except OSError:
            break
        values[name] = value
        index += 1
    return values


def _list_reg_subkeys(root_name: str, path: str) -> list[str]:
    try:
        winreg = _winreg()
        root = getattr(winreg, root_name)
        with winreg.OpenKey(root, path) as handle:
            names, index = [], 0
            while True:
                try:
                    names.append(winreg.EnumKey(handle, index))
                except OSError:
                    break
                index += 1
            return names
    except (ImportError, OSError):
        return []


def _write_reg(root_name: str, path: str, values: dict) -> None:
    winreg = _winreg()
    root = getattr(winreg, root_name)
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_ALL_ACCESS) as handle:
        for name, value in values.items():
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str = ""
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    os: str = ""
    checks: list[Check] = field(default_factory=list)
    status: str = "unknown"
    actions: list[str] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    def to_dict(self) -> dict:
        return {
            "os": self.os,
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "actions": self.actions,
        }


# --------------------------------------------------------------------------
# 探测：Office / WPS
# --------------------------------------------------------------------------


def detect_office() -> dict:
    cfg = _read_reg("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration") or {}
    exe = _read_reg(
        "HKEY_LOCAL_MACHINE",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WINWORD.EXE",
    )
    candidates = [
        Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"),
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE"),
    ]
    found = next((p for p in candidates if p.exists()), None)
    if exe and isinstance(exe, dict):
        exe = exe.get("")
        if exe:
            found = Path(str(exe).strip('"')) if Path(str(exe).strip('"')).exists() else found
    return {
        "installed": bool(cfg) or bool(found),
        "version": cfg.get("VersionToReport") or cfg.get("ClientVersionToReport"),
        "edition": cfg.get("ProductReleaseIds"),
        "platform": cfg.get("Platform"),
        "exe": str(found) if found else None,
        "vsto_runtime": _vsto_runtime_version(),
    }


def _vsto_runtime_version() -> str | None:
    for path in (
        r"SOFTWARE\Microsoft\VSTO Runtime Setup\v4R",
        r"SOFTWARE\WOW6432Node\Microsoft\VSTO Runtime Setup\v4R",
    ):
        info = _read_reg("HKEY_LOCAL_MACHINE", path)
        if isinstance(info, dict) and info.get("Version"):
            return str(info["Version"])
    uninstall = _uninstall_entries()
    for name, version in uninstall.items():
        if "VSTO" in name or "Visual Studio 2010 Tools for Office" in name:
            return version
    return None


def detect_wps() -> dict:
    versions = {
        name: version for name, version in _uninstall_entries().items() if name.upper().startswith("WPS")
    }
    exe = None
    app_path = _read_reg(
        "HKEY_LOCAL_MACHINE",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\wps.exe",
    ) or _read_reg(
        "HKEY_LOCAL_MACHINE",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wps.exe",
    )
    if isinstance(app_path, dict) and app_path.get(""):
        exe = str(app_path[""]).strip('"')
    return {"installed": bool(versions), "versions": versions, "exe": exe}


def _uninstall_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for root in ("HKEY_LOCAL_MACHINE", "HKEY_CURRENT_USER"):
        for suffix in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                       r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            for sub in _list_reg_subkeys(root, suffix):
                info = _read_reg(root, f"{suffix}\\{sub}") or {}
                name = str(info.get("DisplayName") or "").strip()
                if name:
                    entries[name] = str(info.get("DisplayVersion") or "")
    return entries


# --------------------------------------------------------------------------
# 探测：官方插件
# --------------------------------------------------------------------------


def detect_tool() -> dict:
    entries = _uninstall_entries()
    arp = {name: version for name, version in entries.items() if "转XML" in name or "XML编辑器" in name}
    home = Path(os.environ.get("LOCALAPPDATA", "")) / "CNIPR"
    dirs = sorted(p for p in home.glob("PatentTool_*") if p.is_dir()) if home.exists() else []
    data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "PatentTool"
    return {
        "installed": bool(arp) or any((d / "PatentTool.vsto").exists() for d in dirs),
        "arp": arp,
        "dirs": [str(d) for d in dirs],
        "vsto": str(dirs[-1] / "PatentTool.vsto") if dirs and (dirs[-1] / "PatentTool.vsto").exists() else None,
        "dtdandxsl": str(data / "dtdandxsl") if (data / "dtdandxsl").exists() else None,
    }


def detect_addin() -> dict:
    for root in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
        info = _read_reg(root, _ADDIN)
        if isinstance(info, dict) and info:
            return {
                "registered": True,
                "hive": root,
                "load_behavior": info.get("LoadBehavior"),
                "manifest": str(info.get("Manifest") or ""),
            }
    return {"registered": False}


def detect_vsto_inclusion() -> list[dict]:
    entries = []
    for guid in _list_reg_subkeys("HKEY_CURRENT_USER", _VSTO_INCLUSION):
        info = _read_reg("HKEY_CURRENT_USER", f"{_VSTO_INCLUSION}\\{guid}") or {}
        if not isinstance(info, dict):
            continue
        entries.append(
            {
                "guid": guid,
                "url": info.get("Url"),
                "name": info.get("Name"),
                "public_key": bool(info.get("PublicKey")),
            }
        )
    return entries


def detect_signature(vsto: str | None) -> dict:
    """读 ClickOnce 清单签名：证书到期时间、是否有时间戳。"""
    if not vsto or not Path(vsto).exists():
        return {"available": False}
    try:
        raw = Path(vsto).read_text(encoding="utf-8-sig", errors="replace")
        root = ET.fromstring(raw)
    except (OSError, ET.ParseError) as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)[:120]}
    has_signature = root.find(".//d:Signature", _DSIG) is not None
    certificate = root.find(".//d:X509Certificate", _DSIG)
    return {
        "available": True,
        "signed": has_signature,
        "has_timestamp": "SigningTime" in raw or "TimeStamp" in raw,
        "expired": _cert_expired(certificate.text if certificate is not None else None),
        "certificate": certificate.text.strip()[:40] if certificate is not None and certificate.text else None,
    }


def _cert_expired(der_base64: str | None) -> bool | None:
    if not der_base64:
        return None
    try:
        import base64
        import datetime as dt  # noqa: PLC0415

        der = base64.b64decode(der_base64.split()[0] + "=" * (-len(der_base64.split()[0]) % 4))
        # 最小化解析：用 cryptography 若可用，否则从 DER 里找 UTCTime 太不可靠
        try:
            from cryptography import x509  # noqa: PLC0415
        except ImportError:
            return None
        cert = x509.load_der_x509_certificate(der)
        return cert.not_valid_after_utc < dt.datetime.now(dt.timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def inclusion_key(vsto: str) -> str | None:
    """从清单 KeyInfo 取 RSA 公钥，格式与 VSTO 信任项里的 PublicKey 一致。"""
    try:
        root = ET.fromstring(Path(vsto).read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, ET.ParseError):
        return None
    node = root.find(".//d:KeyValue/d:RSAKeyValue", _DSIG)
    if node is None:
        return None
    modulus = node.find("d:Modulus", _DSIG)
    exponent = node.find("d:Exponent", _DSIG)
    if modulus is None or exponent is None or not modulus.text or not exponent.text:
        return None
    return (
        f"<RSAKeyValue><Modulus>{modulus.text.strip()}</Modulus>"
        f"<Exponent>{exponent.text.strip()}</Exponent></RSAKeyValue>"
    )


def fix_trust(tool: dict | None = None) -> dict:
    """写当前用户的 VSTO 信任项。Url 必须指到 .vsto 文件，指目录无效。"""
    tool = tool or detect_tool()
    vsto = tool.get("vsto")
    if not vsto:
        return {"fixed": False, "reason": "未找到 PatentTool.vsto，先安装官方工具"}
    key = inclusion_key(vsto)
    if not key:
        return {"fixed": False, "reason": "清单里没有 RSAKeyValue，无法自动信任"}
    url = Path(vsto).resolve().as_uri()
    _write_reg(
        "HKEY_CURRENT_USER",
        f"{_VSTO_INCLUSION}\\{_INCLUSION_GUID}",
        {"Url": url, "PublicKey": key, "Name": "PatentTool"},
    )
    return {"fixed": True, "url": url, "key_chars": len(key)}


def probe_word_com() -> dict:
    """启动 Word 看插件是否真的 Connect（慢，默认不跑）。"""
    try:
        import pythoncom  # noqa: PLC0415
        import win32com.client  # noqa: PLC0415
    except ImportError:
        return {"available": False, "error": "pywin32 未安装"}
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        try:
            add_in = app.COMAddIns.Item(_ADDIN_PROGID)
            connected = bool(add_in.Connect)
            if not connected:
                try:
                    add_in.Connect = True
                    connected = bool(add_in.Connect)
                except Exception:  # noqa: BLE001
                    pass
            return {"available": True, "connected": connected}
        finally:
            app.Quit()
            pythoncom.CoUninitialize()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"[:160]}


# --------------------------------------------------------------------------
# 汇总
# --------------------------------------------------------------------------


def detect(with_com: bool = False) -> Report:
    is_windows = platform.system() == "Windows"
    report = Report(os=f"{platform.system()} {platform.release()} ({platform.version()})")
    if not is_windows:
        report.add(Check("os", "操作系统", FAIL, report.os, "官方工具只支持 Windows 10+；其他系统只能用系统在线编辑功能"))
        report.status = "unsupported"
        report.actions.append("换一台 Windows 10+ 机器，或在专利业务办理系统里在线编辑申请文件")
        return report

    build = int(re.sub(r"\D", "", platform.version().split(".")[-1]) or 0)
    report.add(
        Check(
            "os",
            "操作系统",
            OK if build >= 10240 else WARN,
            report.os,
            "官方要求 Windows 10（build 10240）及以上",
        )
    )

    office = detect_office()
    wps = detect_wps()
    if office["installed"]:
        report.add(
            Check(
                "office",
                "Microsoft Office",
                OK,
                f"{office.get('edition') or 'Office'} {office.get('version') or ''} / {office.get('platform') or ''}",
                "插件是 VSTO 加载项，需要 Word 2013+；Word 位数要与插件一致",
            )
        )
    elif wps["installed"]:
        report.add(
            Check(
                "office",
                "Office / WPS 宿主",
                WARN,
                f"只有 WPS：{', '.join(wps['versions']) or '未知版本'}",
                "个人版 WPS 不会加载「专利处理」；需要 WPS 2015 专业版以上或装 Word 2013+",
            )
        )
    else:
        report.add(Check("office", "Office / WPS 宿主", FAIL, "未发现 Word 或 WPS", "先安装 Microsoft 365 / Office 2013+ 或 WPS 专业版"))

    runtime = office.get("vsto_runtime")
    report.add(
        Check(
            "vsto",
            "VSTO 4.0 Runtime",
            OK if runtime else WARN,
            runtime or "未检测到",
            "安装 Office 或官方安装包里的 vstor_redist.exe 会带上",
        )
    )

    tool = detect_tool()
    if tool["installed"]:
        report.add(
            Check(
                "tool",
                "官方 WORD 转 XML 编辑器",
                OK,
                f"{', '.join(tool['arp']) or '已安装'}（{tool['dirs'][-1] if tool['dirs'] else '目录未知'}）",
                "安装需管理员；MSI 启动条件要求传 SETUPEXEDIR，直装会报「只能从 bootstrapper 运行」",
            )
        )
    else:
        report.add(
            Check(
                "tool",
                "官方 WORD 转 XML 编辑器",
                FAIL,
                "未安装",
                "管理员运行 tools/cnipa_install.ps1（或 cnipa_env --install-hint 看步骤）",
            )
        )

    addin = detect_addin()
    if addin.get("registered"):
        report.add(
            Check(
                "addin",
                "插件注册",
                OK,
                f"{addin['hive']} LoadBehavior={addin.get('load_behavior')}",
                "LoadBehavior=3 表示随 Word 启动加载",
            )
        )
    else:
        report.add(Check("addin", "插件注册", WARN, "未注册", "工具装好后重开 Word；仍未出现则查安装是否 1603 回滚"))

    inclusion = detect_vsto_inclusion()
    trusted = [e for e in inclusion if str(e.get("url") or "").endswith(".vsto") and e.get("public_key")]

    signature = detect_signature(tool.get("vsto"))
    if signature.get("available"):
        expired = signature.get("expired") and not signature.get("has_timestamp")
        if expired and not trusted:
            report.add(
                Check(
                    "signature",
                    "清单签名",
                    WARN,
                    "证书已过期且无时间戳 → 全新安装默认不信任",
                    "这是发行方打包缺陷；用 --fix-trust 写当前用户信任项",
                )
            )
        elif expired:
            report.add(
                Check(
                    "signature",
                    "清单签名",
                    OK,
                    "证书已过期且无时间戳，但已用 VSTO 信任项绕过",
                    "换新版安装包或重装后需重跑 --fix-trust",
                )
            )
        else:
            report.add(Check("signature", "清单签名", OK, "证书有效或带时间戳"))
    else:
        report.add(Check("signature", "清单签名", SKIP, "未找到 PatentTool.vsto"))
    if trusted:
        report.add(Check("trust", "VSTO 信任项", OK, trusted[-1]["url"], "指到 .vsto 文件才生效；指目录无效"))
    elif inclusion:
        report.add(Check("trust", "VSTO 信任项", WARN, "有信任项但 Url 不是 .vsto", "改正 Url 或重跑 --fix-trust"))
    else:
        report.add(Check("trust", "VSTO 信任项", WARN, "无", "运行 --fix-trust（当前用户级，不需要管理员）"))

    if tool.get("dtdandxsl"):
        report.add(Check("dtdandxsl", "DTD/XSL 资源", OK, tool["dtdandxsl"], "预览要求文档同级或上级有 dtdandxsl"))
    else:
        report.add(Check("dtdandxsl", "DTD/XSL 资源", WARN, "C:\\ProgramData\\PatentTool\\dtdandxsl 不存在", "从安装目录的 dtdandxsl.zip 解出"))

    if with_com:
        com = probe_word_com()
        if com.get("available"):
            report.add(
                Check(
                    "com",
                    "Word 实际加载插件",
                    OK if com.get("connected") else FAIL,
                    "已连接" if com.get("connected") else "未连接",
                    "" if com.get("connected") else "先修信任项，再确认 Word 位数与插件一致",
                )
            )
        else:
            report.add(Check("com", "Word 实际加载插件", SKIP, com.get("error", "未检测")))

    statuses = {c.status for c in report.checks}
    if FAIL in statuses:
        report.status = "not-ready"
    elif WARN in statuses:
        report.status = "degraded"
    else:
        report.status = "ready"

    if report.status == "ready":
        report.actions.append("环境就绪：可直接用官方工具「一键添加标记 → 单书XML转换」")
    else:
        if not tool["installed"]:
            report.actions.append("1) 管理员安装官方工具：powershell -File tools/cnipa_install.ps1")
        if tool["installed"] and not trusted:
            report.actions.append("2) 修插件信任：python tools/patent.py env --fix-trust")
        report.actions.append("3) 装/修完重跑本命令，再加 --com 确认 Word 里真的加载了「专利处理」")
    return report


def render(report: Report) -> str:
    icon = {OK: "✓", WARN: "!", FAIL: "✗", SKIP: "·"}
    lines = [f"环境检测：{report.os}", ""]
    for check in report.checks:
        lines.append(f"  {icon.get(check.status, '?')} {check.title}: {check.detail}")
        if check.status in (WARN, FAIL) and check.hint:
            lines.append(f"      → {check.hint}")
    lines.append("")
    lines.append(f"结论：{report.status}")
    for action in report.actions:
        lines.append(f"  {action}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="检测官方 WORD 转 XML 编辑器与宿主环境")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--com", action="store_true", help="启动 Word 实际验证插件 Connect（较慢）")
    parser.add_argument("--fix-trust", action="store_true", help="写当前用户的 VSTO 信任项")
    args = parser.parse_args(argv)

    if args.fix_trust:
        result = fix_trust()
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("已写入 VSTO 信任项：" + result["url"] if result.get("fixed") else f"未能修复：{result.get('reason')}")
        if not result.get("fixed"):
            return 1

    report = detect(with_com=args.com)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) if args.json else render(report))
    return {"ready": 0, "degraded": 2, "not-ready": 1, "unsupported": 3}.get(report.status, 1)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
