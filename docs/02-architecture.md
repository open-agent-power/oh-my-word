# 技能划分与代码架构

状态：目标架构的当前整合实现。本文仍区分代码/契约实现、真实产物验收和法律/业务判断。

产品术语、来源责任与完成含义集中在 [现行契约与状态](06-contracts-and-states.md)，本页说明实现分层，不另造一套状态模型。注册表已分开必需和可选 Skill 依赖，CLI list/route 对外保留两类信息；这不自动装载工具或证明环境可用。旧案件、两侧 JSON/审阅格式、命令名与制作后端保持兼容。

## 领域 Skill 与可选工具（2026-10-24）

技术报告、软著和专利三个入口已区分文本写作与工具制作。完整仓库资源可供 Agent 阅读，文本路径无需本项目 Python、JSON 或 RAG；这是一组指令和参考资源的调整，没有引入新编排器或更换后端。

| 层次 | 当前职责与资源 | 验证边界 |
| --- | --- | --- |
| 领域写作核心 | 三域 Skill 入口、材料组织方法、注释案例和审阅问题；由 Agent 判断、起草、复核 | 资源/引用已检查，不等于模型实际遵从或专业质量提高 |
| 写前来源 | 各域 `references/domain-sources.md` 指向实际核查的原文和章节，按 [共用阅读规则](../shared/references/source-reading.md) 直接读或限定官方来源检索 | 规则、方法与项目事实分开；同案复用，受限原文留缺口。没有增加数据库、索引或常驻抓取 |
| 可选程序与文件制作 | 原有摄入、JSON、来源校验、软著阶段脚本、专利 CLI、Word/PDF 和各自审阅状态 | 选择后仍满足原契约与门禁；文本自查不获得 reviewed/final，不执行工具就不声明其检查通过 |
| 可选知识检索 | 原固定包、本地检索和 RAG 适配保留，具体资料定位需要时再用 | 不作为三域写作前置条件，不自动更新案件或改变知识配置 |

写作入口见 [技术文档](../skills/oh-my-technology/SKILL.md)、[软著](../skills/oh-my-copyright/SKILL.md)、[专利](../skills/oh-my-patent/SKILL.md)。下面的 JSON、渲染、状态和兼容分层描述仍适用于选择程序制作的路径；并非文本写作必须经过的流程。来源、许可及取舍见 [调研](skills-ecosystem-review.md) 和 [第三方记录](../THIRD_PARTY.md)。

## 当前架构核对与支持范围（2026-10-23）

工具制作主链路为原件/实际运行记录 → Agent正文与证据 → 确定性校验 → DOCX → PDF/页图 → 内容及页面复核 → 定稿。新增CI与独立wheel验收检查工程可用性，不执行模型质量评分或代填人工通过。资料少时直接读取并复用案件记录，检索保持可选；固定知识包新增只读维护/召回检查，不自动更新案件或活动索引。

本次对两套后端的判断是保留兼容分层：`word_skills/legacy_patent.py`只转发到专利CLI，专利拥有稿件解析、专利版式和final/handoff；通用包拥有JSON v1、来源快照、通用制作与reviewed。两侧都处理变化失效，但状态语义不等价，不能直接合并审阅记录。软著临时路径差异已通过具体反例修正；当前没有据此发现必须迁移全部专利模型的跨后端错误。共享函数后续仅在出现同一规则的可复现分歧时提取，不为统一目录迁移旧案件。

| 层面 | 当前可验收内容 | 保留边界 |
| --- | --- | --- |
| 安装与回归 | Linux/Python 3.10、3.12与Windows/Python 3.12完整检查、仓库外wheel命令和合成制作；Linux真实PDF/页图CI已运行 | 环境范围以实际run及产物为准；wheel不包含全部Skill文案，依赖版本报告不等于跨平台锁文件 |
| Agent执行 | 程序校验输入/来源/产物身份、要求和复核记录，原始工具输出可保留 | 不能证明任意Agent真的阅读或正确理解；context-only模型试验不证明工具遵从，哈希不构成OS权限隔离 |
| 内容质量 | 可逐项核对源码、真实命令、引用和条件，失败后另存修订 | 新样本仍出现真实引文下的错误过程解释，单独指示修复未成功；不得称自动语义认证或专业风格普遍提升 |
| 版式 | 默认文字显式黑色；已测LibreOffice/WPS产物；单节基本样式和受限插槽模板 | 用户蓝色标题界面原因尚未复现；Word/其他版本未测，超高行、复杂模板和表格内富文本未提供通用保证 |
| 知识维护 | 固定包原件校验、采集日期提示、指定查询回归、候选与旧包分开、失败不切后端 | 采集日期不证明现行有效；原规则包两项指定来源漏召回保留，知识命中不认证业务事实 |
| 正式业务 | 软著与专利技术草稿、来源映射与明确缺口 | 权属、日期、当期表单、原创交底、查新及专业判断不能由公开源码代填 |

当前没有必要引入新的Agent编排框架、强制RAG或账户审批系统。实际工程证据与未关闭条件见 [推进计划](writing-delivery-plan.md)；工程可复现、任务内容正确和正式业务可提交分别判断。

## 0. 当前落地状态（2026-10-15）

本仓库已由原 `oh-my-patent` 工作树整合成 `oh-my-word` / `word-skills` monorepo。根目录结构与六主技能目标一致；实现状态与模式成熟度分开记录，不能把“有入口和契约”理解为“所有模式同等成熟”。

| 目标 | 当前实现 | 证据与边界 |
|---|---|---|
| `word-skills` 路由入口 | 注册表驱动的 `skills/word-skills/SKILL.md`、`registry/skills.yaml` 与确定性 CLI 路由 | `tests/test_word_skills.py`；路由匹配不代替 Agent 的语义判断 |
| `oh-my-technology` | 七种 JSON v1 模式及来源、内容、Word/PDF 交付流程；技术报告和设计说明为重点模式，另外五种为 baseline 扩展模式 | `tests/test_pipeline.py`、`tests/test_technology_modes.py`、`registry/skills.yaml`；扩展模式的真实客户模板与跨环境版式仍需试运行 |
| `word-document` | 单节基本样式、有限模板插槽、预览与逐页审阅记录 | `skills/word-document/`；不代表任意企业模板或所有 Office/WPS 版本已验证 |
| `oh-my-patent` | 原 Python 包、旧 CLI、主 Skill、六领域 Skill、领域注册表和 final/handoff 门禁保留 | `tests/test_final_gate.py`、`tests/test_skill_bundle.py`；六领域保持 `experimental` |
| `oh-my-proposal` | 指南 Profile、要求/章节/附件/人员/预算校验和共享 build 适配 | `word_skills/proposal.py`、`tests/test_proposal.py`；随附 NSFC 2026 Profile 是过期历史结构 |
| `oh-my-copyright` | 源码扫描、敏感信息排除、哈希/行段校验、手册/字段一致性、摘录与共享 build 适配 | `word_skills/copyright.py`、`tests/test_copyright.py`；页数、权属和当期登记规则仍需人工核对 |

主注册表共六项，均有实现路径；技术模式的 `mode_scope` 进一步区分重点与 baseline 扩展，专利领域另有六项实验性 Skill。`tools/check_word_skills.py` 与 `tools/check_skills.py` 验证路径、frontmatter、注册表和引用；自动化测试验证代码行为，不是写作质量、法律权属或受理结论。

整合决策与兼容边界：

- 专利代码及 `tools/patent.py` 入口保留；`python -m word_skills patent ...` 与 `oh-my-patent` console script 转发给旧 CLI，不把专利模型放进公共文档渲染层。
- 专利 Skill 资源移到 `skills/oh-my-patent/`，域注册表、prompt、参考和评测使用新路径。六领域仍是实验状态，未因迁移升级。
- 技术文档的 `draft.json`、`source-index.json`、`evidence.json` 继续以 `schema_version=1` 为现行数据契约。`validate_*_v1` 负责结构边界；新增字段或版本迁移须显式兼容，不批量重写既有审阅材料。
- `models.py` 中 `CaseManifest`、`Requirement` 等 dataclass 是扩展 DTO，并非现有 JSON v1 的替代序列化格式。当前管线仍以原 v1 字段和校验为准；需求到章节/附件映射及跨业务单位约束不能视为统一模型已落地。0.3.0 的可选 case_id/document_id 已绑定到稿件与交付 manifest；这只是可兼容的身份增量，不是全部扩展对象迁移。
- 两种材料摄入路径保持独立：专利旧流程沿用原转换与专利证据格式；技术文档流程使用 MarkItDown 与独立来源定位/损失提示。它们不共享未经验证的定位或审阅状态。
- 技术文档交付状态是 `blocked`、`failed`、`draft`、`awaiting-review`、`reviewed`。这里的 `reviewed` 只表示完整性门禁通过且已记录内容/页面审阅，不证明事实真实性或正式提交。
- `docs/upstream-sources.json` 是候选研究记录；`upstream.lock.json` 列出实际改编的文字规则和本轮已测直接运行依赖。候选没有自动变成依赖，许可证副本与改编说明见 `THIRD_PARTY.md`。
- wheel 包含 Python 包、章节 schema 和路由元数据快照；完整 Skill 文案与相对资源的受支持读取方式仍是仓库 monorepo。复制单个 Skill 文件不构成完整安装。

2026-10-16 增量：软著增加 prepare/select/package/package-finalize，共享制作层分别生成源码与手册，根包绑定申请辅助 TXT、实际页数与子交付。可选 case_id/document_id 进入现行 v1 稿件和 manifest，旧稿兼容；业务待绑定状态与不可定稿 preview 草稿见 [契约与状态](06-contracts-and-states.md)。这不代表全部扩展 DTO 已成为统一存储格式。

## 1. 六个主技能

| 技能名 | 用户任务与产物 | 边界 | 建设方式 |
|---|---|---|---|
| `word-skills` | 不明确文档类别、一个项目要多份材料时，识别目标并按需组合能力 | 不重复起草各业务全文；明确业务请求可直达相应技能 | 新增总入口 |
| `oh-my-technology` | 技术报告、设计说明、需求、接口、测试、操作和运维文档 | 不承担专利权项或申报资格判断 | 新增，当前优先 |
| `oh-my-patent` | 技术交底、专利点、发明/实用新型/外观设计申请审阅稿与交接包 | “专利申请撰写”和“专利撰写”统一于此；保留原有业务门禁 | 迁入已有入口和 6 个领域模块 |
| `oh-my-proposal` | 项目立项/申报书、可研材料、任务分解、预算说明及附件清单 | 按受理机构与年度指南选择 Profile；技术标书不默认当项目申报 | 新增 |
| `oh-my-copyright` | 软件著作权申请字段草稿、真实源码材料、软件说明/操作手册和交接清单 | 不生成虚构源码；普通操作手册仍走技术文档技能 | 新增 |
| `word-document` | 将已写好的内容排成 Word，使用模板、调整样式、检查版面 | 不创造业务事实，不把排版成功当作内容合规；业务技能按需调用 | 新增共享制作入口 |

计数：6 个主技能 = 4 个业务 + 1 个路由 + 1 个制作。加上既有专利子技能 6 个，当前仓库共 12 个 SKILL.md；其余写作阶段、技术文档模式、字体规则和检索操作均用参考文件或代码模块承载。

总入口不是所有任务的强制前置。明确“写测试报告”时直接使用技术文档技能；明确“只调页眉”时使用 Word 制作技能。跨业务任务共享经过核对的来源，不自动共享每份文档的结论或完成状态。

## 2. 技术文档的七种模式

| 模式 | 核心问题 | 最低可交付内容 | 独立核对重点 |
|---|---|---|---|
| technical-report | 做了什么、证据如何支持结论 | 背景、目标、方法、结果、分析、局限、结论与引用 | 指标定义、测量条件、单位、结果来源 |
| design-spec | 怎么实现，为什么这样设计 | 范围、架构、组件、数据流、关键设计、异常、部署约束与取舍 | 已实现/拟设计的区别；接口与组件关系 |
| requirements-spec | 应当完成什么，如何验收 | 角色、场景、功能/非功能需求、约束与验收准则 | 需求编号、可验证条件、优先级与边界 |
| interface-spec | 系统怎样交互 | 接口契约、字段、类型、鉴权、错误、请求响应例及版本 | 代码或接口定义支持；示例与真实字段一致 |
| test-report | 什么环境下验证了什么 | 环境版本、用例、方法、执行结果、缺陷与结论 | 未执行不能标通过；测试计划与结果报告区分 |
| user-manual | 用户怎样完成任务 | 使用条件、角色、任务步骤、界面、异常和反馈 | 真实页面/操作证据；没有截图时明确缺口 |
| operations-manual | 怎样部署、运行与恢复 | 安装配置、监控、备份、升级、回滚、故障排查 | 版本、命令、凭据保护、恢复和前置条件 |

技术报告应覆盖软件、硬件、制造工艺等技术领域，不限于软件 README；第一阶段选软件项目样本验证工具链。后续领域参考按真实需求增加，不预先复制专利六领域为另一套六技能。

新建完整稿的共用流程：明确受众/目的/模板 → 原件与材料登记 → 事实、需求及缺口梳理 → 选择模式和章节 → 起草并绑定证据 → 内容复核 → DOCX 生成 → 实际渲染检查 → 交付及变更记录。局部修改仅执行相关步骤。

2026-10-17 软著流程更新：直接纳入Fokkyp 2.6的业务阶段脚本，保留统一制作架构。调用链为 `copyright prepare → 上游analyze/business/candidates → Agent业务模型与同一份选材 → workflow manual/fields → copyright build/package → 共享Word制作与审阅`。`copyright_workflow.py`只适配CLI、已有授权、事实及路径边界；`copyright_manual.py`复用markdown-it-py将章节、表格、命令和本地图片投影到现行v1稿件；`_vendor/fokkyp/`保存原件和MIT。原有专利后端、技术文档模式和Word后端不分叉。图片进入同一审计快照，兼容旧无图片稿件。详细复用范围见[吸收记录](05-fokkyp-reuse.md)。

## 3. 目标仓库目录

当前仓库是 `open-agent-power/oh-my-word` 对应的 monorepo；Python distribution 名称保持 `word-skills`。技术文档代码、Skill 资源与专利后端共用同一 Git 历史。

```text
oh-my-word/                        # 当前 GitHub 仓库
├─ README.md
├─ pyproject.toml                  # 安装共享 CLI 和 Python 代码
├─ LICENSE
├─ THIRD_PARTY.md                  # 依赖与实际改编来源
├─ upstream.lock.json              # 实际纳入的上游，不等同本轮候选清单
├─ skills/
│  ├─ word-skills/SKILL.md
│  ├─ oh-my-technology/
│  │  ├─ SKILL.md
│  │  ├─ agents/openai.yaml
│  │  └─ references/               # 写作流程与 7 模式
│  ├─ oh-my-patent/
│  │  ├─ SKILL.md
│  │  ├─ prompts/
│  │  ├─ references/
│  │  └─ domains/                  # 原有 6 个领域 SKILL.md 和 registry
│  ├─ oh-my-proposal/              # 指南映射、目标/任务、预算、附件
│  ├─ oh-my-copyright/             # 项目证据、源码选择、手册和字段
│  └─ word-document/               # DOCX 后端选择、模板、修订和视觉核对
├─ shared/references/              # 共用事实/引用/写作及文档交付契约
├─ registry/skills.yaml            # 名称、路径、路由、依赖、实现状态
├─ word_skills/
│  ├─ cli.py
│  ├─ models.py                    # DocumentDraft、Source、Fact、Review
│  ├─ ingest.py                    # 来源摄入和哈希快照
│  ├─ evidence.py                  # JSON v1 证据/数字/来源校验
│  ├─ technology.py                # 新技术模式的独立记录检查
│  ├─ proposal.py                  # 指南/预算业务层
│  ├─ copyright.py                 # 源码/权属声明业务层
│  ├─ copyright_package.py         # 准备/选择/源码+手册整套交付
│  ├─ business.py                  # 业务结果绑定到共用审阅 manifest
│  ├─ render.py, inspect.py        # Word 制作与 PDF/页图检查
│  ├─ delivery.py                  # build/review/finalize
│  └─ legacy_patent.py             # 原专利入口适配
├─ oh_my_patent/                   # 初期原代码保留，逐步抽取共享函数
├─ tools/
│  ├─ patent.py                    # 保留旧入口兼容
│  └─ check_skills.py              # 迁移后扩展路径和依赖校验
├─ tests/                          # 代码单测、产物/兼容回归
├─ evals/                          # 用户任务、材料、评分标准及执行记录
├─ examples/                       # 合成或获准公开的样本
└─ docs/                           # 架构、维护、迁移、许可证来源
```

只创建开始实现时真正需要的文件。目录图不是要求生成空占位文件的清单。Python 初期采用与现仓库相符的平铺包布局，避免把业务扩展与 `src/` 迁移混在一起。

## 4. 代码职责和依赖方向

```text
用户材料 → ingest → 来源/事实/要求
                       ↓
业务 Skill + 业务规则 → 稿件与证据映射
                       ↓
内容检查 → render(Profile) → DOCX → 渲染页/版面核对 → 交付包
```

- Skill 指挥 Agent 理解材料、选择结构、组织正文和复核语义；Python 不通过关键词堆出“自动撰写”的假能力。
- 共用工具不 import 专利领域规则；专利适配器可 import 旧包，共用层不反向依赖 `PatentDraft`。
- 第一版不建立通用插件框架、数据库、Web 服务或向量库。注册表 + Python 函数足以支撑这些任务。
- 新生成文档默认 python-docx；用户有固定表格模板时评估 docxtpl；其他转换需要时启用 Pandoc。不得将任一可选后端列为所有技能的必装前置。
- Word 排版操作以文档对象/OOXML 处理，Markdown 用成熟 AST 解析器选型，避免继续扩大专利章节正则解析器。具体解析库在实现时按表格、代码块、公式样例比较确定。
- 图片使用已有素材、真实截图或明确标注的示意图。实验图从真实数据生成；不给技术文档设置统一的图片配额。

## 5. 最小数据契约

以 JSON 和 Markdown 为主。技术文档现行结构由七份 YAML 章节 schema、五种独立记录检查与 JSON v1 运行时校验共同约束；申报/软著另有业务输入契约并投影到共用 Word 链。下表中的跨业务对象部分仍是目标模型，不等于所有 dataclass 都已成为现行序列化格式。

| 对象 | 核心字段 | 意义 |
|---|---|---|
| CaseManifest | schema_version、case_id、document_kind、mode、audience、template、deliverables | 项目目标和本次范围；多份文档分别标识 |
| Source | id、path/url、sha256、locator_kind、retrieved_at、conversion_notices | 区分原件和转换结果；网页记录读取日期及证据片段 |
| Fact | id、statement、source_ids、locators、verification_status、assertion_kind | 核验状态与已实现/拟议/目标/实测分开，不把计划变成结果 |
| Requirement | id、text、source_id、locator、applicability、target_sections | 指南/需求对应到稿件位置；不把官方要求当项目已有能力 |
| DocumentDraft | id、document_kind、title、version、section_ids、assets、profile_id | 一致的元数据，正文可保存为带稳定段落标识的 Markdown |
| TraceMap | draft_id、section/block_id、fact_ids、requirement_ids | 可定位正文与证据，内部 ID 默认不印入正式正文 |
| Review | draft/source/asset/template hashes、scope、checks、findings、reviewed_at、reviewer | 修改证据或模板使相关审查过期；语义审查与排版审查分开 |
| BuildManifest | inputs、tool_versions、profile_hash、outputs、output_hashes、render_backend | 可复现输入；跨引擎不要求 DOCX 二进制完全相同 |

业务扩展：专利保留 `claim_support/design_support`；申报增加 `requirement_response/work_packages/budget`；软著增加 `code_selection/application_fields`。普通技术报告不需要填权利要求结构。

## 6. 后续命令接口草案

**以下命令是目标接口草案。当前安装、路由及已实现技术文档命令见根目录 README；不要把本节当作可执行使用说明。**

```text
word-skills init --kind technology --mode technical-report --out CASE_DIR
word-skills ingest INPUT --case CASE_DIR
word-skills template --kind technology --mode design-spec --out DRAFT_MD
word-skills lint DRAFT_MD --case CASE_DIR
word-skills build DRAFT_MD --profile PROFILE --out DOCX_PATH
word-skills review-init DRAFT_MD --case CASE_DIR
word-skills verify DRAFT_MD --case CASE_DIR --review REVIEW_JSON
word-skills bundle --case CASE_DIR --document DOCUMENT_ID --out OUTPUT_DIR
```

不设计一个声称“自动完成全部写作”的 `generate-all`。Agent 负责写作；CLI 提供可验证的材料、检查和产物操作。旧 `python tools/patent.py ...` 与 `oh-my-patent` 命令保留。

交付状态建议：`draft`（可有显式缺口）、`review-ready`（完成本次约定的内容审查和输出核对）、`handoff-ready`（另满足业务交接清单）。状态不能等同已申请、已提交、已受理或已获批。渲染器无法运行时可以交付内容草稿，但须记录版面未验证，不能自动升级为已验证交付。

## 7. 技能安装与发布

- 维护态使用一个 monorepo，引用以当前技能文件位置解析，不能硬编码开发者 Windows 路径。
- 六个主技能分别提供 SKILL.md；总入口明确读取被选模块，不能假定宿主自动发现嵌套目录。
- 第一版以完整仓库安装/读取为受支持形态，Python 工具安装一次。文档中明确路径及运行环境，不把裸复制一个 SKILL.md 宣称为完整安装。
- 后续如提供单技能 zip，构建器必须打包所需共享参考、模板、许可及依赖说明；技能包隔离验证，不允许 `../../shared` 指向包外失效文件。
- 专利领域模块由专利主入口按路径读取，保持当前组合逻辑；无需为每个领域启动一个 Agent。
- 上游纳入记录必须含仓库、提交、文件、许可、落地路径、修改摘要及验证结果。候选调查记录与实际导入锁文件分开维护。
