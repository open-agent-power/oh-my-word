"""在 Word 里自动执行官方工具的「一键添加标记 → 单书XML转换」。

官方 WORD 转 XML 编辑器是 VSTO 加载项，没有命令行接口；这里用 UI Automation 点它
的 ribbon 按钮，属于**实验性**自动化：只在 Windows + Office/WPS 专业版 + 插件已信任时可用，
失败要能明确告诉人「卡在哪一步」，不能假装成功。

实机验证过的路径（2026-10-25，Windows 11 + Microsoft 365 + 官方 V4.3）：

1. 用 Word COM 打开 docx（不要用 `Start-Process WINWORD.EXE`，那样容易进受保护的视图）；
2. 选「专利处理」页签；只有「五书XML转换」时先点「显示高级菜单」；
3. 点「一键添加标记」，再点「单书XML转换」；
4. 产物落在 docx 同级 `<文件名>/<编码>/<编码>.xml`（附图另有 JPG）。

已知会失败并给提示的情况：图号画在图片里或文档不是单书 → 工具弹「请先添加标记」；
插件未加载 → 找不到页签或按钮。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

OK, WARN = "ok", "warn"

CODE_BY_BOOK = {
    "claims": "100001",
    "description": "100002",
    "drawings": "100003",
    "abstract": "100004",
}
CODE_LABELS = {
    "100001": "权利要求书",
    "100002": "说明书",
    "100003": "说明书附图",
    "100004": "说明书摘要",
}


class ConvertError(RuntimeError):
    """转换失败；消息要能直接给人看（含下一步建议）。"""


def clean_name(name: str) -> str:
    """去掉 ribbon 名字里的零宽字符，便于匹配。"""
    return (name or "").replace("\u200b", "").replace("\u200c", "").strip()


def code_from_filename(path: Path) -> str | None:
    match = re.match(r"^(1000\d{2})", path.stem)
    return match.group(1) if match and match.group(1) in CODE_LABELS else None


def code_from_xml(xml: Path) -> str | None:
    """转换后按根元素子节点判定文书类型。"""
    try:
        text = xml.read_text(encoding="utf-8-sig", errors="replace")[:4000]
    except OSError:
        return None
    for tag, code in (
        ("<cn-claims", CODE_BY_BOOK["claims"]),
        ("<cn-description", CODE_BY_BOOK["description"]),
        ("<cn-drawings", CODE_BY_BOOK["drawings"]),
        ("<cn-abstract", CODE_BY_BOOK["abstract"]),
    ):
        if tag in text:
            return code
    return None


def output_root(docx: Path) -> Path:
    return docx.parent / docx.stem


def find_outputs(docx: Path, since: float, timeout: float = 0) -> list[Path]:
    """找 docx 同级、转换后生成的 XML。"""
    root = output_root(docx)
    deadline = time.time() + timeout
    while True:
        hits = sorted(root.rglob("*.xml")) if root.exists() else []
        fresh = [p for p in hits if p.stat().st_mtime >= since - 1]
        if fresh or time.time() >= deadline:
            return fresh
        time.sleep(1)


def dtd_path(near: Path | None = None) -> Path | None:
    """找官方 DTD：文档旁边的 dtdandxsl → ProgramData → 安装目录的 dtdandxsl.zip 解包。"""
    import os
    import tempfile
    import zipfile

    name = "cn-application-body-20080416.dtd"
    candidates: list[Path] = []
    if near is not None:
        for parent in list(near.parents)[:4]:
            candidates.append(parent / "dtdandxsl" / name)
    candidates.append(
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "PatentTool" / "dtdandxsl" / name
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate

    home = Path(os.environ.get("LOCALAPPDATA", "")) / "CNIPR"
    for install in sorted(home.glob("PatentTool_*")):
        archive = install / "dtdandxsl.zip"
        if not archive.exists():
            continue
        target = Path(tempfile.mkdtemp(prefix="cnipa-dtd-"))
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(target)
        extracted = target / name
        if extracted.exists():
            return extracted
    return None


def validate(xml: Path) -> dict:
    """用官方 DTD 校验；缺 lxml 或缺 DTD 时如实说明，不当作通过。"""
    try:
        from lxml import etree  # noqa: PLC0415
    except ImportError:
        return {"validated": False, "reason": "lxml 未安装"}
    dtd = dtd_path(xml)
    if dtd is None:
        return {"validated": False, "reason": "找不到官方 DTD（C:\\ProgramData\\PatentTool\\dtdandxsl）"}
    data = re.sub(r"<!DOCTYPE[^>]*>", "", xml.read_text(encoding="utf-8-sig"), count=1)
    root = etree.fromstring(data.encode("utf-8"))
    schema = etree.DTD(str(dtd))
    valid = schema.validate(root)
    errors = [str(e) for e in schema.error_log.filter_from_errors()][:3]
    return {"validated": True, "valid": bool(valid), "errors": errors}


# --------------------------------------------------------------------------
# UI Automation（Windows 专用，全部惰性导入）
# --------------------------------------------------------------------------


def _uia():
    try:
        import comtypes.client as cc  # noqa: PLC0415
        from comtypes import GUID  # noqa: PLC0415
        import win32gui  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 仅 Windows 有依赖
        raise ConvertError(
            "缺少 Windows 依赖：请 pip install pywin32 comtypes（本项目 extras: [windows]）"
        ) from exc
    cc.GetModule(r"C:\Windows\System32\UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as UIA  # noqa: PLC0415

    automation = cc.CreateObject(GUID("{FF48DBA4-60EF-4201-AA87-54103EEF594E}"), interface=UIA.IUIAutomation)
    return automation, UIA, win32gui


def _word_window(win32gui) -> tuple[int, str] | None:
    found: list[tuple[int, str]] = []

    def callback(hwnd, _):
        if win32gui.GetClassName(hwnd) == "OpusApp" and win32gui.GetWindowText(hwnd).strip():
            found.append((hwnd, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(callback, None)
    return found[0] if found else None


def _buttons(automation, UIA, hwnd: int) -> list[tuple[str, object]]:
    root = automation.ElementFromHandle(hwnd)
    condition = automation.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, 50000)
    found = root.FindAll(UIA.TreeScope_Descendants, condition)
    items = []
    for index in range(found.Length):
        element = found.GetElement(index)
        name = clean_name(element.CurrentName)
        if name:
            items.append((name, element))
    return items


def _click(automation, UIA, hwnd: int, wanted: str) -> bool:
    for name, element in _buttons(automation, UIA, hwnd):
        if wanted in name:
            element.GetCurrentPattern(UIA.UIA_InvokePatternId).QueryInterface(
                UIA.IUIAutomationInvokePattern
            ).Invoke()
            return True
    return False


def _select_patent_tab(automation, UIA, hwnd: int) -> bool:
    root = automation.ElementFromHandle(hwnd)
    condition = automation.CreatePropertyCondition(UIA.UIA_ControlTypePropertyId, 50019)
    tabs = root.FindAll(UIA.TreeScope_Descendants, condition)
    for index in range(tabs.Length):
        tab = tabs.GetElement(index)
        if "专利" in clean_name(tab.CurrentName):
            tab.GetCurrentPattern(UIA.UIA_SelectionItemPatternId).QueryInterface(
                UIA.IUIAutomationSelectionItemPattern
            ).Select()
            return True
    return False


def convert(docx: Path, timeout: float = 180.0, keep: bool = False, do_validate: bool = False) -> dict:
    import pythoncom  # noqa: PLC0415
    import win32com.client  # noqa: PLC0415

    docx = docx.resolve()
    if not docx.exists():
        raise ConvertError(f"找不到文件：{docx}")

    automation, UIA, win32gui = _uia()
    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("Word.Application")
    app.Visible = True
    app.DisplayAlerts = 0
    report: dict = {"docx": str(docx), "steps": []}
    started = time.time()
    try:
        doc = app.Documents.Open(str(docx), ConfirmConversions=False, ReadOnly=False, AddToRecentFiles=False)
        time.sleep(6)
        window = _word_window(win32gui)
        if window is None:
            raise ConvertError("没找到 Word 窗口；确认 Word 没有停在受保护的视图或登录提示")
        hwnd = window[0]
        report["window"] = window[1]

        if not _select_patent_tab(automation, UIA, hwnd):
            raise ConvertError("没有「专利处理」页签：插件未加载。先跑 python tools/patent.py env --com")
        report["steps"].append({"tab": "专利处理", "ok": True})
        time.sleep(1)

        names = [name for name, _ in _buttons(automation, UIA, hwnd)]
        if not any("一键添加标记" in n for n in names):
            if _click(automation, UIA, hwnd, "显示高级菜单"):
                time.sleep(2)
                report["steps"].append({"click": "显示高级菜单", "ok": True})
            names = [name for name, _ in _buttons(automation, UIA, hwnd)]
        if not any("一键添加标记" in n for n in names):
            raise ConvertError("找不到「一键添加标记」按钮：确认装的是官方 V4.3 且是 Word 版插件")

        if not _click(automation, UIA, hwnd, "一键添加标记"):
            raise ConvertError("点击「一键添加标记」失败")
        report["steps"].append({"click": "一键添加标记", "ok": True})
        time.sleep(6)

        if not _click(automation, UIA, hwnd, "单书XML转换"):
            raise ConvertError("找不到「单书XML转换」按钮")
        report["steps"].append({"click": "单书XML转换", "ok": True})

        outputs = find_outputs(docx, started, timeout=timeout)
        if not outputs:
            popup = [name for name, _ in _buttons(automation, UIA, hwnd) if name == "确定"]
            if popup:
                _click(automation, UIA, hwnd, "确定")
                raise ConvertError(
                    "工具提示「请先添加标记」后中止：通常是图号画在图片里，或这份文档不是单书。"
                    "图号改成图片外的正文「图N」后重试；一份文档只放一本书。"
                )
            raise ConvertError(f"{int(timeout)} 秒内没有生成 XML：看 Word 窗口是否有弹窗或报错")

        code = code_from_filename(docx) or code_from_xml(outputs[0])
        report["code"] = code
        report["label"] = CODE_LABELS.get(code or "", "未知")
        report["files"] = [str(p) for p in outputs]
        if do_validate:
            report["validation"] = [{"file": str(p), **validate(p)} for p in outputs]
        doc.Close(SaveChanges=0)
        return report
    finally:
        if not keep:
            try:
                app.Quit()
            except Exception:  # noqa: BLE001
                pass
        pythoncom.CoUninitialize()


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="自动执行官方工具的标记与单书转换（实验性）")
    parser.add_argument("docx", type=Path, help="单个文书的 docx（文件名以 100001 等开头最好）")
    parser.add_argument("--timeout", type=float, default=180.0, help="等待 XML 生成的秒数")
    parser.add_argument("--keep", action="store_true", help="结束后不关闭 Word（排查用）")
    parser.add_argument("--validate", action="store_true", help="转换后用官方 DTD 校验")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    try:
        report = convert(args.docx, args.timeout, args.keep, args.validate)
    except ConvertError as exc:
        print(f"转换失败：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"已转换：{report.get('code')} {report.get('label')}")
        for path in report.get("files", []):
            print(f"  {path}")
        for item in report.get("validation", []):
            status = "通过" if item.get("valid") else "未通过"
            print(f"  DTD {status}：{Path(item['file']).name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
