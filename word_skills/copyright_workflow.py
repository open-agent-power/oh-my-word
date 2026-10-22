"""Thin, isolated entry point for the pinned Fokkyp workflow (MIT).

Business generation stays upstream. Local hooks only restrict file discovery,
avoid invented related documents, and distinguish previews from confirmation.
"""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import subprocess
import sys

STAGES = {
    "analyze": "analyze_project", "business": "generate_business_context",
    "candidates": "propose_code_selection", "manual": "generate_manual_draft",
    "fields": "generate_application_info", "confirm": "confirm_stage",
    "screenshots": "capture_screenshots",
}
VENDOR = Path(__file__).parent / "_vendor" / "fokkyp"


def run_stage(stage, arguments, *, quiet=False):
    """Use a child process so upstream's standalone imports cannot pollute ours."""
    if stage not in STAGES:
        raise ValueError(f"Unknown copyright workflow stage: {stage}")
    result = subprocess.run([sys.executable, "-m", "word_skills.copyright_workflow",
                             stage, *arguments], check=False, capture_output=quiet,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if quiet and result.returncode:
        sys.stderr.buffer.write(result.stdout + result.stderr)
    return result.returncode


def _execute(stage, arguments):
    from . import copyright

    sys.path.insert(0, str(VENDOR / "scripts"))
    import common as upstream
    upstream.EXCLUDE_DIRS.update(copyright._SKIP_DIRS)
    original_walk = upstream.iter_project_files
    original_read = upstream.read_text
    project_root = None
    if "--project" in arguments:
        project_root = Path(arguments[arguments.index("--project") + 1]).resolve()

    def safe_read(path, limit=None):
        path = Path(path)
        if (path.is_symlink() or (project_root and path.absolute().is_relative_to(project_root)
                                 and not path.resolve().is_relative_to(project_root))):
            return ""
        if (path.name.lower() in copyright._SECRET_NAMES or path.name.lower().startswith(".env")
                or path.suffix.lower() in copyright._SECRET_SUFFIXES):
            return ""
        text = original_read(path, limit)
        return "" if copyright._CREDENTIAL.search(text) else text

    # Direct README/package reads bypass iter_project_files in the upstream analyzer.
    upstream.read_text = safe_read

    def safe_walk(project, exts=None):
        root = Path(project).resolve()
        for path in original_walk(root, exts):
            if (path.is_symlink() or not path.resolve().is_relative_to(root)
                    or any(p.is_symlink() for p in path.parents if p != root and p.is_relative_to(root))):
                continue
            if (path.name.lower() in copyright._SECRET_NAMES or path.name.lower().startswith(".env")
                    or path.suffix.lower() in copyright._SECRET_SUFFIXES):
                continue
            # Keep binary design documents discoverable, while withholding text credentials.
            if path.stat().st_size <= copyright._MAX_FILE_BYTES:
                try:
                    text, _ = copyright._read_source(path)
                except (ValueError, OSError):
                    text = ""
                if copyright._CREDENTIAL.search(text):
                    continue
            yield path

    upstream.iter_project_files = safe_walk
    arguments = list(arguments)
    preview = stage in {"manual", "fields"} and "--preview" in arguments
    if preview:
        arguments.remove("--preview")
    interface = "visual"
    if stage == "manual" and "--interface" in arguments:
        position = arguments.index("--interface")
        interface = arguments[position + 1]
        if interface not in {"cli", "visual"}:
            raise ValueError("manual interface must be cli or visual")
        del arguments[position:position + 2]
    if stage in {"manual", "fields"}:
        module = __import__(STAGES[stage])
        original_gate = module.require_confirmed_business

        def require_business(business):
            if preview:
                if not business:
                    raise ValueError("preview still requires an evidence-based business context")
                print("PREVIEW_ONLY: business confirmation is pending; not a submission-ready document")
                return
            original_gate(business)
            if not upstream.confirmation_is_current(business):
                raise ValueError("business confirmation is missing or stale; review the changed context")

        module.require_confirmed_business = require_business
        if stage == "fields":
            original_fields = module.build_fields
            original_write = module.write_application_md
            # Upstream's fallback pads to 500 characters using generic features.
            # Missing evidence must remain visible; never synthesize functionality.
            module.summarize_features = lambda *a, **kw: "待用户确认"

            def conservative_fields(analysis, manifest, name, version, answers, business=None):
                fields = original_fields(analysis, manifest, name, version, answers, business)
                authored = answers.get("软件的主要功能") or (business or {}).get("main_functions")
                if authored is not None and not isinstance(authored, str):
                    raise ValueError("main_functions must be authored text")
                # Preserve even short/long text for review; downstream length checks
                # can report it, but may not replace it with invented filler.
                fields["软件的主要功能"] = authored.strip() if authored and authored.strip() else "待用户确认"
                for field in ("开发方式", "软件说明", "权利范围", "权利取得方式", "开发的硬件环境",
                              "运行的硬件环境", "开发该软件的操作系统", "软件开发环境 / 开发工具",
                              "该软件的运行平台 / 操作系统", "软件运行支撑环境 / 支持软件"):
                    if not answers.get(field):
                        fields[field] = "待用户确认"
                return fields

            module.build_fields = conservative_fields

            def write_fields(path, *args, **kwargs):
                original_write(path, *args, **kwargs)
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("\n本稿为填写辅助。500~1300字为固定上游兼容校验；"
                                 "应对照当次官方表单核对，不以转载代替官方依据。"
                                 "内容不足时补充真实材料，不能凑字或增加未经证实的功能。\n")

            module.write_application_md = write_fields
        if stage == "manual":
            original_related = module.normalize_related_documents

            def actual_related(business):
                return original_related(business) if business and business.get("related_documents") else []

            module.normalize_related_documents = actual_related
            if interface == "cli":
                _cli_manual(module)
        sys.argv = [str(VENDOR / "scripts" / (STAGES[stage] + ".py")), *arguments]
        module.main()
    else:
        sys.argv = [str(VENDOR / "scripts" / (STAGES[stage] + ".py")), *arguments]
        runpy.run_path(sys.argv[0], run_name="__main__")


def _cli_manual(module):
    """Replace only upstream's GUI sentence hooks; retain its structure/checks."""
    module.plain_manual_text = lambda text: text
    module.tidy_manual_output = lambda text: text
    module.purpose_sentence = lambda feature, purpose: module.ensure_sentence(purpose)
    module.visible_elements_sentence = lambda items, feature, index: (
        "终端输出包含" + module.natural_join(items, limit=8) + "。" if items else "")
    original_steps, original_feedback = module.steps_sentence, module.rules_feedback_sentence
    module.steps_sentence = lambda steps, index: original_steps(steps, 1)
    module.rules_feedback_sentence = lambda rules, feedback, index: original_feedback(rules, feedback, 1)
    module.feature_paragraph = lambda item, index: module.ensure_sentence(item["purpose"])
    original_render = module.render_manual_canonical
    original_quality = module.manual_quality_issues
    module.manual_quality_issues = lambda text, modules: [
        issue for issue in original_quality(text, modules) if not issue.startswith("模块内容偏薄：")]

    def render(*args, **kwargs):
        text = original_render(*args, **kwargs)
        text = text.replace(
            "用户进入系统后，可以围绕实际工作内容完成账号进入、业务创建、过程查看、结果确认和资料管理等操作。",
            "用户在终端中运行相应命令，并查看执行结果。")
        text = text.replace("随后按照页面提示处理内容并查看结果", "随后运行对应命令并查看终端反馈")
        text = text.replace(
            "可以按照页面提示从入口进入相应页面，查看当前业务状态，并根据页面中的按钮、输入框、列表或弹窗继续处理。",
            "可以在终端输入命令，并根据实际回显继续处理。")
        text = text.replace(
            "本手册用于说明软件的用途、功能特点、运行要求和页面操作流程。各功能章节按用户能够看到的页面、入口、按钮、输入项、提示信息和处理结果进行说明。",
            "以下章节介绍运行环境、命令入口、输入参数、终端回显和结果处理。")
        text = text.replace("正常打开页面、提交操作和展示处理结果", "执行命令并显示结果")
        return text

    module.render_manual_canonical = render


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in STAGES:
        raise SystemExit("Stages: " + ", ".join(STAGES))
    _execute(sys.argv[1], sys.argv[2:])
