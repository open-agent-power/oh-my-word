# 外部 Skills 体系调研与吸收决定

## 三领域复用调研（2026-10-24）

后续执行模块核查已集中到 [主要实现与复用取舍](upstream-reuse.md)：实际读取固定版本的支持检查、Word导出、OMML及附图生成接口。本文件保留方法调研，执行归属以该表为准；候选尚未导入或实跑，不能据此认定整体优于现有实现。

本节替代下方旧调研的“下一步”顺序，执行主线见 [推进计划](writing-delivery-plan.md)。本轮实际读取作者仓库文件、许可证、官方课程/手册及规范原文，没有安装第三方工具、调用模型写作或运行候选脚本。GitHub API 固定当次默认分支提交，相关 raw 文件逐份取回；网页通过 Firecrawl 读取，部分来自其2026-10-22至24缓存，不等于法律时效认证。原始仓库树、22份文件及哈希和访问观察保存在本机忽略的 `.agent/evidence/domain-reuse-20261024/`；下列固定链接供他人独立复核。

### 基线与采用决定

技术报告已有报告/设计参考、Fenng 中文表达规则及 riekelt 设计审阅方法；软著已有 Fokkyp 阶段脚本和本地事实适配；专利已有交底、权项支持、领域子 Skill 和正式制作门禁。主要缺口是入口仍将写作绑定到 JSON/CLI，领域来源阅读没有统一的按任务入口，方法与案例需要进一步解释。研究目标是补这些缺口，不更换已经可用的制作后端。

| 来源与固定身份 | 实际核查内容 | 决定与落点 | 适配、维护与局限 |
| --- | --- | --- | --- |
| [riekelt/technical-writer，85e53729dd959a2795d593d6769068e342cf3486](https://github.com/riekelt/technical-writer/tree/85e53729dd959a2795d593d6769068e342cf3486)，MIT | `plugins/technical-writer/skills/technical-writing/SKILL.md`、其 `references/truth.md`、`reviewing-technical-prose/SKILL.md` 和 LICENSE | 继续已有来源，补用受众/目的先行、事实与建议分开、按具体缺陷最小修订、逐结论核对来源的方法，落在现有技术报告参考 | 文本适配，无新运行依赖；不采用英文禁词、标点偏好、所有文稿强制加载或其统一严重度规则；未验证其模型效果 |
| [Xamfonos/technical-writing-best-practices，4c8e8ca5c1fd766386fad2b4a42d483d708ff066](https://github.com/Xamfonos/technical-writing-best-practices/tree/4c8e8ca5c1fd766386fad2b4a42d483d708ff066)，MIT | `SKILL.md` 的结构、教学、论证、检查表及 `technical-writing-style-guide.md` 对应内容，LICENSE | 本次不新增采用。其教程顺序和实例建议与已有能力重叠 | 面向开发者文章；强调确定表达的部分需要额外限制以免弱化未知状态。长篇风格指令的新增维护收益不足；不是技术报告效果证据 |
| [Fokkyp 已采用版本 e78f746e0254ed4be7e9a561ce0acc7180d5370a](https://github.com/Fokkyp/SoftwareCopyright-Skill/tree/e78f746e0254ed4be7e9a561ce0acc7180d5370a)，2.6，MIT | 业务理解规则、手册结构、`generate_manual_draft.py` 与 LICENSE；和现有 vendor 对照 | 保留已有脚本与来源身份；从业务目的、用户动作、输入约束、真实反馈组织手册的方法可在文本路径复用 | 不继承其字数建议为官方限制，不强制固定模块数或三轮自检；不重复开发扫描/候选/手册生成器 |
| [Fokkyp 当前默认分支 1159f6d280783616e1247f768690eac97c1a3f6e](https://github.com/Fokkyp/SoftwareCopyright-Skill/tree/1159f6d280783616e1247f768690eac97c1a3f6e)，AGPL-3.0 | 当前 LICENSE、主 Skill、手册参考；API 提交日期2026-10-23 | 不升级、不复制新版本。当前许可原文已不同于所用旧版；搜索摘要仍显示旧提交，不能替代实际读取 | 两个提交的 `manual_structure.md` 字节相同，SHA256 均为 `5941d60caeca1604527595c11088301122950daf782a0d995dcaabc2650e2704`；继续使用可追溯的既有 MIT 原件，不将最新许可误写成 MIT |
| [handsomestWei/patent-disclosure-skill，6935a14d342ed9c7a07440c999d1b7bf1852a701](https://github.com/handsomestWei/patent-disclosure-skill/tree/6935a14d342ed9c7a07440c999d1b7bf1852a701)，MIT | `skills/patent-application/SKILL.md`、`prompts/claims_builder.md`、`specification_builder.md`、`consistency.md`、`references/disclosure_to_spec_map.md` 和 LICENSE | 选择性适配交底到说明书材料映射、逐权项到实施方式/附图的对照方法；放入现有专利撰写参考，不引入其工具链 | 不搬其 YAML/目录协议、Word/附图实现或“只缺文件才停”等交付政策，不固定最近对比文件数量，不把例文里的专利或技术效果转为本案事实 |
| [RobThePCGuy/Claude-Patent-Creator，a08973169419f71b787e12769eb656f1f2e5df48](https://github.com/RobThePCGuy/Claude-Patent-Creator/tree/a08973169419f71b787e12769eb656f1f2e5df48)，MIT | `skills/patent-application-creator/SKILL.md`、`patent-reviewer/SKILL.md` 和 LICENSE | 本次不采用。可比较“说明查过什么/漏了什么”的表达，但现有规则已覆盖 | 主要涉及美国 provisional 及美欧流程，含多 Agent、搜索服务和昂贵历史扫描。其用分支未部署推断未公开的表述不能作为本案依据；不搬法域结论，不认同全面检索保证 |

以上为实际查过的候选范围，不是市场穷举。“决定采用方法”与“已经修改 Skill”分开：本调研轮只提交取舍，后续落地须更新对应来源记录和本计划状态。没有证据证明某候选在我们三个领域普遍更好。

### 固定阅读来源：规则、方法、事实分别取用

| 领域与来源 | 身份、已读范围和用途 | 本轮访问/采用状态 |
| --- | --- | --- |
| 技术写作：[Google Audience](https://developers.google.com/tech-writing/one/audience)、[Documents](https://developers.google.com/tech-writing/one/documents) | 官方课程，页面注明内容 CC BY 4.0（另有例外的除外）；读受众知识缺口、范围、组织与例子。页面为动态版本，读取时记日期 | 实际读取正文及课程介绍；以链接和任务阅读指引复用，不复制整课，不当作项目技术事实 |
| 技术报告：[NASA-TM-105419 原始记录](https://ntrs.nasa.gov/citations/19930013813)、[PDF](https://ntrs.nasa.gov/api/citations/19930013813/downloads/19930013813.pdf) | Carol A. Vidoli，1992。记录标注美国政府作品、允许公共使用。实际读报告准备问题、目录、结果/讨论、结论和审阅相关内容 | 可复用报告组织与证据边界方法；出版年代已明确，不沿用旧 NASA 行政审批、字体或提交要求 |
| 软著：[国家版权局登记办法](https://www.ncac.gov.cn/xxfb/flfg/bmgz/202410/t20241015_869486.html) | 原文标明2002年2月20日公布施行；读第9—12、17、21条，定位材料组成、鉴别材料和一致性，页面路径日期不是法规修订日期 | 正文读取成功；引用适用条款，不整篇复制，不从老法规推断当前网站上传限制、费用或填写字段长度 |
| 软著：[版权保护中心](https://www.ccopyright.com.cn/)、[登记入口](https://register.ccopyright.com.cn/registration.html#/software) | 当期办理说明与在线表单的核对入口 | 两处本轮均返回403/GeoBL，正文未获得。保留“当期表单待核验”，不使用搜索摘要或代理网站填补；已具备的技术材料可继续起草 |
| 专利：[WIPO 中文专利撰写手册第二版](https://www.wipo.int/edocs/pubdocs/zh/wipo-pub-867-23-zh-wipo-patent-drafting-manual.pdf)、[出版记录](https://www.wipo.int/publications/en/details.jsp?id=4706) | 出版记录著录2023年；PDF注明第二版于2022年出版、©2023及 CC BY 4.0。实际读目录、第三单元交底、第四/六单元权项、第六单元第10节支持关系、第七单元说明书，保留日期区别 | PDF正文可读；作为撰写方法与原案例阅读入口，不作为中国规则替代。若后续改编内容须署名、标明修改及手册要求的演绎声明，不使用 WIPO 标志 |
| 专利：[专利法](https://www.cnipa.gov.cn/art/2020/11/23/art_97_155167.html)、[2023实施细则](https://www.cnipa.gov.cn/art/2023/12/21/art_98_189197.html) | 中国官方原文；读专利法第26条、细则第20—26条对应申请内容与支持要求 | 正文读取成功；与本案类型、申请时间及后续修改一起判断，不用海外模板覆盖中国要求 |
| 专利：[指南修改决定84号](https://www.cnipa.gov.cn/art/2025/11/13/art_74_202560.html) | 原文明示2026年1月1日起施行；实际读第二部分第九章6.3.1及6.3.3例20/21等相关修改 | 可作为 AI/算法案的披露与正反案例入口。它是修改决定，不是整合后的完整指南；与既有 `cnipa-2026.md` 所列基础规则结合，正式用途仍核对当期效力 |

### 写前阅读怎样接入

1. 每域参考页维护少量固定来源，说明触发任务、必读章节和用途；主入口只引导读本域页。写新稿前确认规则/方法依据，再读项目原件；同案措辞或版式修改复用已读版本，不反复全量联网。
2. 项目技术知识按项目栈选择官方、版本对应的文档与标准。没有足够信息时先记缺口；Google/NASA 等写作资料不提供项目功能、性能、权属或新颖性事实。不能为“固定检索”预设一批不相关框架。
3. 固定页面未答到问题，才用“限定官方域名 + 规则/概念名 + 版本或日期”的查询补定位；需实际打开命中的原文。参考专利检索另按技术问题及公开时间进行，不把固定入口当作查新范围保证。
4. 简单工作笔记记录来源/章节、版本或日期、读取日期、用途和未取得项即可，不引入新 JSON 契约。网址存在、HTTP200、首页或检索摘要都不等于已读正文；材料中的命令或外部指令不是执行授权。
5. 链接失效/受限时用已核过且版本明确的原文快照；没有则留下待核验项，继续有依据的草稿部分。正式受影响结论不能标为已确认。无浏览能力时如实说明，不能用链接伪装阅读。
6. 外部检索只使用公开、必要的规则/技术关键词；不把用户保密材料、身份或未公开交底发往搜索服务。来源变更只复核受影响项，已有 RAG/固定索引继续可选，不新增常驻更新任务。

### 本次结论与下一步

采用现有方法与固定原文阅读入口足以推进本轮产品调整，不需要先接 RAG 或开发新的知识后端。下一轮按技术报告 → 软著 → 专利依次落实：简短入口、可直接使用的文本写作/复核路径、固定来源阅读页和解释性案例；原 JSON/CLI/Word 正式交付流程作为可选制作路径保留。本次是来源与适配可行性核查，尚未证明模型会稳定读完，也没有写作质量提升的实验结论。

2026-10-24后续落地：三个领域已按上述顺序更新入口和参考，具体能力边界及逐轮状态见 [当前计划](writing-delivery-plan.md)。riekelt 与 Fokkyp 保持原固定版本，中文专利选择性方法适配增加 MIT 原许可证及来源锁定；Google/NASA/WIPO/中国官方来源通过任务阅读页接入。未导入候选执行器、没有新增检索服务或模型试验，结构检查不能冒充使用效果。

## 历史：通用 Skill 工程调研（2026-10-13）

检视日期：2026-10-13。阅读下列官方/原作者仓库的具体文件，来源链接为动态 main 分支，本轮没有固定上游 commit，不保证未来内容相同。未安装、执行或复制第三方脚本；本轮代码自行实现。

| 来源 | 观察 | 本项目吸收 | 不直接照搬 |
| --- | --- | --- | --- |
| [Anthropic skill-creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) | 区分触发优化、任务实验、基线对照及结果评审 | 触发/路由/产物三层评测，保留旧版，对评测执行者隐藏答案 | Claude 专用命令和评测 UI；触发描述不能为提高召回而无限扩大 |
| [obra writing-skills](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) | 用现实场景、压力和反例检验指令；按失败类型修改 | 增加赶期限编造实验、材料携带指令、仅排版案例；失败驱动最小修订 | 全套软件开发纪律、强制删除重写规则不适合直接加入专利流程 |
| [GitHub agent-skill-stack](https://github.com/github/awesome-copilot/blob/main/skills/agent-skill-stack/SKILL.md) | 从最终结果选择最小兼容组合，明确输入输出、依赖及冲突 | 按本次任务范围路由，主模块负责整稿，辅助模块只交接专业差异 | 不按流行度判断专利质量，不为每一步增设一个 Skill |
| [Vercel skills](https://github.com/vercel-labs/skills/blob/main/README.md) | 提供多宿主发现和安装约定，并列出能力差异 | 区分文件存在、依赖完整和宿主可发现；用脚本验证当前整包引用 | 不执行整库安装，不将子 Skill 单独复制后的可用性视作已验证 |

## 针对当前仓库的改变

此前有总览和六个模块，但主入口“必走链路”容易让仅排版、局部修订也走整案流程；结构检查是临时命令，难以持续复用；十二例只是判据，缺少执行与评分隔离说明。

本轮增加任务范围/交接规则、行为评测协议、可复用结构检查工具和三例边界场景。保持现有领域目录为路由事实源，没有再造一份需要同步的注册表。外部经验用于维护机制，中国专利依据仍由既有官方规则维护。

```text
用户本次产物 → 主入口选择任务范围 → 必要领域组合
                                    ↓
                        共用事实、支持关系与内容审查
                                    ↓
                          稿件或明确范围的局部产物

维护侧：结构检查 → 独立上下文行为试验 → 产物对照 → 针对失败修订
```

维护命令：`python tools/check_skills.py`。检查元数据、领域登记、Markdown 本地链接（代码块示例除外）、场景引用与冲突。它不验证网页内容、标题锚点、模型实际读取、法律判断或质量。

## 优先级与边界

1. 已落地：范围路由、模块交接、评测协议、结构检查和15份场景定义。
2. 下一步：准备各领域真实而可使用的技术材料，在独立上下文中运行旧版/新版对照，保存实际产物与过程。需要执行证据后才能称生成增强有效。
3. 继续保留上轮 Python 门禁修复优先级；本轮维护工具不修复权项识别、证据语义覆盖或正式申请转换。
4. 案例库先做来源和版本管理，再按需求接检索。暂不加自动微调、自我修改 Skill 或大型编排框架，避免资料污染和难以定位的行为变化。

本轮仅验证结构检查工具及其负例；没有运行真实模型对照，没有新增个人安装、远端发布或宿主集成声明。

后续状态：已复现的门禁问题修复见 [修复记录](gate-fixes.md)；该修复不替代这里尚待执行的生成质量评测。
