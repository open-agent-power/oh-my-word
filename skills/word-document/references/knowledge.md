# 材料使用与按需检索

先读实际来源再写结论。按本次任务选择成本合适的路径，已有索引配置本身不触发检索：

| 情况 | 使用方式 | 留存与核对 |
|---|---|---|
| 少量原件，能直接定位所需内容 | 直接阅读固定版本原件，不要求入库或启动 RAG | 在既有业务记录中标来源、版本、位置和未确认项 |
| 同案修改，输入版本及事实未变 | 复用业务理解、TECH_FACTS 或 evidence；只修改目标内容 | 核对原件是否变化，保留修改前后版本；新产物重新校验和审阅 |
| 新增事实、功能、参数或规则疑问 | 补读相关原件，必要时运行验证 | 补齐受影响记录和支持关系，不凭旧稿填事实 |
| 资料量大、跨来源定位困难，或用户明确要求检索 | 使用已有索引与检索器，回到原文核实 | 保存实际查询、命中与缺口；检索结果仍是候选 |

直接阅读也要核对规则的版本、生效日期与适用范围；涉及现行要求而固定材料不足时查官方来源，不能以节省成本为由沿用失效规则。缺少本案事实时优先指出具体缺件，检索无法替用户补出真实项目数据。沿用原业务记录，不为每次写作建立第二套事实库。

选择索引路径后，本机项目根若有 `knowledge.local.json`，读取已固定的路径与 kb_id；执行 `kb verify`，返回身份须一致。未配置时使用用户指定的本地索引，或在确有索引需求时按来源清单建立新索引。已有案件的知识绑定必须保留并验证，不得删除绑定以绕过失败；需要更新时按下述版本机制处理。

## 入口

```text
python -m word_skills kb build SOURCE_MANIFEST.json --out NEW_INDEX
python -m word_skills kb verify INDEX
python -m word_skills kb search INDEX --topic copyright --kind rule --query "源程序 文档 鉴别材料 连续 页 行"
python -m word_skills kb context INDEX --topic patent --kind reference --query "与本案技术贡献相关的实际检索词" --out NEW_CONTEXT
python -m word_skills copyright prepare PROJECT --out NEW_CASE --name NAME --version VERSION --knowledge INDEX
python -m word_skills patent template invention -o NEW_DRAFT.md --knowledge INDEX
```

`copyright prepare --knowledge` 自动保存规则检索上下文并绑定到 copyright.json；后续 lint/build/package 校验绑定，package 留存上下文审计副本。专利 template 在稿件旁保存 `.knowledge` 目录和 `.knowledge.json` 绑定；后续同路径 lint/build/review-init 会验证，build 另存输入/产物哈希回执，仍走已有 strict/final 门禁。不要只移动稿件导致绑定丢失；改名/迁移时明确携带并重建相对路径，不能把新路径当自动仍有绑定。正式 handoff 仍按既有流程，额外保留本次知识上下文供审阅。

两个业务入口的预设查询只检索 rule。技术参考及本案源码要按实际问题另用 `kb context`，不把默认规则查询说成已完成技术查新。每次换主题可执行多次 `--query`，保留每条查询的命中和缺口。`--top-k` 是数量上限；词法相似并不表示语义支持。

## 阅读与引用

读取 context.md、searches.json、source-map.json 和相关完整源文件。上下文只是召回片段，论证跨段落、图表、公式或权项依赖时打开原文扩展阅读。PDF 抽取的行位仅对应文本快照；页标记用于回到原PDF核对，不保证图、表、排版无损。

| kind | 用途 | 不可代替 |
|---|---|---|
| rule | 官方法规、审查/登记要求 | 本案事实、适用性专业判断、永久现行性 |
| reference | 公开专利、写作/现有技术参考、历史文本 | 用户原创技术、当前权利状态、全面查新 |
| project | 经登记的本案代码和技术材料 | 权属、发明人、未经实际运行的效果 |

检查来源标题、URL、版本、生效/公开日期、获取日期、提取限制及引用上下文。旧文本与修改决定分开，不自行声称已合并成现行全文。找不到来源或只找到不相干片段时，记录缺口，不为了让引用齐全而改写成不存在的事实。

候选在 evidence-candidates.json，保持 unverified，case/evidence.json 初始为空。实际阅读后才能提炼陈述并建立原业务事实账本；软著沿用业务理解/源码选择，专利沿用 TECH_FACTS 和逐特征支持，不另外维护第二套已核验事实。规则和参考不得因检索命中自动抄入本案事实。

## 固定与更新

索引包含原文快照、SHA256、行位置、分块与检索参数。没有在线隐式更新；需更新资料时建立新 pack/索引，再更新本机指针。旧 case 保留原索引身份与上下文。无 `ragflow.json` 的旧包使用本地BM25；新包可按仓库 `tools/ragflow/README.md` 导入本机RAGFlow，复用其检索能力。不要自行另写检索或重排算法。返回片段必须与固定原文一致，仍可能误召回或漏召回。

保密项目材料仅在确需索引时另建 project 索引。无配置包检索不联网，RAGFlow包通过本机HTTP检索；其embedding等模型端点也须本地或获准。`kb verify`不检查服务在线，需实际 `kb search` 验证；服务故障时报告失败，不假称已检索。公开资料采集工具单独运行，不把本案文件交给抓取服务。哈希用于检查变化，不是签名或操作系统隔离。上下文存在或结构校验通过，不证明模型读过来源或生成质量提高。
