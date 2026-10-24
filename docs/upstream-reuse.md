# 上游复用决策

更新于2026-10-24。本文件集中记录执行能力的主要实现和复用取舍；产品术语与完成含义见 [共用契约](06-contracts-and-states.md)。实际采用的固定提交、许可证及落点以 [来源锁定](../upstream.lock.json) 和 [第三方记录](../THIRD_PARTY.md) 为准。候选核查或隔离试跑不等于已接入依赖，原件/调用检查不证明写作质量优于上游。

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
| 专利Word与交接 | `word_skills/legacy_patent.py` 只转发到原 CLI；`oh_my_patent/render/upstream.py` 调用固定上游转换器并套用本项目边界版式；原 `oh_my_patent/render/docx.py` 保留为本地草稿/外观设计路径 | 2026-10-24 第 32 轮起默认 `auto`：发明/实用新型走上游转换器，外观设计走本地；`--renderer local` 保留草稿占位稿；缺图/坏公式默认明确失败，见下方接入实现 |
| 知识定位 | 固定原文直接阅读，必要时调用已有 knowledge/context 和RAGFlow适配 | 保持可选；不再建检索服务或新的自动事实库 |

外部工具输入输出由适配器在边界转换。适配器可以增加明确的本地事实/安全约束，但不静默改原文、捏造确认、重写上游版本或把候选扫描结果变成事实。Fokkyp 当前存在多个内部函数钩子，不能仅因代码叫适配器就当作零维护：后续升级须固定版本，核对签名、默认值、失败行为和相应回归。

## 专利执行代码候选与制作器实测

固定来源为 [handsomestWei/patent-disclosure-skill，6935a14d342ed9c7a07440c999d1b7bf1852a701](https://github.com/handsomestWei/patent-disclosure-skill/tree/6935a14d342ed9c7a07440c999d1b7bf1852a701)，其原 MIT 许可已随已采用的方法保留。前一轮实际读取下面四份接口；用户随后同意完整制作模块试跑，已在忽略的证据目录执行未修改的 `emit_application_docx.py`、`md_to_docx.py` 及其公式/分隔符辅助模块。支持检查和计划附图生成仍未执行。2026-10-24 第 30 轮已把转换链接成可选制作路径并把 `latex2mathml`、`docxcompose` 列为运行依赖；默认后端与交付状态仍未切换，见下方接入实现。

| 固定源码 | 已核对的接口/限制 | 取舍及最小验证条件 |
| --- | --- | --- |
| [check_support.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/check_support.py) | 读取分开的权利要求/说明书/摘要文件及图件计划/件号表；依赖同包词库、图件规划与标号检查。步骤标签和名称等为机械比对，源码明确语义仍需人工判断 | 暂不整体替换现有支持/内容门禁。将来对接已有稿件时先验证真实不一致能被发现、缺少图件计划时覆盖范围明确，再决定替换对应机械检查或补足不同职责 |
| [emit_application_docx.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/emit_application_docx.py) | 按固定四类文件名调用同包 md_to_docx，含公式分隔符预检；与本地单稿解析/拆分、证据和final流程的接口不同 | 已完整试跑三组合成稿，优先整体复用制作模块。接口差异作为薄适配处理；原版的版式和失败策略未通过替换条件，不能仅按退出码切默认后端 |
| [math_to_omml.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/math_to_omml.py) | 使用 latex2mathml 将LaTeX经MathML转为可挂载的OMML元素；try入口失败返回None，调用方负责回退。本地所查专利正文写入路径未调用同类LaTeX到OMML生成器；已有OMML输入提取不是同一能力 | 已随完整转换器实跑：代表稿中生成4个可编辑公式对象，另测无效公式退回原文。对象存在不证明所有数学语义和复杂宏保真；复用完整转换器并在外层拦截不允许的回退，不重写转换器 |
| [render_invention_figures.py](https://github.com/handsomestWei/patent-disclosure-skill/blob/6935a14d342ed9c7a07440c999d1b7bf1852a701/skills/patent-application/tools/render_invention_figures.py) | 读取YAML/JSON计划生成黑白SVG，PNG路径使用Playwright及可用浏览器；退出成功可仅表示SVG已生成。本地专利渲染器主要嵌入已登记图件 | 优先列为图件生成候选。验证所需图型、标签/连线、技术对应和实际版面；若任务需PNG，额外核对PNG结果，不能只看退出码。通过后复用该模块，不再另写绘图器 |

排序依据是已观察到的能力差异和接入边界，不是质量排名。接口核查轮仅交付取舍表；后续获准试跑只在证据目录装入小型依赖，没有安装浏览器或运行模型实验。原后端继续可用是替换条件尚未满足，不是永久拒绝复用。

### 2026-10-24 同内容制作对照

本地实现身份为 `9d116c3b1d3daa0b874b835dab694eb46583070d`，上游为上述固定原件，未打补丁。使用三组明确标注的合成材料：普通文字、公式表格、已存在的附图加长文。正文来自同一组字段，分别投影到本地 PatentDraft 和上游分文书 Markdown；标题、章节外观和自动附图说明属于各自的接口表现，不是逐字相同的输入文件。没有运行模型写作，也不把合成稿当作原创交底或真实申请。

普通文字和公式组两侧各生成3份文书；附图组本地生成5份、上游生成4份，共21份DOCX。实际用 `render_docx.py`、LibreOffice 26.8.1.1及Poppler渲染6份说明书和2份附图，共13页；逐页联系表和关键整页均已查看。正文定位标记与长文30个片段/结尾均在PDF中找到，未检出页面外字符；这只是哨兵与页面边界检查，不是全文语义等价认证。所有权利要求、摘要文书仅生成并检查对象，未全部渲染，也未在Word/WPS客户端验收。

| 项目 | 本地现有制作器 | 上游未修改制作器 | 结论 |
| --- | --- | --- | --- |
| 普通文字 | A4、黑色标题，1页 | Letter、蓝色标题，1页 | 原版版式不能直接替换；页数相同不代表样式相同 |
| 公式与表格 | 1张表，LaTeX按原文显示，0个OMML对象 | 1张表，4个OMML对象，LibreOffice中可见公式结构 | 上游在这组公式上有明确能力收益；已核对原生公式结构及显示，未做Word/WPS编辑往返，不代表复杂公式全覆盖 |
| 长文与已有附图 | 说明书4页，附图1页、1张图；另生成摘要附图 | 说明书3页，附图1页、1张图；默认4文书入口未另生成摘要附图 | 两侧未见本组文字截断，图件均可见；字号、纸张和行距不同，不能把页数减少当作质量提高 |
| 无效公式负例 | 本轮不对其失败策略排名 | `emit_application_docx.py` 返回0，正文仍为原始LaTeX，stderr为空 | 外层必须读取公式结果/产物，不能信任退出码 |
| 缺图负例 | 本轮不对其失败策略排名 | 返回0，产物写入“图片缺失”标记 | 制作完成前必须明确拒绝缺图或保留不完整草稿状态 |
| 普通括号误写LaTeX负例 | 本轮不对其失败策略排名 | 返回1，拒绝该文书并输出定位 | 该检查可直接复用，不能据此推断所有公式错误都会拦截 |

决定：**优先复用上游完整转换模块，补薄适配并核验后再切换默认制作路径。** 不再以“接口不同”或已有测试数量作为保留自有排版的理由。接入前的具体缺口是：沿用现有A4/黑色标题等制作配置；显式拦截不允许的公式退回和缺图；映射现有文书/摘要附图、来源与选用参数，并保留外层审阅/交接。旧案卷兼容不要求保留旧排版算法。以上适配尚未进入生产路径，不能称为已切换或整体评测通过。

### 2026-10-24 接入实现（第 30 轮）

上游制作链在第 30 轮先接成**显式可选路径** `oh-my-patent build … --renderer upstream`（第 32 轮改为默认 `auto`，见下节），当时默认路径保持本地排版。原件逐字节保存在 `oh_my_patent/render/_vendor/patent_application/`（`md_to_docx.py`、`math_to_omml.py`、`latex_delimiters.py`、`stdio_utf8.py`、`emit_application_docx.py` 及 MIT LICENSE），SHA256 与上游 `6935a14d` 一致并写入 `UPSTREAM.json`；`oh_my_patent.render.upstream` 在每次制作前校验，哈希不符即拒绝。适配层只负责：稿件→四类 Markdown 投影（章节组装复用本地渲染层的同一实现）、调用上游 `convert_md_to_docx`、边界版面与失败门禁；原文解析、表格和公式转换没有重写。

边界版式沿用现有配置：A4（210×297 mm）、页边距 25/25/15/15 mm、标题与正文黑色、宋体正文 12 pt、1.5 倍行距、2 字符首行缩进、标题字号 22/16/12/12 pt；上游自动编号列表在边界还原为纯文本编号（本项目不用 WPS 不可靠的 `numPr`）。失败门禁：公式回退为原文、含公式但无 OMML 对象、缺图/图片无法嵌入、普通括号 LaTeX、外观设计均明确失败，不生成「成功」产物。

实测：4 组合成内容（普通、公式+表格、附图+长文、实用新型）生成 4 份单文件 DOCX；LibreOffice 26.8 实际渲染 17 页并逐页查看。核对结果：A4、页边距、标题字号/黑色、12 pt 正文、24 pt 首行缩进、`numPr=0`、蓝色像素计数 0、4 个原生 OMML、表格 3 行（含公式单元格）、图件可见、长文 30 段与结尾标记可在 PDF 定位。负例（坏公式回退、缺图、普通括号 LaTeX、外观设计）均被拒绝。证据（`audit.json`、逐页 PNG、PDF、运行日志）在忽略目录 `.agent/evidence/patent-upstream-20261024/`；本机 LibreOffice 必须把 `TEMP/TMP/HOME/XDG_*` 指向可写工作区目录，否则会报「source file could not be loaded」。

第 30 轮交付时默认未切换：上游对缺图/坏公式的严格拒绝，与现有「非 `--strict` 草稿允许占位句继续出稿、`--force` 可强制」的契约冲突（示例稿件本身含未登记图件的附图说明）。已知限制：外观设计不支持；`latex2mathml` 对部分畸形 LaTeX 仍会产出公式对象（不是回退，门禁无法判定数学语义）；LibreOffice 中块级公式的可见位置与 Word 可能不同；未做 Word/WPS 编辑往返、复杂公式全集和正式提交兼容验收。

安装态验收：`tools/check_installed_delivery.py` 于仓库外安装的 wheel 环境中，用纯文本发明稿执行默认 `auto`（断言使用固定上游、A4、三类文书与正文标记）、外观设计默认本地回落、以及显式 `--renderer local`；固定 commit/原件哈希同时校验。CI 的 Linux 3.10/3.12、Windows 3.12 矩阵和隔离 wheel 任务都会执行该步骤；本机沙箱里仓库外可写目录受限，本地执行时用工作区内的仓库外目录模拟同一流程。

### 2026-10-24 第 32 轮：默认切换（auto）

在可选路径基础上，用更接近真实的复杂合成稿复核：发明稿 5 项权利要求（含 4 项从属与多项引用）、结构化发明内容、内联/块级公式、含公式单元格的表格、2 幅附图；实用新型 2 项权利要求 + 1 幅附图；外观设计稿件上游拒绝、本地可出稿。两稿共 9 页实际渲染并逐页查看：A4、页边距、黑色标题、12 pt 正文、24 pt 缩进、`numPr=0`、蓝色像素 0、发明稿 4 个原生 OMML、表格 3 行、图件可见；未发现新的映射缺口。

据此把默认制作器改为 `auto`：发明/实用新型使用固定上游转换器，外观设计回落本地；不可用稿（缺图、公式回退、无 OMML、裸括号 LaTeX）默认**明确失败并提示 `--renderer local`**，不自动回退、不改变交付状态。`--renderer local` 保留用于含占位句的草稿审阅稿，旧命令与参数不变。该行为由 `tests/test_patent_upstream_render.py` 与 `tests/test_knowledge_context.py`（共 28 项相关用例）以及安装态 `tools/check_installed_delivery.py` 固化，并随 CI 三平台矩阵执行。

仍然成立的限制：Word/WPS 编辑往返、复杂公式全集、真实案卷与正式提交兼容未验证；本机渲染只覆盖 LibreOffice 26.8，块级公式可见位置可能与 Word 不同；外观设计不支持该路径。本轮只切换 `build`；`handoff` 仍显式使用本地排版（官方 XML 转换兼容未验证），两者是否统一留作后续轮次。

### 2026-10-24 第 33 轮：完整验证与修复

对默认 `auto` 路径做了选项矩阵与边界输入的完整验证：`--font / --font-size / --line-spacing / --page-numbers / --no-part-titles / --no-page-breaks / --subsection-style keep|flatten / --type / --split / --json / --renderer local|upstream` 逐项执行并核对产物；split 的 5 份文书（含说明书附图、摘要附图）全部实际渲染并查看；PNG/JPG 可嵌入，SVG 明确拒绝；表格转义竖线在边界还原为 `|`；知识绑定（`--knowledge`）与默认 upstream 组合生成 receipt 并实际走上游。

验证中发现并修复三处问题：`--json` 的 stdout 被制作器/产物提示污染、`--no-part-titles` 对说明书附图文书无效、表格单元格转义竖线残留反斜杠；另修正 `latex2mathml` 的许可文案（MIT，不是 MIT-0）。新增选项矩阵、JSON 纯净性、JPG/SVG、转义竖线、知识绑定等回归测试。

试跑使用Codex随附Python 3.12、python-docx 1.2.0；latex2mathml 3.81.1、PyYAML 6.0.3当时仅装在本机忽略的 `.agent/evidence/patent-render-trial-20261024/deps/`，不修改当时的项目虚拟环境或发行依赖；第 30 轮接入后 latex2mathml 与 docxcompose 已列入 pyproject 运行依赖。证据同目录保存源SHA256清单、fixture、运行命令/日志、21份生成物、PDF/页面、对象与哨兵检查、3个负例；脚本为 `fetch.py`、`trial.py`、`render_trial.py`、`negative.py` 和 `audit.py`。首轮PDF文字提取因捆绑Poppler不含pdftotext而失败，改用随附pypdf后全部完成，未把失败写成第一次即通过。计划附图生成器只下载审查，图中采用预先制作的合成图，不宣称自动制图链已验收。

## 软著材料

当前采用 Fokkyp 2.6 的 MIT 提交 `e78f746e0254ed4be7e9a561ce0acc7180d5370a`，保留16份原件，其中9个脚本对应7个阶段入口和2个共享/依赖脚本。业务准备链实际调用上游，不只是参考提示；最终源码分页、Word和审阅交付仍归本地既有工具。具体钩子、原因和边界见 [直接复用记录](05-fokkyp-reuse.md)。早期 `947d5963194bfda8ce57b8b454b486f13359dee4` 仅改编方法，已被本次说明及既有来源锁定替代，不能再据此写成“未使用上游执行代码”。本项目没有采用 OfficeCLI 或上游独立Word执行器。

suling-fun/software-copyright-materials-skill 的固定提交 `d7b49eea8f6e455ef3547c0d16d1945e204bc8a7` 核查了 `SKILL.md`、`verify_materials.py` 和 MIT `LICENSE`。本地吸收了“机械一致性检查”和“人工语义/权属判断”分离的原则，并增加了声明字段与源文件变化失效；没有复制它的黑名单、验证器或登记流程。

## 项目申报

caolonghao/nsfc-grant-assistant-skill 的固定提交 `a694ab4cfbf8bad64357c6803e5f39c4b0eda47a` 核查了 `ndrc-bid-assistant/` 入口和 MIT `LICENSE`。本地 `word_skills/proposal.py` 采用渠道、指南快照、要求定位、章节映射和条件证据先行，并把预算算术交给确定性校验；没有复制它的评审模型、提示词编排或提交动作。随附 NSFC Profile 是历史回归结构，状态为 expired，不能代表当前开放申报渠道。

## 其他参考

技术写作规则和设计说明方法分别来自 `Fenng/Tech-Doc-Style-Chinese` 与 `riekelt/technical-writer` 的固定提交，采用范围见 `THIRD_PARTY.md`。`official-document-drafting`、doc-coauthoring、Pandoc 模板和未明确许可的标书仓库只作比较；没有把它们的文本、字体、模板或执行代码放进发行包。

复用后的代码仍遵守本仓库的事实边界：工具能核对来源、哈希、章节、预算、代码行段和版面启发式，但不会自动确认权属、法律资格、官方受理或写作语义充分性。
