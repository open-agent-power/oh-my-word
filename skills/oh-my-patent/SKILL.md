---
name: oh-my-patent
description: 中国专利申请的通用总览与编排入口。识别申请类型、技术领域和案件阶段，按需组合领域子 Skill，基于技术材料完成交底、检索、起草、证据审查、Word 审阅稿及官方 XML 转换交接；用于发明、实用新型与外观设计，不代表自动提交或授权保证。
---

# oh-my-patent

以通用模板组织申请，按技术贡献加载领域知识，最后汇总为一份一致的审阅稿。

## 写前阅读与交付路径

新案或影响依据的改稿先读 [固定来源与章节](references/domain-sources.md)，实际阅读相关 WIPO 方法、中国规则及本案技术资料；已读的同案记录可复用，规则与范例不能替代本案事实。

- **文本起草/审阅**：按 [交底到稿件的方法](references/drafting-method.md)、通用模板和有关领域模块直接读材料、起草、核对事实及支持关系，交付 Markdown/文本及未确认问题。不要求安装后端、调用 CLI、创建 JSON 或接 RAG。
- **工具审阅稿/正式交接准备**：需要本项目结构校验、Word、审阅状态或交接包时，使用下方工具链路及其事实/审阅 JSON。文本检查不产生工具定稿状态，也不替代官方转换或提交。

参考中的工具命令、JSON/支持协议字段仅适用于选定的工具路径；所有路径都要核对事实、披露与支持。只解释术语或局部审阅仍按实际任务取最小必要范围。

## 总览与领域路由

先读 [领域目录](references/domain-catalog.md) 和 [路由规则](references/domain-routing.md)。申请类型、技术领域、案件阶段分别判断：行业名称不等于保护主题，多个领域可以共同适用，无法确定时保留通用路径并记录缺口。

- 共有的事实、权项支持、形式与交付流程以本入口为准；子 Skill 只补充领域问题、披露要点和反例。
- 按目录中的明确文件路径读取被选中的子 Skill；不能假定宿主会自动发现嵌套目录，也不需要为每份 Skill 创建新 Agent。
- 直接进入子 Skill 时先建立本入口的共用流程；已建立则直接继续，避免来回路由。
- 起草使用 [通用撰写模板](references/general-drafting-template.md)。准备积累已有专利或领域经验时才读 [资料增强规则](references/domain-corpus.md)；扩展新领域时读 [子 Skill 契约](references/domain-skill-contract.md)。
- 当前领域子 Skill 是可读的流程模块，尚无跨领域生成质量盲测证据；加载资料不会自动改变模型权重。
- 按 [材料使用与按需检索](../word-document/references/knowledge.md) 选择路径。少量交底与固定规则原文直接阅读，不要求先建索引；需要跨来源定位或用户指定检索时用已有知识入口，`template --knowledge INDEX` 保存实际规则命中。现有稿件不要为补检索重新生成模板；参考专利按实际技术问题检索，不能作为本案事实或查新覆盖保证。
- 同案局部修改先核对原件版本，复用 `TECH_FACTS.json`、既有对比材料和支持关系；新增特征、数据或规则适用性问题只增量取证。稿件变化后原内容审查失效，按现有门禁重新审查；复用来源不等于复用旧审查结论。

## 可选工具交付链路

选择本项目工具制作新案审阅稿或定稿时适用以下链路；局部修改、材料梳理、仅排版按 [任务范围与模块交接](references/task-scope.md) 选取必要步骤。文本路径按上方方法执行，保留未完成状态，不把局部任务或文本自查称作完整申请审查。

1. 读 [01 intake](prompts/01-intake.md)，确定申请类型、领域路由、案件阶段、已有公开、申请人/发明人及材料边界。
2. 读材料。Word/PPT 用 `python tools/patent.py ingest`；遇到公式退化、纯图页或缺失必须核对原件。
3. 读 [事实账本](prompts/00-technical-facts.md)，建立 `TECH_FACTS.json`。任何来源路径、位置、参数和实验不得臆造。
4. 读 [06 撰写](prompts/06-specification-build.md) 与 [中国现行规则](references/cnipa-2026.md)，结合通用模板和已加载子 Skill 起草稿件。
5. 读 [内容审查](prompts/08-content-review.md)，将领域结论汇入已有检查项，形成逐特征支持关系和 `content-review.json`。
6. 跑 [07 自检](prompts/07-self-check.md)，修改后重新审查，执行 `--final`；交付 Word 审阅稿或 `handoff` 交接包。
7. 需要正式电子申请时读 [XML 转换](references/cnipa-xml-handoff.md)，在官方工具转换、预览核对并完成请求书及实际提交。没有回执不能称已提交。

只有一句话也不能跳过事实核对。工具路径材料完整时可跳过 02～05，但不可跳过事实账本和内容审查。文本路径同样核对事实及支持，可用普通笔记；缺必要实施信息时交付可修改草稿与问题，不补造技术。

## 按需增强

- 项目/代码材料：读 [02 项目扫描](prompts/02-project-scan.md)。
- 不知道保护什么：读 [03 专利点](prompts/03-patent-points.md)。
- 创造性判断：读 [04 现有技术](prompts/04-prior-art-search.md)，实际阅读对比文件，记录申请/优先权与公开日期及区别特征；没有正式查新证据不保证新颖性。
- 需要技术交底：读 [05 交底](prompts/05-disclosure-build.md)。
- 内容合并/反馈：读 prompts/iteration 下对应文件；修改稿件后原审查失效。

## 可选 CLI

在本项目目录运行；安装 `requirements.txt`；摄入 Office 再装 `requirements-ingest.txt`。

```bash
python tools/patent.py template invention -o outputs/draft.md
python tools/patent.py lint outputs/draft.md
python tools/patent.py build outputs/draft.md -o outputs/review.docx --strict
python tools/patent.py review-init outputs/draft.md --facts outputs/TECH_FACTS.json -o outputs/content-review.json
# 实际审查并补齐 JSON 后：
python tools/patent.py build outputs/draft.md -o outputs/final-review.docx --final --facts outputs/TECH_FACTS.json --review outputs/content-review.json
python tools/patent.py handoff outputs/draft.md -o outputs/cnipa-handoff --facts outputs/TECH_FACTS.json --review outputs/content-review.json
```

- 普通 build：草稿；strict：无形式 ERROR；final：本工具的审阅交付门禁，不是法律认证。
- **版面默认值即合规基线**：正文 12pt、行距 1.25 倍（实测行间空白 2.96mm，落在 2.5~3.5mm）、页码默认输出（各部分分别编号、页脚居中、下沿距底 15mm）。1.5 倍行距实测 4.32mm 已超上限，不要用；纯屏幕审阅稿才加 `--no-page-numbers`。字高与行距不能按 pt/倍数推断，须渲染后量墨迹，见 [format-spec](../../docs/format-spec.md) 与 [实测结论](../../docs/cnipa-format-lessons.md)。
- 标题字号默认 13pt（宋体墨迹约 4.3mm），与正文 12pt 同处 3.5~4.5mm 区间；14pt 实测 4.7mm 即超限，**不要把标题调大**。这些默认值由 `tests/test_layout_baseline.py` 钉住，改动会失败。
- `--final` 不允许 `--force`，缺图、待确认、未闭合 P0/P1 或过期证据均拒绝。
- `handoff` 默认 pending official conversion，包含拆分 Word、原图、审查证据与核对清单；不生成自定义 CNIPA XML。
- 机器不能证明技术现实、支持关系语义完备或创造性。不得机械填写 pass。
- 领域路由和资料清单目前由 Agent 执行；现有 CLI 不校验这些记录，也不证明各领域规则已执行。不得把新增 Skill 文档说成已修复 Python 门禁。
- 发明/实用新型摘要含标点不超过 300 字；有说明书附图时指定摘要图；拆分输出分离摘要与摘要图。
- 外观设计的 Word 是简要说明审阅稿；视图原件由 handoff 另存。不得把仅有 Word 的外观设计稿称完整申请。

## 交付

文本路径交付稿件或审阅意见、必要事实/支持笔记与待确认项；工具路径另交其事实账本、内容审查、审阅文件及需时的交接包。说明实际检查，不把内部证据标记写入正式正文。不自动提交，不保证受理或授权。工具状态仍以实际 CLI 证据为准；docs 中历史设计仅供参考。

维护本体系时运行 `python tools/check_skills.py` 检查专利兼容结构，运行 `python tools/check_word_skills.py` 检查总注册表与共享技能路径；按 [行为评测协议](references/skill-evaluation.md) 验证触发与产物。结构通过不等于生成质量通过。模块登记、改稿接入、资料需求与评测执行见 [维护工具用法](../../docs/skills-maintenance.md)，仅维护或积累资料时读取。
