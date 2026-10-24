"""官方 XML 转换交接包；不生成未经验证的 CNIPA XML。"""
from __future__ import annotations

import json
from dataclasses import asdict
import shutil
import tempfile
from pathlib import Path

from .gate import sha256
from .render import render_docx_selected


INSTRUCTIONS = """# 官方 XML 转换与提交核对

状态：review_ready / official_conversion_pending。本包没有 CNIPA XML，也未提交。

1. 从 https://cponline.cnipa.gov.cn 的“工具下载”获取当前 XML 转换工具、数据标准和手册；或使用系统的申请文件编辑功能。官方工具入口：https://cponline.cnipa.gov.cn/GzfwYwblGlwhTMVC/GzfwYwblGlwhT/selectToolsById?weihuRid=157 。
2. 将 review-docx 中对应文书导入官方工具。若当前版本要求不同输入格式，按手册转换；不得将 DOCX 改扩展名冒充 XML。使用官方五书模板时，在相应区域编辑/粘贴内容，再在“专利处理”中“添加标记”，把光标放入对应一书后“XML生成”；本工具不伪造官方专有标记。
3. 在官方预览中逐项核对：名称、权利要求项数及引用、说明书各段、公式上下标、表格数值和单位、所有附图及标号、摘要与摘要附图。对照 content.json、稿件及原图。
4. 在官方系统填写请求书：真实申请人和全部自然人发明人身份、地址及联系方式；按案件核实优先权、委托、保密审查、费减和其他附件。不要用正文中的姓名列表代替请求书。
5. 保存转换工具版本、XML/图片文件清单、官方校验和预览结果；由申请人确认最终内容。发生更改则重新内容审查并重新生成本包。
6. 通过专利业务办理系统实际签署和提交；保存受理通知/回执、申请号与缴费记录后才能称已提交。通过本工具检查不保证授权。

依据：2025-11-12 XML 通知、2025-05-26 转换工具通知、2026-07-01 问题解答更新。详见 references/cnipa-2026.md。
"""


def create_handoff(draft_path, draft, facts_path, review_path, output, options, renderer="auto"):
    options.validate()
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("交接输出目录已存在，请选择新目录，避免混入旧文件。")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".patent-", dir=output.parent) as temp:
        root = Path(temp) / "package"
        root.mkdir()
        _, renderer_used = render_docx_selected(
            draft, root / "review-docx", options=options, split=True, renderer=renderer
        )
        evidence = root / "evidence"
        evidence.mkdir()
        shutil.copyfile(draft_path, evidence / ("draft" + Path(draft_path).suffix))
        # 原始账本及源引用保持目录关系；本包用于核对，原始 final 审查仍绑定原输入。
        shutil.copyfile(facts_path, evidence / "TECH_FACTS.original.json")
        shutil.copyfile(review_path, evidence / "content-review.original.json")
        facts = json.loads(Path(facts_path).read_text(encoding="utf-8"))
        source_map = []
        for index, source in enumerate(facts["sources"], 1):
            target = evidence / f"source-{index:03d}.txt"
            shutil.copyfile(Path(facts_path).parent / source["path"], target)
            source_map.append({"id": source["id"], "path": target.relative_to(root).as_posix(), "sha256": sha256(target)})
        figures = []
        for drawing in draft.drawings:
            target = root / "figures" / f"figure-{drawing.number:03d}{Path(drawing.path).suffix}"
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(drawing.path, target)
            figures.append({"number": drawing.number, "caption": drawing.caption,
                            "abstract": drawing.is_abstract, "path": target.relative_to(root).as_posix()})
        content = {"title": draft.title, "patent_type": draft.patent_type.value,
                   "claims": [{"number": c.number, "text": c.text} for c in draft.claims],
                   "description": {x: getattr(draft, x) for x in ("technical_field", "background", "problems", "solution", "effects", "embodiments")},
                   "abstract": draft.abstract, "figures": figures, "sources": source_map,
                   "extra_sections": [asdict(x) for x in draft.extra_sections],
                   "design_brief": asdict(draft.design_brief),
                   "note": "内部核对数据，非国知局 XML。original 审查对应原路径输入，勿在交接目录直接重用作 final 证据。"}
        (root / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "CONVERT-AND-CHECK.md").write_text(INSTRUCTIONS, encoding="utf-8")
        manifest = {"schema_version": 1, "tool_version": "0.2.0", "status": "official_conversion_pending",
                    "filing_status": "not_submitted", "draft_sha256": sha256(draft_path),
                    "renderer": renderer_used,
                    "files": [{"path": p.relative_to(root).as_posix(), "sha256": sha256(p)} for p in sorted(root.rglob("*")) if p.is_file()]}
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        root.rename(output)
    return output, renderer_used
