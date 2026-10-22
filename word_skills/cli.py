from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import read_json, write_json
from . import copyright, proposal
from .delivery import build, finalize, review_init
from .evidence import contract, validate
from .ingest import ingest
from .render import fingerprint
from .router import list_skills, route
from .technology import scaffold


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "patent":
        from .legacy_patent import main as patent_main

        return patent_main(argv[1:])
    parser = argparse.ArgumentParser(description="Local evidence-bound technical documents; writing is performed by the agent")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("ingest")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--case", required=True)
    p = commands.add_parser("template")
    p.add_argument("--mode", required=True, help="已安装的技术文档模式名")
    p.add_argument("--out", required=True)
    p = commands.add_parser("fingerprint")
    p.add_argument("docx")
    p.add_argument("--out", required=True)
    p = commands.add_parser("lint")
    p.add_argument("draft")
    p.add_argument("--case", required=True)
    p = commands.add_parser("build")
    p.add_argument("draft")
    p.add_argument("--case", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--template")
    p.add_argument("--template-mode", choices=["style", "slots"], default="style")
    p.add_argument("--soffice")
    p.add_argument("--pdftoppm")
    p.add_argument("--no-preview", action="store_true")
    p = commands.add_parser("freeze-content", help="冻结已通过机械校验的技术报告或设计说明及来源；不代表语义审阅")
    p.add_argument("draft")
    p.add_argument("--case", required=True)
    p.add_argument("--out", required=True, help="全新的锁定目录")
    p = commands.add_parser("format-content", help="仅应用允许的排版字段，不修改锁定正文")
    p.add_argument("bundle")
    p.add_argument("--patch", required=True)
    p.add_argument("--out", required=True, help="全新的 JSON 文件路径")
    p = commands.add_parser("build-locked", help="从锁定内容与排版 patch 生成待审阅文档")
    p.add_argument("bundle")
    p.add_argument("--patch", required=True)
    p.add_argument("--out", required=True, help="全新的交付目录")
    p.add_argument("--template")
    p.add_argument("--template-mode", choices=["style", "slots"], default="style")
    p.add_argument("--soffice")
    p.add_argument("--pdftoppm")
    p.add_argument("--no-preview", action="store_true")
    for name in ("review-init", "finalize"):
        p = commands.add_parser(name)
        p.add_argument("output")
    p = commands.add_parser("skills", help="列出仓库登记的技能及其实现状态")
    p.add_argument("action", choices=["list"], nargs="?", default="list")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p = commands.add_parser("route", help="根据用户请求选择技能；只做确定性路由，不生成正文")
    p.add_argument("request")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    p = commands.add_parser("kb", help="固定资料检索：支持本地快照及可选的本机RAGFlow，生成待阅读上下文")
    kb_commands = p.add_subparsers(dest="kb_action", required=True)
    p = kb_commands.add_parser("build")
    p.add_argument("manifest")
    p.add_argument("--out", required=True)
    p = kb_commands.add_parser("verify")
    p.add_argument("index")
    for action in ("search", "context"):
        p = kb_commands.add_parser(action)
        p.add_argument("index")
        p.add_argument("--query", action="append" if action == "context" else "store", required=True)
        p.add_argument("--top-k", type=int, default=3)
        p.add_argument("--kind", choices=["rule", "reference", "project"])
        p.add_argument("--topic", choices=["copyright", "patent"])
        if action == "context":
            p.add_argument("--out", required=True)
    p = commands.add_parser("proposal", help="项目申请 Profile、模板与机械校验")
    proposal_commands = p.add_subparsers(dest="proposal_action", required=True)
    p = proposal_commands.add_parser("template")
    p.add_argument("--profile", default="nsfc-2026-general")
    p.add_argument("--out", required=True)
    p = proposal_commands.add_parser("lint")
    p.add_argument("draft")
    p.add_argument("--case", help="ingested source/evidence case directory")
    p.add_argument("--allow-expired", action="store_true", help="仅供历史案例检查，不表示指南仍有效")
    p = proposal_commands.add_parser("build")
    p.add_argument("draft")
    p.add_argument("--case", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--allow-expired", action="store_true", help="仅供历史案例检查，不表示指南仍有效")
    p.add_argument("--soffice")
    p.add_argument("--pdftoppm")
    p.add_argument("--no-preview", action="store_true")
    p = commands.add_parser("copyright", help="软著源码清单、材料草稿与机械校验")
    copyright_commands = p.add_subparsers(dest="copyright_action", required=True)
    p = copyright_commands.add_parser("workflow", help="直接运行固定 Fokkyp 业务阶段；后续参数原样传递")
    p.add_argument("stage", choices=["analyze", "business", "candidates", "manual", "fields", "confirm", "screenshots"])
    p.add_argument("stage_arguments", nargs=argparse.REMAINDER)
    p = copyright_commands.add_parser("prepare", help="建立源码候选、业务理解与申请材料草稿")
    p.add_argument("source_root")
    p.add_argument("--out", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--version", default="")
    p.add_argument("--knowledge", help="已构建的固定规则知识库；生成待阅读上下文，不代填项目事实或权属")
    p = copyright_commands.add_parser("select", help="应用已审阅的 selection.json，不确认权属")
    p.add_argument("draft")
    p.add_argument("--workflow-selection", help="复用上游代码文件选择.json，投影成原件哈希/完整行段")
    p.add_argument("--reviewed-by", default="", help="实际源码审阅人或Agent；不代表用户权属确认")
    p = copyright_commands.add_parser("package", help="共享链路生成源码、操作说明与申请信息辅助稿")
    p.add_argument("draft")
    p.add_argument("--out", required=True)
    p.add_argument("--draft", action="store_true", dest="preparation_only", help="允许权属等字段待确认；只能生成不可定稿的草稿")
    p.add_argument("--soffice")
    p.add_argument("--pdftoppm")
    p.add_argument("--no-preview", action="store_true")
    p = copyright_commands.add_parser("package-finalize")
    p.add_argument("output")
    p = copyright_commands.add_parser("scan")
    p.add_argument("source_root")
    p.add_argument("--out")
    p = copyright_commands.add_parser("template")
    p.add_argument("--out", required=True)
    p = copyright_commands.add_parser("lint")
    p.add_argument("draft")
    p.add_argument("--source-root")
    p = copyright_commands.add_parser("extract")
    p.add_argument("draft")
    p.add_argument("--source-root")
    p.add_argument("--out", required=True)
    p = copyright_commands.add_parser("build")
    p.add_argument("draft")
    p.add_argument("--source-root")
    p.add_argument("--out", required=True)
    p.add_argument("--soffice")
    p.add_argument("--pdftoppm")
    p.add_argument("--no-preview", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "skills":
            result = {"schema_version": 1, "skills": list_skills()}
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                for row in result["skills"]:
                    path = row["path"] or "(planned; no implementation path)"
                    scope = row.get("mode_scope") or {}
                    focused = ", ".join(mode for mode, value in scope.items() if value == "focused")
                    extended = ", ".join(mode for mode, value in scope.items() if value == "baseline")
                    suffix = f" | focused: {focused}" if focused else ""
                    if extended:
                        suffix += f" | baseline: {extended}"
                    print(f"{row['name']:<18} {row['status']:<11} {path}{suffix}")
            return 0
        if args.command == "route":
            result = route(args.request)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"selected: {result['selected']}")
                print(f"status: {'clarification-needed' if result['needs_clarification'] else 'ready'}")
                print(result["reason"])
                for match in result["matches"]:
                    scope = f", {match['mode_scope']} scope" if match["mode_scope"] else ""
                    print(f"- {match['skill']} ({match['status']}{scope}): {', '.join(match['matched_terms'])}")
            return 0
        if args.command == "kb":
            from .knowledge import build_index, search, verify_index
            if args.kb_action == "build":
                checked = build_index(args.manifest, args.out)
                result = {"state": "indexed", "path": args.out, "kb_id": checked["kb_id"],
                          "documents": len(checked["documents"]), "chunks": len(checked["chunks"])}
            elif args.kb_action == "verify":
                checked = verify_index(args.index)
                result = {"state": "integrity-verified-not-semantic", "kb_id": checked["kb_id"],
                          "documents": len(checked["documents"]), "chunks": len(checked["chunks"])}
            elif args.kb_action == "search":
                result = search(args.index, args.query, args.top_k, kind=args.kind, topic=args.topic)
            else:
                from .knowledge_context import retrieve_context
                result = retrieve_context(args.index, args.query, args.out, kind=args.kind, topic=args.topic, top_k=args.top_k)
        elif args.command == "proposal":
            if args.proposal_action == "template":
                result = proposal.write_template(args.out, args.profile)
            elif args.proposal_action == "build":
                result = proposal.build(args.draft, args.case, args.out, allow_expired=args.allow_expired,
                                        soffice=args.soffice, pdftoppm=args.pdftoppm, no_preview=args.no_preview)
            else:
                result = proposal.lint(args.draft, allow_expired=args.allow_expired, case=args.case)
        elif args.command == "copyright":
            if args.copyright_action == "workflow":
                from .copyright_workflow import run_stage
                return run_stage(args.stage, args.stage_arguments)
            elif args.copyright_action in {"prepare", "select", "package", "package-finalize"}:
                from . import copyright_package
                if args.copyright_action == "prepare":
                    result = copyright_package.prepare(args.source_root, args.out, name=args.name, version=args.version, knowledge=args.knowledge)
                elif args.copyright_action == "select":
                    result = copyright_package.apply_selection(args.draft,
                        workflow_selection=args.workflow_selection, reviewed_by=args.reviewed_by)
                elif args.copyright_action == "package-finalize":
                    result = copyright_package.finalize_package(args.output)
                else:
                    result = copyright_package.package(args.draft, args.out, draft=args.preparation_only,
                        soffice=args.soffice, pdftoppm=args.pdftoppm, no_preview=args.no_preview)
            elif args.copyright_action == "scan":
                result = copyright.scan(args.source_root, args.out)
            elif args.copyright_action == "template":
                result = copyright.write_template(args.out)
            elif args.copyright_action == "lint":
                result = copyright.lint(args.draft, source_root=args.source_root)
            elif args.copyright_action == "extract":
                result = copyright.extract_materials(args.draft, args.out, source_root=args.source_root)
            else:
                result = copyright.build(args.draft, args.out, source_root=args.source_root,
                                         soffice=args.soffice, pdftoppm=args.pdftoppm, no_preview=args.no_preview)
        elif args.command == "ingest":
            result = ingest(args.inputs, args.case)
            result = {"sources": len(result["sources"]), "skipped": result["skipped"], "case": args.case}
        elif args.command == "template":
            if Path(args.out).exists():
                raise ValueError("Draft already exists")
            schema = contract(args.mode)
            result = {"schema_version": 1, "mode": args.mode, "title": schema["title"], "sections": [
                {"id": k, "title": v, "blocks": [{"id": k + "-body", "type": "paragraph", "intent": "gap", "text": "待补充", "claim_ids": []}]}
                for k, v in schema["required_sections"].items()], **scaffold(args.mode)}
            write_json(args.out, result)
            result = {"draft": args.out, "state": "scaffold-not-deliverable"}
        elif args.command == "fingerprint":
            if Path(args.out).exists():
                raise ValueError("Fingerprint file already exists")
            result = fingerprint(args.docx)
            write_json(args.out, result)
        elif args.command == "lint":
            result = validate(read_json(args.draft), args.case)
        elif args.command == "build":
            result = build(args.draft, args.case, args.out, args.template, args.template_mode, args.soffice, args.pdftoppm, args.no_preview)
        elif args.command == "freeze-content":
            from .content_lock import freeze_content
            result = freeze_content(args.draft, args.case, args.out)
        elif args.command == "format-content":
            from .content_lock import format_locked
            result = format_locked(args.bundle, args.patch, args.out)
        elif args.command == "build-locked":
            from .locked_delivery import build_locked
            result = build_locked(args.bundle, args.patch, args.out, args.template,
                                  args.template_mode, args.soffice, args.pdftoppm, args.no_preview)
        elif args.command == "review-init":
            result = review_init(args.output)
        else:
            result = finalize(args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("passed") is False or result.get("state") in {"blocked", "failed"} else 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
