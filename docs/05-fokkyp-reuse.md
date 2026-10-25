# Fokkyp 软著流程直接复用

2026-10-24补充：软著入口增加无需本项目后端的文本起草/审阅路径，选择性适配本固定版本的业务理解与操作手册方法；新参考见 [领域写法](../skills/oh-my-copyright/references/drafting.md) 和 [写前来源](../skills/oh-my-copyright/references/domain-sources.md)。原有工具流程、vendor 字节、哈希与正式审阅要求不变。对上游当前提交 `1159f6d280783616e1247f768690eac97c1a3f6e` 实读 LICENSE 为 AGPL-3.0，本项目不升级、不引入该版本；既有 MIT 提交继续明确固定。搜索结果仍可能显示旧版本，许可和内容须按实际提交核对。

更新：2026-10-17。当前固定 [2.6 e78f746e0254ed4be7e9a561ce0acc7180d5370a](https://github.com/Fokkyp/SoftwareCopyright-Skill/tree/e78f746e0254ed4be7e9a561ce0acc7180d5370a)，MIT。此前2.5仅改编流程；本轮根据用户要求改为实际复用阶段脚本。完整许可证保留在 third_party/licenses/fokkyp-MIT.txt 及 vendor/LICENSE。

## 直接复用

word_skills/_vendor/fokkyp 保留16份上游原件，UPSTREAM.json记录源提交、相对路径及SHA256；原件不打补丁。9个脚本为 common、analyze_project、generate_business_context、propose_code_selection、extract_code_material、generate_manual_draft、generate_application_info、confirm_stage、capture_screenshots。extract_code_material仅作为上游候选脚本的依赖，不用于最终源码分页。另保留原SKILL及五份阶段参考。不引入OfficeCLI、安装器、截图浏览器或上游生成demo。

copyright prepare直接执行上游analyze→business证据收集→candidates。copyright workflow提供business/model-context、manual、fields、confirm、screenshots等原脚本入口。copyright select --workflow-selection导入同一份候选选择，绑定本地原件哈希，避免重复选择。源码选择按完整文件投影；原接口仍支持显式原始行段摘录。

## 适配位置与原因

| 位置 | 适配 | 原因 |
|---|---|---|
| copyright_workflow.py | 隔离子进程调用；上游发现时叠加本地凭据、目录、符号链接排除 | 防止脚本模块污染及私人材料进入公开输出 |
| copyright.py | 未知扩展名调用上游内容识别；已知语言保留原哈希/编码/行数契约 | 复用新语言候选发现而不重写扫描器 |
| workflow manual --interface cli | 通过句式钩子适配终端；不替换命令标识；CLI不沿用390字页面段落下限 | CLI没有按钮和页面导航；短命令不应凑字 |
| workflow manual | 没有真实配套文档时不填“总体设计/详细设计/测试案例” | 上游缺省值不是项目事实 |
| workflow fields | 未提供的开发方式、权利基础、环境保留待确认 | 本机配置与软件开发环境不能等同 |
| workflow manual/fields --preview | 允许继续起草但不写用户确认；正常生成检查确认内容哈希 | 已有用户授权继续执行，未知事实仍不能伪造 |
| copyright_manual.py | 用markdown-it-py保留章节、表格、命令块和已声明图片 | 旧适配把手册降成纯段落，无法呈现操作结果 |
| render/delivery/evidence | 同一Word后端插图、图片审计复制与校验、软件页眉 | 不再引入第二套生成器；图文与正文一起交付 |

原始SKILL是溯源资料，不是另一个并行入口；实际指令以skills/oh-my-copyright为准。上游建议字数、V1.0习惯与软件字段枚举须结合当期官网核对，不能作为登记资格认证。已在会话中确认的项目、软件名和执行授权不重复索取；真正缺失的权属和日期不代填。

## 验证与限制

专项测试实际调用上游脚本，检查未知扩展名、WPS资料登记、凭据排除、确认过期、字段留空、图片/表格入Word及图片篡改。固定OKS实例保留模型稿、上游生成草稿、自检记录、原始运行日志来源与图文交付。可运行 `python -m pytest tests/test_copyright_workflow.py tests/test_copyright_package.py` 及 `python tools/check_word_skills.py` 复核。实际申请材料、运行日志及本机路径不纳入源码。

上游自检是启发式规则，不是独立语义审查；多条round记录不等于多次人工评审。源码候选里的估计页数仅帮助选材，最终交存页数和行数须从实际产物核对；CLI日志排成图必须标注实际输出排版，不能称为原生终端截图。GUI自动截图仍使用调用环境已有工具，本轮没有新接入浏览器自动截图器或安装依赖。

OKS软件名已获用户确认：开知智能体知识与记忆管理系统，简称OKS，版本V0.6.23。权利人、完成日期、开发方式等仍未知。运行代码与依赖链接不为规避审查而修改。

## 2026-10-25 真实项目交付复盘

一次真实项目交付验证了几个需要写回 Skill 的操作边界：未合并候选版本的代码、运行页面和截图必须绑定同一提交；上游 60 页估算不能代替 Word 实际分页；标题样式变化后目录字段可能显示“未找到目录项”，应改用可见、与章节一致的静态目录并重新核页；生成器自检为 0 不等于人工通读。完整检查项见 [真实项目交付复盘](../skills/oh-my-copyright/references/real-project-retrospective.md)。本轮只沉淀规则与门禁，不复制项目私密截图、运行数据或申请材料。

## 2026-10-22 字段保真修复

`workflow fields` 现禁用上游为达到字数下限而生成通用功能的 fallback。主要功能优先使用 answers 中的真实填写值，其次使用业务稿原文；为空时保留待确认。短文或长文照原样输出并交给检查提示，不能默默用“数据持久化、角色协作、配置管理”等无证据文字替换。预览不产生用户确认，权属与环境待确认行为不变；vendor 原件哈希保持不变。

500~1300仍是固定上游业务/确认入口的兼容校验，不因简单案例写作成本就直接移除。公开转载存在该字数范围的近期表单说明，但不是本轮取得的官方证据；官网本轮通过连接器与网页访问返回403，未以旧页面或转载冒充当期官方核查。实际使用按当次官方表单核对，材料不足就补事实或保留草稿，不编功能凑字。
