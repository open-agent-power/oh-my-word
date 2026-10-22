"""Finite public-source reuse trial: copyright preparation + patent draft.

This runner only creates draft materials. It does not attest ownership,
inventorship, novelty, or legal eligibility, and never finalizes a package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


REPO = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = Path(r"D:\XiangMuLuoDi\Development\word-skills-reuse-trial\public-project")
DEFAULT_OUT = Path(r"D:\XiangMuLuoDi\Development\word-skills-reuse-trial\business-trial-baseline-final")
DEFAULT_SOFFICE = Path(r"D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\.archive\oh-my-technology-0.1.0\.tools\LibreOffice\program\soffice.exe")
DEFAULT_PDFTOPPM = Path(r"C:\Users\chenfeng\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")


def run(args: list[str], log: list[dict], *, stdin: str | None = None,
        cwd: Path = REPO) -> str:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run(args, cwd=cwd, input=stdin, text=True, encoding="utf-8",
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=240)
    log.append({"command": args, "returncode": p.returncode, "output": p.stdout})
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(args)}\n{p.stdout}")
    return p.stdout


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manual_text(phrase: str, cli_output: str) -> str:
    return f"""# Python Slugify 8.0.4 操作说明（演示草稿）

## 软件用途

本项目提供 Python 文本 slug 处理函数及命令行入口。输入文本经字符规范化和规则处理后，输出适合用作 URL 路径片段或标识的文本。本说明依据公开源码及下方记录的本机命令运行结果编写；该项目及其代码的权利归属未由本次演示确认。

## 运行环境与启动

项目 README 记载通过 pip 安装 `python-slugify`。命令行入口在 `slugify/__main__.py`，安装后可运行 `slugify TEXT`；源码目录中也可运行 `python -m slugify TEXT`。基础 transliteration 依赖由 `setup.py` 声明为 `text-unidecode>=1.3`。

## 命令操作

1. 打开命令提示符或终端，进入项目目录。
2. 对普通文本运行 `python -m slugify "C'est déjà l'été &amp; café!"`。
3. 需要保留 Unicode 字符时增加 `--allow-unicode`；需要限制结果长度时使用 `--max-length N`，可配合 `--word-boundary`。
4. 阅读终端输出。命令成功时标准输出显示生成的 slug；无输入时输出空行。参数说明可用 `python -m slugify --help` 查看。

## 本次实际运行记录

下列命令由本地 Python 运行，输出按文字记录排版，不是原生终端截图。

```text
python -m slugify "C'est déjà l'été &amp; café!"
{cli_output.splitlines()[0] if cli_output.splitlines() else "(无输出)"}
```

## 功能说明

核心 `slugify()` 流程先处理用户替换规则，再规范化文本；默认执行 Unicode 转换，按配置解码 HTML 命名、十进制和十六进制字符实体；之后执行小写转换、引号及数字标点清理、非法字符替换、重复连字符压缩、停用词移除、替换规则收尾和可选截断。`allow_unicode`、分隔符、正则、停用词与长度等选项均以公开函数及 CLI 源码为准。

## 问题处理

- 提示缺少 `text_unidecode`：按项目安装说明安装 `python-slugify`，并确认当前 Python 环境已安装项目声明的运行依赖。
- 中文字符被转写：这是默认 Unicode 转换路径的表现；需要原样保留时尝试 `--allow-unicode`。
- 输出长度不符合预期：确认 `--max-length` 数值及 `--word-boundary`、`--save-order` 参数。

## 复核提示

这是公开第三方软件的操作材料演示。开发者、申请人、权利人、完成日期、登记范围及第三方依赖许可适用口径需另行确认。本稿不得作为已确认权属或可提交的登记材料。
"""


def patent_text() -> str:
    return """---
title: 一种文本标识生成方法（公开软件实现摘编演示稿）
type: invention
applicant: 待确认
inventors: [待确认]
---

# 权利要求书

1. 一种将输入文本转换为文本标识的方法，其特征在于，包括：接收输入文本及转换参数；按用户替换规则预处理所述输入文本；对预处理文本进行 Unicode 规范化，并依据配置执行字符转写；解析启用的 HTML 字符实体；依据字符许可规则将非许可字符替换为默认分隔符；压缩连续默认分隔符并移除首尾分隔符；依据停用词集合过滤分隔后的词项；以及依据长度参数对结果截断并将默认分隔符替换为指定分隔符。
2. 根据权利要求1所述的方法，其特征在于，所述转换参数包括是否保留 Unicode 字符、是否转换命名实体/十进制实体/十六进制实体、是否转为小写、停用词集合、替换规则、最大长度及词边界截断选项；当启用词边界截断时，按分隔符分割结果并依据词项顺序及最大长度确定输出。

# 说明书

## 技术领域
本演示稿涉及文本规范化处理，具体以公开的 Python Slugify 8.0.4 源码所示文本标识转换流程作为技术内容实例。

## 背景技术
公开源码的 README 将软件描述为处理 Unicode 文本并生成 slug 的 Python 应用。输入文本可能含有大小写、标点、HTML 字符实体及 Unicode 字符；本演示稿仅描述该已公开实现所采用的处理步骤，不据此断言其新颖性或创造性。

## 发明内容

### 要解决的技术问题
演示如何把实际软件实现中的文本处理流程转写为结构化专利申请文件草稿。技术问题及其法律可专利性均未经过独立查新或法律审查。

### 技术方案
以 `slugify/slugify.py` 的 `slugify()` 和 `smart_truncate()` 为技术依据：先执行可选用户替换和引号预处理，再按 `allow_unicode` 分支执行 NFKC 或 NFKD 规范化及转写；处理命名、十进制、十六进制字符实体；再次规范化并按选项转小写；清理引号和数字间逗号；按字符模式替换非法字符、合并连续连字符并裁掉首尾连字符；按停用词过滤；执行替换规则收尾；需要时进行智能截断，最后替换为用户分隔符。步骤细节及选项以随稿公开源文件为准。

### 有益效果
本节仅概括源码所展示的处理组织方式：多个可配置的规范化、字符清理及截断步骤由统一函数顺序执行。没有实测对照或基准数据，因此不主张性能提升、准确率提升或其他量化效果。

## 附图说明
本演示以文字描述源码中的处理步骤，未提供附图。

## 具体实施方式
实施例依据公开版本 `v8.0.4` 的 `slugify/slugify.py`。调用 `slugify(text, allow_unicode=False)` 时，函数先处理 `replacements`，用引号正则将引号替换为默认连字符；随后进入 Unicode 转写分支。默认字符模式允许 ASCII 字母、数字和连字符，其他字符替换为连字符，再合并连续连字符并清除两端连字符。调用者可传入停用词、替换规则、分隔符和 `max_length`；当最大长度大于零时，函数调用 `smart_truncate()`。CLI 参数由 `slugify/__main__.py` 解析，最终调用相同的 `slugify()` 并将结果写到标准输出。上述为第三方公开代码的实现说明，不表示本演示参与开发或取得申请权。

## 摘要
本演示稿依据公开软件中的文本转换实现，描述一种文本标识生成流程：对输入文本执行替换和 Unicode 规范化，按配置转写字符并解析字符实体，再清理不许可字符、压缩分隔符、过滤停用词，并按需截断及替换输出分隔符。本稿用于展示从公开技术材料生成的申请文件草稿；申请人、发明人、权属以及新颖性和创造性均未确认。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    ap.add_argument("--knowledge", type=Path, help="Existing fixed knowledge index; omitted for the frozen baseline")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--soffice", type=Path, default=DEFAULT_SOFFICE)
    ap.add_argument("--pdftoppm", type=Path, default=DEFAULT_PDFTOPPM)
    ap.add_argument("--manual-phrase", default="命令运行后，请核对终端显示的转换结果。",
                    help="Editable wording for the repeatable regeneration check")
    args = ap.parse_args()
    project, out = args.project.resolve(), args.out.resolve()
    if not project.is_dir():
        ap.error(f"Project folder not found: {project}")
    if out.exists():
        ap.error(f"Output must be fresh: {out}")
    if args.knowledge and not args.knowledge.exists():
        ap.error(f"Knowledge index not found: {args.knowledge}")
    out.mkdir(parents=True)
    log: list[dict] = []
    started = time.time()
    py = sys.executable
    case = out / "copyright-case"
    prepare = [py, "-m", "word_skills", "copyright", "prepare", str(project), "--out", str(case),
               "--name", "Python Slugify", "--version", "8.0.4"]
    if args.knowledge:
        prepare += ["--knowledge", str(args.knowledge.resolve())]
    run(prepare, log)

    # Inspect selection scope from real manifest; select every runtime package .py file.
    selection_path = case / "workflow" / "草稿" / "代码文件选择.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8-sig"))
    reasons = {
        "slugify/__init__.py": "Package public API: re-exports slugify functions and package metadata.",
        "slugify/__main__.py": "Actual command-line entrypoint: parses text/options and prints the function result.",
        "slugify/__version__.py": "Runtime package identity and version metadata used by the release.",
        "slugify/slugify.py": "Core text normalization, entity handling, character cleanup, stopword filtering and truncation implementation.",
        "slugify/special.py": "Runtime special-character mapping imported by the public package API.",
    }
    selected = []
    for item in selection["files"]:
        item["selected"] = item["path"] in reasons
        item["model_reason"] = reasons.get(item["path"], "")
        if item["selected"]:
            selected.append(item["path"])
    selection_path.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run([py, "-m", "word_skills", "copyright", "select", str(case / "copyright.json"),
         "--workflow-selection", str(selection_path), "--reviewed-by", "reuse-trial-source-review"], log)

    # Capture only demonstrated CLI behavior from this actual project source.
    commands = [
        [py, "-m", "slugify", "C'est déjà l'été &amp; café!"],
        [py, "-m", "slugify", "影師嗎", "--allow-unicode"],
        [py, "-m", "slugify", "Project 123, Revision 4", "--max-length", "12", "--word-boundary"],
    ]
    outputs = []
    for command in commands:
        outputs.append(run(command, log, cwd=project))
    log_path = out / "execution-log.json"
    write_json(log_path, log)
    manual = case / "manual.md"
    manual.write_text(manual_text(args.manual_phrase, outputs[0]) + "\n\n## 本轮可变说明\n\n" + args.manual_phrase + "\n",
                      encoding="utf-8")
    draft_path = case / "copyright.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8-sig"))
    draft["manual"].update(path="manual.md", verified_against="execution-log.json")
    draft["application"]["category"] = "应用软件（登记分类待确认）"
    draft["ui_type"] = "headless"
    draft["ai_use"] = {"used": True, "human_verified": False,
                       "disclosure": "本演示由自动化生成草稿；权属和登记事实未核验。"}
    write_json(draft_path, draft)
    run([py, "-m", "word_skills", "copyright", "package", str(draft_path), "--out",
         str(out / "copyright-delivery"), "--draft", "--soffice", str(args.soffice),
         "--pdftoppm", str(args.pdftoppm)], log)

    patent = out / "patent-draft.md"
    if args.knowledge:
        run([py, "-m", "word_skills", "patent", "template", "invention", "-o", str(patent),
             "--knowledge", str(args.knowledge.resolve())], log)
    else:
        run([py, "-m", "word_skills", "patent", "template", "invention", "-o", str(patent)], log)
    patent.write_text(patent_text(), encoding="utf-8")
    patent_docx = out / "patent-delivery.docx"
    run([py, "-m", "word_skills", "patent", "build", str(patent), "-o", str(patent_docx)], log)
    from word_skills.inspect import preview
    patent_preview = preview(patent_docx, out / "patent-preview", soffice=str(args.soffice), pdftoppm=str(args.pdftoppm))
    write_json(out / "patent-preview.json", patent_preview)
    # Keep a final log including all artifact commands.
    write_json(log_path, log)
    summary = {
        "state": "drafts-generated-pending-human-review",
        "project": str(project),
        "knowledge": str(args.knowledge.resolve()) if args.knowledge else None,
        "selected_runtime_python_files": selected,
        "cli_commands": commands,
        "cli_outputs": outputs,
        "copyright_delivery": str(out / "copyright-delivery"),
        "patent_draft": str(patent),
        "patent_document": str(patent_docx),
        "patent_pages": patent_preview["pages"],
        "manual_phrase": args.manual_phrase,
        "manual_sha256": digest(manual),
        "patent_sha256": digest(patent),
        "elapsed_seconds": round(time.time() - started, 2),
        "review_status": "pending visual and factual review; no ownership, inventorship, novelty, or submission claim",
    }
    write_json(out / "trial-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
