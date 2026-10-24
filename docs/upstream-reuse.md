# 上游复用决策

更新于2026-10-24。本文件集中记录执行能力的主要实现和复用取舍；产品术语与完成含义见 [共用契约](06-contracts-and-states.md)。实际采用的固定提交、许可证及落点以 [来源锁定](../upstream.lock.json) 和 [第三方记录](../THIRD_PARTY.md) 为准。候选只读核查不成为已接入依赖，原件/调用检查不证明写作质量优于上游。

## 执行能力的主要实现

以已有实现为复用起点；需要自写时先指出具体缺口。不同职责可分层，同一职责不长期保留两份等价实现。以下“保留”描述当前选择，不宣称它已在同案对照中胜出。

| 能力 | 当前主要实现与调用边界 | 当前决定 |
| --- | --- | --- |
| Skill 登记与路由 | `registry/skills.yaml` → `word_skills/registry.py` / `router.py` → CLI；必需/可选依赖分开 | 保留小型声明和函数，不引入编排平台；不承担写作、环境检测或执行调度 |
| 材料读取与定位 | `word_skills/ingest.py` 处理通用文本/DOCX/PDF快照与定位；`oh_my_patent/ingest.py` 保留专利Office转换及损失提示 | 两侧格式与保留对象不同，先按任务选择；不强行互换定位和证据记录，不另写第三套摄入 |
| 软著项目分析、业务/候选、手册/字段准备 | Fokkyp 固定原件，由 `copyright_workflow.py` 隔离调用；`copyright_package.prepare` 调 analyze/business/candidates | 已直接复用，继续固定版本；本地只保留事实、路径、确认及接口适配，升级需验证钩子和行为 |
| 软著源码身份与选段 | 上游候选由 Agent 选择，`copyright_package.apply_selection` 投影为本地原件哈希和行段；`copyright.py` 校验 | 一份选择，两种用途的投影；不再独立生成第二份业务选择。上游源码抽取仅保留依赖，不负责最终分页 |
| 手册结构转为通用稿件 | `copyright_manual.py` 调用成熟的 markdown-it-py，将章节、表格、命令和声明图片投影到现有 v1 | 保留适配器，不自造Markdown解析器；不引入上游另一套Word执行器 |
| 技术/软著Word及通用交付 | `word_skills/render.py` / `delivery.py`，复用 python-docx、可选 docxtpl、外部预览工具 | 继续使用该制作链；页面、内容及业务审阅分别记录，不能由导出成功代替 |
| 专利Word与交接 | `word_skills/legacy_patent.py` 只转发到原 CLI；`oh_my_patent/render/docx.py` 与原 gate/handoff 负责专利稿件 | 保留原专利模型和交付门禁；不会因共用产品术语就迁移所有案件或互认 reviewed |
| 知识定位 | 固定原文直接阅读，必要时调用已有 knowledge/context 和RAGFlow适配 | 保持可选；不再建检索服务或新的自动事实库 |

外部工具输入输出由适配器在边界转换。适配器可以增加明确的本地事实/安全约束，但不静默改原文、捏造确认、重写上游版本或把候选扫描结果变成事实。Fokkyp 当前存在多个内部函数钩子，不能仅因代码叫适配器就当作零维护：后续升级须固定版本，核对签名、默认值、失败行为和相应回归。

## 专利执行代码候选：已读接口，未执行对照

固定来源为 [handsomestWei/patent-disclosure-skill，6935a14d342ed9c7a07440c999d1b7bf1852a701](https://github.com/handsomestWei/patent-disclosure-skill/tree/6935a14d342ed9c7a07440c999d1b7bf1852a701)，其原 MIT 许可已随已采用的方法保留。下面四份代码于本次实际读取；尚未在本项目执行，没有新增依赖或上游执行器。后续导入代码还需核对其依赖许可及实际行为。

| 固定源码 | 已核对的接口/限制 | 取舍及最小验证条件 |
| --- | --- | --- |
| [check_support.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/check_support.py) | 读取分开的权利要求/说明书/摘要文件及图件计划/件号表；依赖同包词库、图件规划与标号检查。步骤标签和名称等为机械比对，源码明确语义仍需人工判断 | 暂不整体替换现有支持/内容门禁。将来对接已有稿件时先验证真实不一致能被发现、缺少图件计划时覆盖范围明确，再决定替换对应机械检查或补足不同职责 |
| [emit_application_docx.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/emit_application_docx.py) | 按固定四类文件名调用同包 md_to_docx，含公式分隔符预检；与本地单稿解析/拆分、证据和final流程的接口不同 | 本次不引入另一套Word链。只有具体文书能力缺口和实际导出/审阅证据支持时才评估替换；不因示例好看选作胜者 |
| [math_to_omml.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/math_to_omml.py) | 使用 latex2mathml 将LaTeX经MathML转为可挂载的OMML元素；try入口失败返回None，调用方负责回退。本地所查专利正文写入路径未调用同类LaTeX到OMML生成器；已有OMML输入提取不是同一能力 | 优先列为独立复用候选，不新写转换器。验证代表公式的符号/上下标/单位保真、可编辑性和复杂宏失败可见性；证明可用后才接现有制作入口，依赖仅在选用时启用 |
| [render_invention_figures.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/render_invention_figures.py) | 读取YAML/JSON计划生成黑白SVG，PNG路径使用Playwright及可用浏览器；退出成功可仅表示SVG已生成。本地专利渲染器主要嵌入已登记图件 | 优先列为图件生成候选。验证所需图型、标签/连线、技术对应和实际版面；若任务需PNG，额外核对PNG结果，不能只看退出码。通过后复用该模块，不再另写绘图器 |

排序依据是已观察到的能力差异和接入边界，不是质量排名。此轮只交付取舍表；候选验证按具体任务另设焦点，不自动安装浏览器、LaTeX转换依赖或运行模型实验。保留现有后端是有范围的当前决定，不是永久拒绝替换。

## 软著材料

当前采用 Fokkyp 2.6 的 MIT 提交 `e78f746e0254ed4be7e9a561ce0acc7180d5370a`，保留16份原件，其中9个脚本对应7个阶段入口和2个共享/依赖脚本。业务准备链实际调用上游，不只是参考提示；最终源码分页、Word和审阅交付仍归本地既有工具。具体钩子、原因和边界见 [直接复用记录](05-fokkyp-reuse.md)。早期 `947d5963194bfda8ce57b8b454b486f13359dee4` 仅改编方法，已被本次说明及既有来源锁定替代，不能再据此写成“未使用上游执行代码”。本项目没有采用 OfficeCLI 或上游独立Word执行器。

suling-fun/software-copyright-materials-skill 的固定提交 `d7b49eea8f6e455ef3547c0d16d1945e204bc8a7` 核查了 `SKILL.md`、`verify_materials.py` 和 MIT `LICENSE`。本地吸收了“机械一致性检查”和“人工语义/权属判断”分离的原则，并增加了声明字段与源文件变化失效；没有复制它的黑名单、验证器或登记流程。

## 项目申报

caolonghao/nsfc-grant-assistant-skill 的固定提交 `a694ab4cfbf8bad64357c6803e5f39c4b0eda47a` 核查了 `ndrc-bid-assistant/` 入口和 MIT `LICENSE`。本地 `word_skills/proposal.py` 采用渠道、指南快照、要求定位、章节映射和条件证据先行，并把预算算术交给确定性校验；没有复制它的评审模型、提示词编排或提交动作。随附 NSFC Profile 是历史回归结构，状态为 expired，不能代表当前开放申报渠道。

## 其他参考

技术写作规则和设计说明方法分别来自 `Fenng/Tech-Doc-Style-Chinese` 与 `riekelt/technical-writer` 的固定提交，采用范围见 `THIRD_PARTY.md`。`official-document-drafting`、doc-coauthoring、Pandoc 模板和未明确许可的标书仓库只作比较；没有把它们的文本、字体、模板或执行代码放进发行包。

复用后的代码仍遵守本仓库的事实边界：工具能核对来源、哈希、章节、预算、代码行段和版面启发式，但不会自动确认权属、法律资格、官方受理或写作语义充分性。
