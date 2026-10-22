# 软著与专利固定知识库

提供 `word-skills kb build/verify/search/context`。首版公开资料固定为9份443片段的规则/参考索引，项目源码另建3份21片段的project索引，来源URL、版本、日期、行位置及哈希均保留。无配置的旧快照在本地检索；可选的RAGFlow通过本机HTTP服务检索。公开采集脚本单独运行。

## 复用现成检索

本轮收敛为现有Fokkyp业务阶段、Word输出和RAGFlow检索适配，不继续扩展通用检索算法、通用排版或自动专业裁判。导入工具和命令见 [RAGFlow接入说明](../tools/ragflow/README.md)，公开业务验收见 [可重复运行的演练](../evals/reuse/README.md)。

在新目录导入既有固定资料包，配置本机RAGFlow的中文embedding模型和环境变量API key。导入成功后生成的 `ragflow.json` 绑定远端资料及片段ID。将这个新目录传给现有 `--knowledge` 即可；没有另外的业务编排平台。RAGFlow负责排序，返回的片段ID、文档和原文须与固定包一致；不一致或服务不可用时失败，不静默降级为旧BM25。检索上下文保留检索器配置及命中记录，候选仍待阅读。

`kb verify`只检查本地固定包；真实服务可用性需实际执行 `kb search`。API key仅从环境读取，不写入资料包；LLM、embedding、rerank服务也须选择本地或获准端点，不能只凭知识库本地部署就声称没有对外传输。

软著 `prepare --knowledge INDEX` 和专利 `template --knowledge INDEX` 实际检索规则上下文并绑定；后续制作验证变动。检索结果不自动成为verified，未改原有权属、事实支持或最终审阅门禁。详细[使用流程](../skills/word-document/references/knowledge.md)。本机已在被gitignore的knowledge.local.json固定索引身份；新机器须取得合法资料包自行构建或配置索引，公共仓库不包含本地资料或私密案件。

实际演练产物为源码5页、手册2页、专利4页，最终11页全部看图。修复真实演练发现的“小数参数被当作附图标记”误报，严格构建已通过，未定稿/提交。检索小样仍有2个指定上位法来源未进入top5，长篇指南挤占问题保留；没有生成质量提高的受控实验证据。

本机[完整结果及来源](D:/XiangMuLuoDi/Development/word-skills-ip-kb/RESULT.md)与原始上下文/日志/负结果均在仓库外。该路径只供当前工作区复查，发布时应另行提供合法可移植的证据存储。
