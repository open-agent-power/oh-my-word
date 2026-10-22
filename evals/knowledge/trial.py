"""Real fixed KB and workspace component through copyright and patent CLIs.

This is a source-grounded preparation exercise, not a registration, novelty
opinion, controlled writing-quality experiment, or a complete software deposit.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

from word_skills.common import read_json, sha256, write_json
from word_skills.inspect import preview
from word_skills.knowledge import search, verify_index
from word_skills.knowledge_context import verify_context


PATENT = """---
title: 一种基于来源快照校验的文档知识检索方法
type: invention
---
# 权利要求书
1. 一种基于来源快照校验的文档知识检索方法，其特征在于，由处理器执行以下步骤：读取包含文档标识、文件路径、文件哈希、资料类型和版本的来源清单；核对所述文件哈希后，将对应文件保存为本地来源快照；将来源快照按行划分为文本片段，为文本片段记录来源标识、起止行位置及资料类型，并保存片段索引和索引身份；接收检索词后，核对索引身份、来源快照和片段索引的一致性；对通过核对的文本片段计算词法相关性得分，按得分返回包含原文、起止行位置、资料类型和版本的结果。
2. 根据权利要求1所述的基于来源快照校验的文档知识检索方法，其特征在于，当检索结果得分相同时，按文本片段标识排序；当没有正得分结果时，返回空命中状态。
# 说明书
## 技术领域
本说明涉及计算机文档处理及本地信息检索，具体说明来源快照、行位置和检索片段之间的对应方法。
## 背景技术
文档写作可能引用不同版本的资料，引用片段与原始资料之间需要保留对应关系。本稿依据当前知识检索组件的实际源码描述实现，尚未完成与既有技术的全面对比，不据此判断新颖性或创造性。
## 发明内容
### 要解决的技术问题
使一次本地检索能够核对索引所使用的来源状态，并返回可在原文快照中定位的片段。
### 技术方案
读取包含文档标识、文件路径、文件哈希、资料类型和版本的来源清单。核对文件哈希后，将对应文件保存为本地来源快照。将来源快照按行划分为文本片段，为文本片段记录来源标识、起止行位置及资料类型，并保存片段索引和索引身份。接收检索词后，核对索引身份、来源快照和片段索引的一致性。对通过核对的文本片段计算词法相关性得分，按得分返回包含原文、起止行位置、资料类型和版本的结果。当得分相同时，按文本片段标识排序；没有正得分结果时，返回空命中状态。
### 有益效果
返回片段附带原文位置，便于复核引用来自哪个快照及其对应行。哈希核对能够发现与登记状态不一致的文件变化，但不能认证原文事实真实、阻止主动重建清单，或自动确认检索片段支持本案技术结论。本文没有性能对照实测结论。
## 具体实施方式
来源文档以规则、参考材料和项目材料区分，分别保存标识、路径、哈希、主题与版本。构建函数先读取文件字节核对哈希，再保存来源快照、片段索引和索引清单。采用来源标识及片段序号组成片段标识，片段保留原文的起止行位置。
当前实现按完整行组合文本片段，目标长度为1500字符；相邻片段在预算允许时重叠不超过2行。超过长度目标的不可分单行单独保存并标记，不静默截断。该切分属于当前实现参数，不表示适合所有专利长距离技术关系，跨片段论证仍须扩展阅读。
检索前重新校验来源快照、清单和片段的一致性。对英文标识符和汉字二元组分词，以BM25计算词法得分，其中k1取1.5，b取0.75。只返回正得分片段；得分相同按片段标识排序。实际调用者还可按资料类型和主题过滤。检索命中只提供来源定位，未核验候选保持未核验状态。
本稿是对本地项目功能子集的撰写演练。申请人、发明人、权属、技术贡献归属和完整现有技术检索仍待另行确认；未进行申请提交或最终审阅门禁验收。
# 摘要
本说明涉及一种基于来源快照校验的文档知识检索方法，读取来源清单并核对文件哈希，保存本地快照及带行位置的片段索引；检索时复核来源与索引一致性，按词法相关性返回包含原文、行位置、资料类型和版本的片段，以供引用复核。检索结果不自动成为已核验事实。
"""


def call(args, log, expected=0):
    proc = subprocess.run([sys.executable, "-m", "word_skills", *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=240)
    write_json(log, {"argv": list(map(str, args)), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
    if proc.returncode != expected:
        raise ValueError(f"CLI failed; see {log}: {proc.stdout[-500:]} {proc.stderr[-500:]}")
    return proc


def run(root, soffice):
    out = root / "trial-v1"
    out.mkdir(parents=True, exist_ok=False)
    kb = root / "indexes/ip-v1"
    verified = verify_index(kb)
    questions = [
        {"id": "copyright-identification", "topic": "copyright", "kind": "rule", "query": "源程序 文档 鉴别材料 前后 连续 页", "expected_source": "computer-software-copyright-registration-measures"},
        {"id": "patent-disclosure", "topic": "patent", "kind": "rule", "query": "说明书 清楚 完整 实现 权利要求 依据", "expected_source": "patent-law-2020"},
        {"id": "patent-abstract", "topic": "patent", "kind": "rule", "query": "摘要 文字部分 300字", "expected_source": "patent-law-implementing-regulations-2023"},
        {"id": "ai-disclosure", "topic": "patent", "kind": "rule", "query": "人工智能 模型 构建 训练 必要模块 层级 连接关系", "expected_source": "patent-examination-guidelines-amendment-order-84"},
        {"id": "patent-reference", "topic": "patent", "kind": "reference", "query": "信息安全系统 方法", "expected_source": "cn103597488a-information-security-system-and-method"},
        {"id": "no-hit", "topic": "copyright", "kind": "rule", "query": "zzq_no_such_evidence_9f83d", "expect_empty": True},
        {"id": "no-project-fact-from-rule", "topic": "patent", "kind": "project", "query": "知识索引 软件", "expect_empty": True},
    ]
    write_json(out / "retrieval-cases-prefrozen.json", {"scope": "known-source integration checks, not heldout retrieval benchmark", "kb_id": verified["kb_id"], "cases": questions})
    results = []
    for q in questions:
        result = search(kb, q["query"], 5, topic=q["topic"], kind=q["kind"])
        write_json(out / (q["id"] + ".json"), result)
        results.append({"id": q["id"], "source_ids": [h["source_id"] for h in result["hits"]],
            "expected_in_top5": q.get("expected_source") in [h["source_id"] for h in result["hits"]] if "expected_source" in q else None,
            "empty": not result["hits"]})
    write_json(out / "retrieval-checks.json", results)
    case = out / "copyright-case"
    call(["copyright", "prepare", root / "project-component", "--out", case, "--name", "Word Skills", "--version", "0.3.0", "--knowledge", kb], out / "copyright-prepare.json")
    selection = read_json(case / "selection.json")
    selection["reviewed_by"] = "root actual source inspection; no ownership inference"
    for item in selection["files"]:
        item.update(selected=True, reason="知识检索组件实际核心源码；完整文件转录，仅功能子集演练，非完整登记程序")
    write_json(case / "selection.json", selection)
    call(["copyright", "select", case / "copyright.json"], out / "copyright-select.json")
    verification = call(["kb", "verify", kb], out / "kb-verify.json")
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    lines = ["实际运行输出排版（非原生终端截图）"] + textwrap.wrap("python -m word_skills kb verify " + str(kb), 70) + verification.stdout.splitlines()
    img = Image.new("RGB", (1200, 45 + 30 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((20, 15 + i * 30), line, fill="black", font=font)
    img.save(case / "verify-output.png")
    (case / "manual.md").write_text(f"""# Word Skills 0.3.0

## 用途与范围
知识检索组件用于将已登记资料固定为本地快照，按检索词找到带来源位置的片段。本手册依据当前组件源码及本次实际命令输出编写。演练源码仅为功能子集，权属及正式申请字段尚未确认。

## 建立知识索引
准备来源清单，逐项填写文档标识、路径、哈希、资料类型及版本。运行 kb build 时指定新目录；已有目录会被拒绝。构建成功返回索引身份、文档数量和片段数量。输入文件哈希不一致时，核对原件并建立新版本，不覆盖旧案资料。

## 核对索引
使用 kb verify 指定索引目录。本次实际命令已完成，输出如下图；图为实际输出排版，不是终端窗口截图。它只表示索引完整性核对，不是资料语义或法律认证。

![索引校验实际输出排版](verify-output.png)

## 检索与阅读
使用 kb search，提供 query，可按 topic 和 kind 筛选。结果包含来源标识、版本、原文及起止行位置。词法相似不等于支持结论，应读取对应原文；无命中时保留资料缺口。

| 资料类型 | 使用方式 |
| --- | --- |
| rule | 核对官方法规或审查要求，注意版本与适用性 |
| reference | 阅读已公开文献，不能代替本案事实或全面查新 |
| project | 核对本案源码与技术材料，不推断权属或实测效果 |

## 保存检索上下文
使用 kb context 将查询结果保存到新目录。阅读 context.md 及完整源文件；evidence-candidates.json 保持未核验，原业务事实账本由实际阅读后另行建立。修改来源后建立新索引，不静默改写旧检索上下文。
""", encoding="utf-8")
    value = read_json(case / "copyright.json")
    value["application"]["category"] = "命令行软件"
    value["manual"]["verified_against"] = "root read actual knowledge.py plus recorded kb verify CLI execution"
    value["screenshots"] = [{"path": "verify-output.png", "feature": "索引校验实际输出排版，非原生窗口截图"}]
    value["ai_use"] = {"used": True, "human_verified": False, "disclosure": "Agent辅助编写；仅准备草稿，未完成权属与正式业务审阅"}
    write_json(case / "copyright.json", value)
    call(["copyright", "package", case / "copyright.json", "--out", out / "copyright-delivery", "--draft", "--soffice", soffice], out / "copyright-package.json")
    patent = out / "patent.md"
    call(["patent", "template", "invention", "-o", patent, "--knowledge", kb], out / "patent-template.json")
    patent.write_text(PATENT, encoding="utf-8")
    call(["kb", "context", kb, "--topic", "patent", "--kind", "reference", "--query", "信息安全系统 方法", "--out", out / "patent-reference-context"], out / "patent-reference-retrieval.json")
    source = root / "project-component/knowledge.py"
    text = source.read_text(encoding="utf-8")
    facts = []
    for n, (statement, term) in enumerate((("按来源哈希核对文件后构建本地索引", 'if _hash(data) != d["sha256"]:'),
        ("BM25检索只返回正得分并按片段标识稳定排序", 'scored.sort(key=lambda pair: (-pair[0], pair[1]["chunk_id"]))')), 1):
        line = next(i for i, v in enumerate(text.splitlines(), 1) if term in v)
        facts.append({"id": f"F{n}", "text": statement, "status": "verified", "source_id": "P1", "locator": f"L{line}", "quote": text.splitlines()[line-1], "verified_by": "root source reading; not novelty or legal certification"})
    write_json(out / "TECH_FACTS.json", {"schema_version": 1, "sources": [{"id": "P1", "path": str(source), "sha256": sha256(source)}], "facts": facts})
    call(["patent", "review-init", patent, "--facts", out / "TECH_FACTS.json", "-o", out / "content-review.json"], out / "patent-review-init.json")
    call(["patent", "build", patent, "-o", out / "patent-review.docx"], out / "patent-build.json")
    rendered = preview(out / "patent-review.docx", out / "patent-preview", soffice=soffice)
    write_json(out / "patent-preview.json", rendered)
    tampered = out / "tampered-context"
    shutil.copytree(case / "knowledge", tampered)
    (tampered / "context.md").write_text("changed", encoding="utf-8")
    try:
        verify_context(tampered)
    except ValueError:
        blocked = True
    else:
        blocked = False
    assert blocked
    write_json(out / "summary.json", {"kb_id": verified["kb_id"], "copyright_state": "draft",
        "patent_state": "draft-not-finalized", "patent_pages": rendered["pages"], "context_tamper_blocked": blocked,
        "visual_review": "pending", "scope": "real project component + real public sources, integration only; no quality uplift or registration claim"})
    print(read_json(out / "summary.json"))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--soffice", required=True)
    args = p.parse_args()
    run(args.root, args.soffice)
