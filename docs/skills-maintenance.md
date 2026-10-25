# 维护模块、利用改稿、运行评测

日常起草仍使用 [主 Skill](../skills/oh-my-patent/SKILL.md) 与 patent.py。以下工具供维护者改进体系，不要求每个使用者建立数据库。真实案卷放在仓库外的私有目录；本工具不爬资料、不上传语料、不训练模型。

你提供一套“交底 → 初稿 → 专家改稿/批注 → 定稿”，维护者先登记当时可见的输入与隐藏答案，再用工具提取差异；专家确认为什么改。反复出现的问题才进入通用模板或现有领域模块，随后用未参与修改的案件复核。这就是本轮的“接数据集”，不需要你先搭知识库，也不是把定稿全文塞给每次生成。

资料需求清单则处理单案缺口，例如缺标准版本、指标定义或对比文件原文：先列明确问题，让人或检索 Agent 找资料，再核对是否适用。案卷经验与外部资料分别使用，均不能替代本案真实事实。

## 模块管理

`python tools/patent_lab.py modules` 读取 [登记表](../skills/oh-my-patent/domains/registry.yaml)。每个模块登记 owner、version、scope、exclusions、reviewed_on、status 和 quality_evidence；frontmatter 与登记版本必须一致。

experimental 表示初版指导；validated 需要质量对照证据及专业复核；deprecated 保留迁移说明。程序只检查证据文件存在，不认证结论。结构检查、几例路由或授权结果均不是完整质量对照。细分行业先用参考资料，确有稳定独特判断和回归案例时才拆模块。

## 登记真实案卷

保留交底、初稿、改稿、批注、定稿和审查过程原件。input 是本次任务当时可见材料，reference 是允许参考的资料，answer 是隐藏的专家答案。原始申请在答复任务中可以是 input；角色按任务登记，不能按文件名猜。

```powershell
python tools/patent_lab.py case-init D:/private-corpus/case-a --id case-a --family family-a --project project-a --input disclosure.docx --answer expert-final.docx
python tools/patent_lab.py case-check D:/private-corpus/case-a/case.json D:/private-corpus/case-b/case.json
python tools/patent_lab.py revision D:/private-corpus/case-a/edited.docx -o D:/private-corpus/case-a/edits.json
python tools/patent_lab.py revision D:/private-corpus/case-a/draft.docx D:/private-corpus/case-a/expert-final.docx -o D:/private-corpus/case-a/diff.json
```

case-init 新建 case.json，计算哈希，不修改原件。将 kind/version 的 unclassified/unconfirmed 换成实际文书种类与版本；未确认仍保留未知。清单包含 family_id、project_id、split（development/test）和 use_permission。默认 local_only；资料所有者允许后才能改 approved_external，公开合成样例用 public；外部模型执行拒绝 local_only。

case-check 拒绝同族/同项目跨组及涉及 input/answer 的完全相同跨组内容，包括把另一组答案改标 reference。它不能识别改写、近重复、未登记同族或历史答案泄漏，需人工清理。DOCX revision 区分常见行内插入/删除/移动的前后文本，保留批注与 XML 段落位置；段落号不是页码。复杂嵌套修订、段落/表格结构、字段、公式、图片和版面须核对原件；PDF/OCR 未实现。

modification_reasons 默认为空，请由专家标注必要特征、支持不足、范围调整、事实补充、文风等原因。申请前补充与申请后限缩分别分析；程序不从差异猜法律理由。

## 按问题收集资料

Agent 发现缺口后生成 knowledge-needs.json，交给人或可用检索工具，说明问题、查询、资料角色、版本/日期范围和原文定位。未找到记 unavailable，不改成“没有相关技术”。

```json
{"schema_version":1,"needs":[{"id":"N1","question":"本案耐磨指标采用哪种测试方法和条件？","query":"材料名称 耐磨 测试标准","role":"standard","version_or_date_scope":"确认本案采用版本；未知时请技术人员补充","delivery":"标准标识/版本、原文位置、适用条件及本案记录","status":"pending","evidence":[]}]}
```

`python tools/patent_lab.py needs-check knowledge-needs.json` 校验清单。found 必须附 evidence：source、locator、supports、limitations。校验不执行检索、不认证支持；最终按 [资料角色](../skills/oh-my-patent/references/domain-corpus.md) 和事实账本审查。

## 准备、执行、复核

```powershell
python tools/patent_lab.py eval-prepare --case generic-unknown --case mechanical-utility --case medical-design -o D:/private-eval/run-1
python tools/patent_lab.py eval-run D:/private-eval/run-1 --timeout 180
python tools/patent_lab.py eval-report D:/private-eval/run-1
```

默认生成 generic/domain 两种条件；`--mode domain` 仅作单条件流程验证，`--repeats 3` 观察波动。通用条件用 [替换段落](../evals/generic-entrypoint.md) 机械替换完整主入口的领域路由段，其他共用链路及约束保留。Skills、输入和提示词记录哈希；输出与 JSONL 过程另存。未知版本/token/评分不补0；未传 --model 使用宿主配置，resolved_model 保留 unknown，不能声称固定了模型版本。执行失败或超时即停队列，余下保持 not_run；中断记 interrupted，已有记录保留，重跑另建目录。

只替换路由段可以减少共用入口差异，但不能据此把 A/B 的全部结果归因于领域模块。质量对照还需固定解释器、依赖、模型、工具、材料和预算，重复运行，并由独立评分者核对原文与过程记录；未满足时结论保持探索性，`quality_gain` 仍为 unknown。

Windows 评测进程默认继承已启用的系统代理；显式 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 优先（包括显式空值），NO_PROXY 保留。代理只传给子进程，系统与用户环境保持原值。如果出现模型缓存缺字段，核对 PATH 中 `codex --version` 与缓存 client_version，更新 CLI 到兼容版本；桌面应用与独立 CLI 可能共用缓存。确认连接后另建运行目录，已有失败记录保留。

模型能回复后，还要确认过程中的文件读取成功。若命令返回 `helper_unknown_error: setup refresh had errors`，查看 `.codex/.sandbox` 最新日志，核对运行时文件占用和权限；按 [官方 Windows 沙箱排障](https://learn.chatgpt.com/docs/windows/windows-sandbox) 处理。进程 succeeded 与材料读取/任务完成分开，缺口回复保留未完成状态；原始日志留在私有运行目录。

已有15例是缺完整材料的合成路由/事实边界短例。执行器只读，最终回复保存 response.md，适合文本/路由/缺口比较；二进制交付、官方转换与实际申请另验证。这里显式加载入口，不测宿主自动发现。任务包分离和提示词不是 OS 文件隔离；高保密评测须用具备文件/网络边界的宿主。其他宿主可读取 task.json，本轮内建执行器只适配 Codex CLI。

真实案卷的 cases YAML 放在私有目录，用 manifest 字段指向相对 case.json，request 写任务，expected 为 required/avoid/behavior。执行器只复制 input/reference；answer 与 expected 留在 suite.json 评分侧。完整任务包同时检查本任务隐藏答案及跨组 input/answer 的哈希，防止它们经共享参考文件混入。角色随任务确定，同组另一任务合法输入不一概禁用。已见测试样本转开发；不同版本各自冻结完整包，固定模型、工具和预算。检索增益另设资料条件，本工具没有实时RAG服务。

grade.json 初始全部 unknown。评分者填写 reviewer、status（pass/fail/unknown/not_applicable）、reason 和 evidence（file、quote）；非未知判据需引用真实运行文件的原文。routing 的 pass/fail 只接受 trace.jsonl 成功命令事件，复核者须确认命令确实读了文件，不能拿模型自报代替。哈希变化使评分失效；定位校验不等于自动语义评分。

task_outcome 与 execution_state 分开；进程结束不代表案卷完成。task_outcome/severe_failure 非 unknown 时，在 outcome_evidence 对应项填 reason 和 evidence（格式同判据），不能只填评分者姓名。editing_minutes 只填实际耗时，同时记录 editing_record 的 started_at、ended_at（带时区的 ISO 时间）与 activity；多段修改分开评测或使用明确的连续计时段，不能补猜测值。汇总保留未知和失败，不自动宣称 quality_gain；完整质量需专业人员复核必要特征、支持、公开充分、合理范围与修改成本。

## 工作区与验收记录

开发与发布目录的身份、用途和核对命令见 [工作区管理](workspace-management.md)。当前工作副本中未提交的修改必须在发布前逐项审阅，不能把远端提交身份当成本地修改的身份。

本地代码快照位于 `.agent/current-code-manifest.json`，不纳入公开发布。改完所列文件后运行 `python tools/check_code_manifest.py --refresh`，新增文件用 `--include <相对路径>`；交接前再运行无参数校验。完整依赖验收运行 `python tools/check_full_dependencies.py`，其 JSON 报告记录解释器、依赖版本、测试数与 skip 数，任何 skip 均使验收失败。报告保存在 `outputs/acceptance/`，不与发布检出混用。

## 跨 skill 依赖声明

六个业务 skill 共用 `word-document` 的排版能力和 `word_skills` 的转换实现。依赖原先只藏在正文链接里，
改共享文档时不知道影响谁。2026-10-25 起在 `SKILL.md` frontmatter 里显式声明：

```yaml
---
name: oh-my-patent
depends_on: [word-document]     # 硬依赖：必须存在、不能成环
see_also: [oh-my-technology]    # 软引用：允许互相引用，不参与成环判断
---
```

检查命令：

```bash
python tools/check_skill_deps.py              # 存在性、成环、未声明链接
python tools/check_skill_deps.py --reverse    # 反向影响面：改某 skill 会影响谁
python tools/check_skill_deps.py --strict     # 未声明链接也算失败
```

规则：**硬依赖必须无环**；互相引用（例如 `word-document` 引用 `oh-my-technology` 的审阅流程，
同时被它依赖）写 `see_also`。正文链接到别的 skill 却没在两者之一声明，会给警告——
这通常意味着依赖关系只在某段文字里“事实上存在”，改共享文档时容易漏。

## 行尾必须是 LF（Windows 编辑注意）

`.gitattributes` 声明 `* text=auto eol=lf`，但 Windows 上 `Path.write_text()` 会按 `os.linesep`
把 `\n` 写成 CRLF。评测夹具（`evals/public_runner`）一边按文本读 Skill、一边按字节算哈希，
CRLF 会让 frozen Skill 哈希对不上，表现为「只加了一行 frontmatter 却整组评测失败」。

写文件用 `Path.write_bytes(text.encode("utf-8"))`，或 `open(..., newline="\n")`。
检查：`python tools/check_line_endings.py`（只查 `skills/`、`registry/`、`shared/`、
`word_skills/schemas/`，已进 `check.py --all`）。
