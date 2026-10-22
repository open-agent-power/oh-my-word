# Word Skills 公开材料实验

本目录包含 2026-10-20/21 实验的可维护执行器。数据、评分答案、运行日志和文档产物在仓库外：

`D:/XiangMuLuoDi/Development/word-skills-public-eval`

以该目录的 `RESULT.md`、`control/experiment.yaml`、各 run 的 freeze/summary 和原始记录为准。
这轮只评估明确注入上下文后的生成、宿主检索、程序门禁和原生渲染。
子进程自主读文件受运行环境限制；没有验证 Agent 自动发现 Skills、自主按需加载或完整生产交付流程。

## 目录职责

| 目录 | 内容 |
| --- | --- |
| `public_data` | 来源快照和任务构建、中文 QA 独立评分实现、24 页简单保真夹具 |
| `public_runner` | 输入冻结、提示词角色/哈希检查、独立 CLI 调用、失败记录、可选结构化输出候选 |
| `public_control` | 开发侧检索/指令条件、机械评分、原样文档渲染、独立匿名 AI 评审、配对统计和资源清点 |

生成阶段不读取 `scoring-data`。评分脚本会读答案，不能当生成器运行。
这只是工作流分离，不是操作系统安全隔离。公开题目可能进入模型预训练。

## 条件和样本

A：共同事实边界和合同；B：再注入冻结完整 Skills。C：B 加宿主 BM25 选材。
S：B 加跨项目中文风格参考；M：精简规则；D：宿主按任务选取现有规则；X：固定 MIT 上游技术写作规则的上下文适配。
M/D 与 B 规则集合不完全等价，不能把结果归因于纯长度。X 不是上游原生工作流性能。
G 保留 B 的逐字提示词，只在 CLI 增加 `--output-schema`，不保证事实正确。

正式生成 306 次：开发 AB96、C18、写作消融48、留出 AB96、G48；另有小样12、结构探针2、模型连通探针、AI 评审、失败重试和失效批次。
每任务每条件3次重复；独立样本量按论文/上下文/项目，不能把重复当新项目。
小样只验证执行链。`formal-v1-dev-ab-v4` 为协议失效批次，保留成本但禁止评分或复用。

## 检查和重新评分（不调用模型）

在本仓库根目录 PowerShell 中执行，使用项目的 Python 3.12 环境：

```powershell
$evalRoot = 'D:\XiangMuLuoDi\Development\word-skills-public-eval'
.\.venv\Scripts\python.exe -B -m unittest discover -s evals/public_runner -p 'test_*.py'
.\.venv\Scripts\python.exe -B -m pytest evals/public_control -q
.\.venv\Scripts\python.exe -B evals/public_runner/structured_candidate.py self-test
.\.venv\Scripts\python.exe -B evals/public_control/score.py --run "$evalRoot\runs\formal-v1-heldout-ab-v1" --gold "$evalRoot\scoring-data\formal-v1\heldout-gold.jsonl" --out "$evalRoot\control\recomputed-heldout-ab"
.\.venv\Scripts\python.exe -B evals/public_control/score.py --run "$evalRoot\runs\formal-v1-heldout-g-v1" --gold "$evalRoot\scoring-data\formal-v1\heldout-gold.jsonl" --out "$evalRoot\control\recomputed-heldout-g"
.\.venv\Scripts\python.exe -B evals/public_control/resource_audit.py --root $evalRoot --out "$evalRoot\control\resource-recomputed.json"
```

`score.py` 将 JSON 可解析和共同合同合格分开；formal runner 摘要的 `valid_json` 实际是两项同时合格，不能当纯 JSON 解析率。
原始首个有效观测响应固定计分，不因质量失败重抽。
CMRC 的 EM/LCS-F1 按公开协议独立实现，仅用于这些短中文题；日期更精确或同义解释也可能被 EM 扣分，不等于语义错误率。

## 新跑批和审阅

模型调用需要现有 CLI 授权及配额。`public_runner/README.md` 和 `FORMAL_RUNNER.md` 说明 prepare/freeze/run 协议。
必须先冻结新的输出目录、模型请求、任务、来源和代码，再调用 `run --jobs 1..3 --max-attempts 1`。
同一批次的 QA/写作响应不能为了过合同重试；配额等执行失败恢复单独留痕。
G 额外执行 `structured_candidate.py freeze --run <新目录>`，之后使用同脚本 run，禁止静默换模型。
本轮请求型号始终 `gpt-6-luna`；精确 resolved version 不可得，不能填成已知。

`render_outputs.py` 只添加结构 ID，使用项目 Word 后端；不修补原文或无效 JSON。
DOCX/PDF/PNG 是 formatter 试验产物，不自动变成 production reviewed/finalized。
必须实际看完被声明已检查的所有页，记录可见问题并核对提取警告。
本轮代表性渲染只取写作 repeat1，其余重复不声称做过视觉检查。

匿名评审使用新 CLI 上下文、原文和候选，不挂载 Skill 条件名称。开发评审保留原始结果；
报告类 reasoning 维度受到不适用设计建议要求影响，不作为改进证据。
`judge_heldout_v2.py` 和独立 rubric 修正了这一测量问题，冻结后才评留出输出。
AI 评分不是专家意见；全部严重失败和至少20%配对样本另作协调者核查。

## 复现边界

执行器硬编码了本机 CLI 路径，文档渲染需要可用 LibreOffice/Poppler，迁移机器时应显式配置并重新冻结，不改旧 run 的代码哈希。
保真夹具只有24页稀疏合成材料，不是 OmniDocBench 或真实复杂扫描件成绩。
没有 OCR、复杂数学语义、密集多栏的本轮有效验证。没有领域专家或真人返工计时。
资源按原始 usage 记录已知小计和未知尝试；cached input 不再加到 input；不推算美元费用。
数据来源许可分别记录，代码许可不推定为数据许可，不提交保密材料或无再分发许可下载。
