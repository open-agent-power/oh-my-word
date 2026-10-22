# 第一批可靠性修复

本批修复来自公开实验中已经观察到的结构、评审和排版问题。保留原实验、旧评分器及原始失败；新增 v3 评审协议和新产物目录，不追溯改分。不改变 G 的“不设为默认”结论，不宣称本批提高了事实推理准确率。

## 渲染与交付前置合同

`models.validate_renderable_draft` 在读取模板或写 DOCX 前检查标题、章节、blocks、块类型、正文、矩形表格及有限正数列宽。错误携带具体字段路径，不填空章节或补写内容。renderer-neutral 草稿不强制业务元数据，正式 `build` 仍需 v1 的 mode/schema；build 在创建交付目录前完成结构预检。

`validate_draft_v1` 同步检查这些渲染必需字段，业务来源/证据/审阅规则仍由原管线执行。合法 JSON 不代表合法稿件；本合同也不证明语义支持。

## 显式行内代码

普通段落、源码块和表格继续按原文输出。需要行内代码时，仅对 paragraph 显式声明：

```json
{"id":"b1","type":"paragraph","text":"调用 `request.body()` 返回字节。","inline_format":"markdown"}
```

当前只支持 CommonMark 的文本、行内代码和软换行，代码跨度的空白按 CommonMark 规则处理。加粗、链接、图片、HTML 等其它 Markdown 标记在此 opt-in 模式下明确拒绝；不会静默丢掉结构。源码块不能添加该模式。证据文本提取、DOCX 检查、PDF 检查与渲染共享同一可见文本定义，避免去掉反引号后被错误判作丢文。

这不是完整 Markdown 到 Word 的转换器；表格单元格本轮不解释行内 Markdown。

## 表格分页

保留重复表头，为表格行设置 `w:cantSplit`，移除表后没有内容的占位段落。真实 LibreOffice 对照中，Gin 和 Express 原先跨页拆开的行现在完整保留。

整行移动可能增加上一页留白；超过整页高度的单行仍可能被 Office 拆开，需要专门布局或人工处理。自然短尾页仍存在，未通过删文或缩字减少页数。本轮未验证所有 Office/WPS 客户端。

## 评审 v3

新增 `evals/public_control/judge_v3.py`，旧 judge/score/formal runner 不改。新版明确提供共同生成合同，合法 JSON 外壳不作为文风/可用性缺陷；描述性报告不被要求额外设计方案，提案不当作已实现。

程序独立校验候选完整且唯一、六维整数分数、低于4分的对应 issue、非空依据/理由、合法严重度、精确原文引文、严重问题引文、完整排序和 uncertainties。引文可匹配 JSON 解码后的字符串，避免 JSON 转义导致的误报。非空 source_basis 并不意味着它在语义上真实。

执行成功、结构有效、评审合同有效分别记录。只有完成执行且通过合同的 o0 主方向进入条件统计；o1 反向另报，不能补主方向。冻结文件/identity map/prompt/response 均校验哈希；缓存和汇总重新校验原响应，不信自报“通过”。不合格记录保留并拒收。

两次真实 gpt-6-luna 校准都识别了编造实测/专家审阅，且未将明确提案当虚构事实。但主方向仍有一项低分缺依据，被拒收；反向通过也未替代主方向。因此本轮没有新的有效主方向比较分，v3 只作辅助，不能称为可靠自动专家。

## 验证与产物

全量 `tests + evals/public_runner + evals/public_control`：438 passed、185 subtests passed。3份新DOCX/PDF共12页已实际看图；正文原字符串及表格单元格顺序/内容保持，自动DOCX检查无问题。每份PDF仍有一条段落续页提取警告，保留并对照页图说明。

完整结果及原始记录位于仓库外：

`D:/XiangMuLuoDi/Development/word-skills-reliability-batch1`

包括 `RESULT.md`、`regression.xml`、`layout-trial`、`calibration-audit.json`、`judge-calibration-v3`、`output-contract-controls.json` 和 `historical-integrity.json`。上一轮19项交付文件及30项已登记评测源码哈希复核未变。

重跑测试：

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests evals/public_runner evals/public_control -q
```

重做排版 trial 时必须选择新的输出目录：

```powershell
.\.venv\Scripts\python.exe -B evals/public_control/trial_layout.py --source-root 'D:\XiangMuLuoDi\Development\word-skills-public-eval' --out '<新的绝对输出目录>' --soffice '<本机soffice.exe绝对路径>'
```

新评审使用 `judge_v3.py prepare --runs ... --tasks ... --data-root ... --gold ... --out <新目录> --reverse`，再执行 `run --out <同目录> --jobs 1..3`。prepare 不调用模型；run 使用现有 CLI 授权与配额。示例校准输入与冻结记录保留在本批目录，不能把已知控制例的判断率当实际业务泛化成绩。
