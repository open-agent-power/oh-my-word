---
name: oh-my-copyright
depends_on: [word-document]
description: 复用 Fokkyp 流程，从真实软件项目生成中文软著材料，完成业务理解、源码选择、申请字段、图文操作手册和 Word 交付。适用于软著材料生成与复核；权属和真实申请字段由用户确认。
---

# 软件著作权材料

复用 Fokkyp SoftwareCopyright-Skill 2.6 的方法和可选阶段脚本，固定提交及 MIT 原件位于 [上游记录](../../word_skills/_vendor/fokkyp/UPSTREAM.json)。选用工具时调用已纳入的脚本，不另写业务分析器、源码候选或手册生成器；保持本文的事实与接口适配。完整差异见 [复用说明](../../docs/05-fokkyp-reuse.md)。

## 先阅读，再选交付路径

确定本次是业务说明、手册、填写辅助、审阅，还是源码/Word 完整材料制作。新稿写前读 [固定来源与范围](references/domain-sources.md)，实际阅读有关规则与方法；同案修改复用已读记录，只补查变化。

- **文本起草/审阅**：按 [领域写法](references/drafting.md) 直接读材料、整理业务与操作依据、写作并复核，交付文本和缺口。无需 prepare、JSON、索引或 RAG；不称为已完成完整登记包。
- **工具制作**：需要源码摘录、结构校验、Word/PDF 或完整准备包时进入下方流程，仍满足原输入、确认、真实渲染和审阅要求。

先按 [材料使用与按需检索](../word-document/references/knowledge.md) 选择路径。少量项目材料直接阅读，首次 prepare 默认不传 `--knowledge`；需要跨来源检索规则或用户指定索引时，才用 `prepare --knowledge INDEX` 保存实际上下文。登记规则须核对来源、版本与适用性，项目功能仍从真实源码和操作取证。

同案只改手册措辞或版式时，核对输入版本后复用既有业务理解、源码选择及运行记录，修改原手册并向新目录制作；不重新 prepare、确认业务或全篇起草。新增功能、版本或效果陈述时补读相关源码和运行证据，重审受影响内容。保留已有知识绑定和审计材料；变化使原确认或审阅失效时按现有流程重新核对，不能沿用旧通过状态。

## 可选工具流程

在仓库环境或已安装 word-skills 的环境运行。`SOURCE` 是真实项目；`CASE` 是源码树之外的新目录。下列占位符须替换为本次实际值。

1. **分析与业务理解。**运行 `word-skills copyright prepare SOURCE --out CASE --name NAME --version VERSION`。它直接调用上游 analyze、business、candidates，输出 `CASE/workflow/analysis/project.json`、`CASE/workflow/草稿/业务理解证据.md/json`、模型稿模板及代码候选。读取证据及相关源码后填写模型稿；运行：

   ```text
   word-skills copyright workflow business --project SOURCE --analysis CASE/workflow/analysis/project.json --software-name NAME --model-context MODEL.json --out-dir CASE/workflow/草稿
   ```

   业务判断由 Agent完成，脚本只收集和组织证据。上游阶段细则按需读 [业务理解规则](../../word_skills/_vendor/fokkyp/references/business_understanding_rules.md)。

2. **申请信息与源码选择。**使用上游 `代码文件选择.json`，按真实用途填写 selected、model_reason；以完整文件为基本选择单位，避免零散函数凑量。阅读 [源码选择](../../word_skills/_vendor/fokkyp/references/code_selection_rules.md)，CLI、库或服务程序按真实入口及核心流程选择，不机械地优先前端。运行：

   ```text
   word-skills copyright select CASE/copyright.json --workflow-selection CASE/workflow/草稿/代码文件选择.json --reviewed-by REVIEWER
   ```

   此命令把同一选择投影成原件哈希和原始行段，不再维护第二份业务选择。候选集合不是整个登记程序；先记录程序范围和固定顺序，再决定全部交存或前后页交存。上游页数估计仅供候选选材，不用作实际页数或合规证明。姓名、日期、环境、开发方式、权利基础按 [字段适配](references/application-fields.md) 填写。

3. **操作手册。**复用上游 manual 阶段。按业务模型填写使用场景、入口、真实可见内容、动作、限制和反馈；面向软件用户写，删除生成过程说明。业务已经确认时用上游 confirm 记录实际授权依据；不能凭空记录“用户已确认”。

   ```text
   word-skills copyright workflow manual --analysis CASE/workflow/analysis/project.json --business-context CASE/workflow/草稿/业务理解.json --software-name NAME --version VERSION --out-dir CASE/workflow/草稿
   ```

   命令行软件增加 `--interface cli`；业务口径待确认但用户已授权继续起草时增加 `--preview`，不会写入用户确认。按 [手册规则](../../word_skills/_vendor/fokkyp/references/manual_structure.md) 使用其结构和检查，结合 [本地适配](references/workflow.md)。把审阅修正后的成稿保存为 `CASE/manual.md`，绑定 `copyright.json`。生成器自检是启发式检查，不能冒充独立语义审查。

4. **真实图文。**GUI 实际运行后截图；CLI 记录命令、工作目录、退出码和实际回显。日志排成图须标明“实际运行输出排版”，不能冒充原生窗口截图。使用已有浏览器/截图工具，不为截图另行安装全局依赖。上游 `workflow screenshots --input-dir IMAGES --out-dir CASE/screenshots` 可复用排序和图片清单。将图片声明到 `copyright.json.screenshots`，在手册中引用，路径相对 CASE，支持 PNG/JPEG，图中事实也须复核：

   ```markdown
   ![结果说明](screenshots/result.png)
   ```

5. **申请字段与统一制作。**可复用 `workflow fields --help` 的参数与上游字段顺序；预览加 `--preview`，并用 answers JSON提供已确认值。上游建议字数和版本习惯不当作当前官网强制要求。不得把本机检测配置自动写成开发环境，不改真实版本为 V1.0。

   字段齐备后运行 `copyright lint` 和 `copyright package CASE/copyright.json --out DELIVERY --soffice PATH --pdftoppm PATH`。缺权属等事实时明确用 `package --draft`，继续生成完整技术材料并列出缺口，不以小样替代用户要求的完整材料。两种情况都复用同一 Word 后端，保留章节、表格、命令和真实图片，不安装 OfficeCLI。

6. **检查与交付。**检查实际 Word/PDF、所有页图、源码连续性、名称版本和材料范围。正式准备包的 source/manual 分别 review-init、finalize，最后 package-finalize。draft 不能升级为正式审阅包；补齐事实后重新生成。交付源码、手册、填写辅助；原件、映射和检查记录单独留档。reviewed 不表示登记受理通过。

## 确认与事实边界

上游的 STOP_FOR_USER 代表相应信息需要真实依据；先检查本次已有授权和确认，已确认不重复询问。用户允许自动选材或继续起草时按授权执行，并记录真实审阅者；未知权属、日期及正式申请字段继续留空。需要人提供的事实不可由等待超时、仓库组织、Git日期或开源许可证代填。

上游原文保留供溯源；实际执行以本适配入口为准，特别是后端、截图工具、CLI表达和已经给出的授权。不上网提交，不修改原项目源码来隐藏日期、依赖或版权信息。旧 `copyright scan/template/lint/extract/build` 接口继续适用于原文摘录；摘录与完整交存材料必须明确区分。
