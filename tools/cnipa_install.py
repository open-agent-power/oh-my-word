"""安装/修复官方「WORD 转 XML 编辑器」，装完自动补齐 VSTO 信任项。

为什么需要这个脚本（都是 2026-10-25 实机踩出来的）：

1. 官方 MSI 的启动条件是 ``SETUPEXEDIR OR REMOVE="ALL"``；直接 ``msiexec /i`` 会
   报「This package can only be run from a bootstrapper」。传 ``SETUPEXEDIR=<解包目录>``
   才能继续。
2. 安装要写 ``C:\\ProgramData\\PatentTool``（Users 只读），所以**必须管理员**；
   非管理员跑到一半会以 1603 回滚，并留下删不掉的只读残留。
3. 失败半装的残留必须清掉，否则下次安装在同一批文件上报 1310/1603。
4. 装完后插件默认**不加载**：发行方清单签名证书 2026-07-14 到期且没有时间戳，
   VSTO 报「签名清单或证书未知」。需要用当前用户级的 Inclusion 信任项绕过——
   不需要再提权。``Url`` 必须指到 ``PatentTool.vsto`` 文件，指目录无效。

用法::

    python tools/cnipa_install.py --package downloads/word转xml-安装包-2025.12.18.zip
    python tools/cnipa_install.py --package <已解包目录>
    python tools/cnipa_install.py --verify-only

脚本自身会请求一次 UAC（ShellExecuteW runas）来跑 MSI 部分；没有管理员也可以
先用 ``--verify-only`` 看缺什么，或手动装完再跑 ``python tools/patent.py env --fix-trust``。
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

PACKAGE_HINT = "从 https://cponline.cnipa.gov.cn 的「工具下载」获取 word转xml-安装包-*.zip"
PROGRAM_DATA_TOOL = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "PatentTool"


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _log_dir() -> Path | None:
    root = _root()
    candidates = [
        Path(os.environ.get("LOCALAPPDATA") or "") / "cnipa-install" / "logs",
        Path(tempfile.gettempdir()) / "cnipa-install" / "logs",
        Path.home() / ".cnipa-install" / "logs",
        root / ".cache" / "cnipa-install" / "logs",
    ]
    for target in candidates:
        if not target.is_absolute():
            continue
        try:
            if root in target.parents:  # don't litter the repo
                continue
            target.mkdir(parents=True, exist_ok=True)
            return target
        except OSError:
            continue
    return None


def _log_path() -> Path | None:
    directory = _log_dir()
    return directory / f"install-{time.strftime('%Y%m%d-%H%M%S')}.log" if directory else None


class Log:
    def __init__(self) -> None:
        self.path = _log_path()
        if self.path is not None:
            print(f"日志：{self.path}")

    def __call__(self, message: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {message}"
        print(line)
        if self.path is None:
            return
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except AttributeError:
        return False


def elevate(argv: list[str]) -> int:
    """用 UAC 重新启动自己；返回父进程的退出码。"""
    executable = sys.executable
    params = " ".join(f'"{a}"' for a in [str(Path(__file__).resolve()), *argv])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    if result <= 32:
        print(f"提权失败（ShellExecuteW={result}）；请以管理员身份打开终端后重跑。")
        return 4
    return 0


def locate_package(hint: str | None) -> Path:
    if hint:
        path = Path(hint).expanduser()
        if path.exists():
            return path
        raise SystemExit(f"找不到安装包：{path}\n{PACKAGE_HINT}")
    candidates = []
    for base in (Path.home() / "Downloads", Path.home() / "Desktop", _root() / "downloads", _root() / "third_party"):
        if base.exists():
            candidates.extend(sorted(base.glob("*word*XML*.zip"), key=lambda p: p.stat().st_mtime, reverse=True))
            candidates.extend(sorted(base.glob("*转xml*.zip"), key=lambda p: p.stat().st_mtime, reverse=True))
    if candidates:
        return candidates[0]
    raise SystemExit(f"没找到安装包，用 --package 指定。{PACKAGE_HINT}")


def unpack(package: Path, work: Path) -> Path:
    if package.is_dir():
        return package
    work.mkdir(parents=True, exist_ok=True)
    if any(work.rglob("*.msi")):
        return work
    with zipfile.ZipFile(package) as archive:
        archive.extractall(work)
    return work


def find_msi(root: Path) -> Path:
    msins = sorted(root.rglob("*.msi"))
    if not msins:
        raise SystemExit(f"{root} 里没有 .msi，确认这是官方安装包")
    return msins[0]


def remove_tree(path: Path, log: Log, attempts: int = 6) -> bool:
    """删掉失败半装留下的只读残留（rd /s /q + 重试 + \\\\?\\ 长路径删除）。"""
    for attempt in range(1, attempts + 1):
        if not path.exists():
            return True
        log(f"清理残留 {path}（第 {attempt} 次）")
        subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(path)], capture_output=True, text=True)
        if not path.exists():
            return True
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return True
        try:
            os.system(f'cmd /c rd /s /q "\\\\?\\{path}"')
        except OSError:
            pass
        if not path.exists():
            return True
        time.sleep(3)
    return not path.exists()


def install(package: Path, log: Log) -> int:
    work = Path(tempfile.gettempdir()) / "cnipa-tool-package"
    root = unpack(package, work)
    msi = find_msi(root)
    log(f"安装包：{root}")
    log(f"MSI：{msi.name}（{msi.stat().st_size:,} 字节）")

    if PROGRAM_DATA_TOOL.exists() and not remove_tree(PROGRAM_DATA_TOOL, log):
        log("残留删不掉：先手动 cmd /c rd /s /q C:\\ProgramData\\PatentTool 再重试")
        return 5

    msi_log = _log_path()
    msi_log = msi_log.with_suffix(".msi.log") if msi_log else Path(tempfile.gettempdir()) / "cnipa-msi.log"
    log("运行 msiexec（SETUPEXEDIR 必传，否则启动条件直接拒绝）")
    completed = subprocess.run(
        [
            "msiexec",
            "/i",
            str(msi),
            f"SETUPEXEDIR={root}",
            "ALLUSERS=1",
            "/qn",
            "/norestart",
            "/l*v",
            str(msi_log),
        ],
        capture_output=True,
        text=True,
    )
    log(f"msiexec 退出码 {completed.returncode}；日志 {msi_log}")
    if completed.returncode != 0:
        log("安装失败。常见原因：非管理员（1603/1310）、ProgramData 残留、杀软拦截")
        return completed.returncode or 6

    if not (PROGRAM_DATA_TOOL / "dtdandxsl").exists():
        log("提示：C:\\ProgramData\\PatentTool\\dtdandxsl 未出现，预览会缺 DTD/XSL")
    return 0


def fix_trust(log: Log) -> bool:
    sys.path.insert(0, str(_root()))
    from oh_my_patent import cnipa_env  # noqa: PLC0415

    tool = cnipa_env.detect_tool()
    if not tool.get("installed"):
        log("还没装工具，跳过信任项")
        return False
    result = cnipa_env.fix_trust(tool)
    if result.get("fixed"):
        log(f"已写 VSTO 信任项：{result['url']}")
        return True
    log(f"信任项未写入：{result.get('reason')}")
    return False


def verify(log: Log) -> int:
    sys.path.insert(0, str(_root()))
    from oh_my_patent import cnipa_env  # noqa: PLC0415

    report = cnipa_env.detect(with_com=True)
    print(cnipa_env.render(report))
    log(f"环境结论：{report.status}")
    return {"ready": 0, "degraded": 2, "not-ready": 1, "unsupported": 3}.get(report.status, 1)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="安装官方 WORD 转 XML 编辑器并修复插件信任")
    parser.add_argument("--package", help="官方安装包 zip 或已解包的目录")
    parser.add_argument("--verify-only", action="store_true", help="只检测，不安装")
    parser.add_argument("--no-elevate", action="store_true", help="不提权，只做能做的部分")
    parser.add_argument("--json", action="store_true", help="安装后输出 JSON 检测结果")
    args = parser.parse_args(argv)

    log = Log()

    if args.verify_only:
        return verify(log)

    if not is_admin() and not args.no_elevate:
        log("需要管理员安装 MSI，正在请求 UAC…")
        child = [a for a in (argv or sys.argv[1:]) if a not in ("--no-elevate",)]
        if "--package" not in child and args.package:
            child += ["--package", args.package]
        code = elevate(child)
        log("如果没看到 UAC 弹窗，请以管理员身份重跑本脚本。")
        return code

    package = locate_package(args.package)
    code = install(package, log)
    if code:
        return code

    fixed = fix_trust(log)
    log("信任项已就绪" if fixed else "信任项未就绪，可用 python tools/patent.py env --fix-trust 重试")
    return verify(log)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
