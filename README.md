# oh-my-word / word-skills

`word-skills` 是面向中文领域写作的 Skills monorepo。技术报告、软著材料和专利初稿以写作方法、规范、案例和审阅标准为核心；项目分析、程序校验、Word/PDF 制作及 RAG 按需选用。

产品名统一为 `word-skills`，仓库名及兼容的 `oh-my-patent` 命令保留。材料、事实、文稿、交付和完成状态的含义见 [共用契约](docs/06-contracts-and-states.md)。

当前实现包括：

- `word-skills`：总入口、技能注册表和确定性路由；
- `oh-my-technology`：以技术报告、设计说明为重点的技术文档 Skill，并保留需求规格、接口说明、测试报告、用户手册和运维手册五种有契约约束的扩展模式；
- `word-document`：基本单节样式与受限 `docxtpl` 插槽模板；
- `oh-my-patent`：原有发明、实用新型、外观设计 CLI、六个领域模块和 final/handoff 门禁；
- `oh-my-proposal`：版本化指南、要求/章节/附件映射、人员材料和预算一致性检查；
- `oh-my-copyright`：源码清单、原文选段、手册/申请字段一致性及材料生成。

项目申报与软件著作权已接入 CLI 和共享交付链。附带的 NSFC Profile 只用于过期历史案例，不能当作当前开放渠道；真实申请仍须当期官方指南、申请人资料及人工核查。目标架构和能力边界见 [docs/02-architecture.md](docs/02-architecture.md)、[docs/03-roadmap.md](docs/03-roadmap.md) 和 [registry/skills.yaml](registry/skills.yaml)。

## 先使用领域 Skill

保留完整仓库及相对资源，读取对应入口即可进行文本起草与审阅，不需要先安装 Python 后端或接入 RAG。由 Agent 实际读取任务材料和有关来源，交付文本、依据及缺口；这不产生工具的定稿状态。

| 任务 | 入口 | 写前固定来源与阅读范围 |
| --- | --- | --- |
| 技术报告、设计说明 | [技术文档 Skill](skills/oh-my-technology/SKILL.md) | [Google/NASA 写法及本案官方技术资料](skills/oh-my-technology/references/domain-sources.md) |
| 软著业务说明、手册、填写辅助 | [软著 Skill](skills/oh-my-copyright/SKILL.md) | [国家版权局、版权中心及固定 Fokkyp 方法](skills/oh-my-copyright/references/domain-sources.md) |
| 专利交底、草稿及支持复核 | [专利 Skill](skills/oh-my-patent/SKILL.md) | [WIPO 中文手册、中国法/细则/指南修改](skills/oh-my-patent/references/domain-sources.md) |

写新稿前实际阅读适用章节；同案修改复用已读版本，只补查变化。固定入口不足时按 [共用阅读规则](shared/references/source-reading.md) 限定官方来源进一步定位。网页受限或无浏览能力时保留未读项，不能把链接存在当作已核验。规则、范例和项目事实分开；固定阅读不是查新或生成质量保证。

## 可选工具安装

选择本项目程序校验或文件制作时需要 Python 3.10+。基础安装包含专利和技术文档的结构检查、Word 生成与来源校验；读取 DOCX/PDF 材料和插槽模板使用可选依赖。

```powershell
python -m pip install -e ".[dev,ingest,templates]"
python -m word_skills skills list --json
python tools/check_word_skills.py
```

安装包不包含真实案卷、`outputs/`、本机证据、LibreOffice、Poppler 或字体。完整 monorepo 是受支持的 Skill 安装形态，不能只复制一个 `SKILL.md` 就声称共享资源已安装。

制作前可运行 `python tools/check_delivery_environment.py --soffice SOFFICE_EXE --pdftoppm PDFTOPPM_EXE`，只读核对Python依赖、转换工具版本与本机客户端/字体是否存在。缺失返回退出码2，不自动下载或安装；显式路径无效时不换另一个工具。检测到Word/WPS不代表已完成兼容测试，仍须实际打开或渲染目标文档核对。

`requirements-tested.txt` 记录验收使用的直接依赖版本，可在新环境用 `python -m pip install -r requirements-tested.txt` 安装后，再执行 `python -m pip install -e . --no-deps`。它不是传递依赖锁文件。独立 wheel 包含 Python 工具、Schema、注册表快照及所需上游脚本；完整 Skill 文案仍需本仓库。字体及 PDF 预览工具由使用环境显式配置。

### 安装后独立验收

完整 Agent Skill 使用本仓库，wheel 仅提供 Python 工具和所需运行资源。先在仓库内构建 wheel，再将它装入仓库外的新虚拟环境，避免误用开发目录中的代码：

```powershell
python -m pip install build
python -m build --wheel
# 使用仓库外尚不存在的目录，示例以 Windows PowerShell 为例。
$checkRoot = Join-Path $env:TEMP ('word-skills-check-' + [guid]::NewGuid())
python -m venv "$checkRoot/venv"
$checkPython = "$checkRoot/venv/Scripts/python.exe"
Get-ChildItem dist/word_skills-*.whl | ForEach-Object { & $checkPython -m pip install $_.FullName }
& $checkPython -I tools/check_installed_delivery.py --out "$checkRoot/smoke"
# 有转换工具时另用新目录要求真实 PDF/页图，不接受跳过预览。
& $checkPython -I tools/check_installed_delivery.py --out "$checkRoot/preview" --preview --soffice SOFFICE_EXE --pdftoppm PDFTOPPM_EXE
```

Linux/macOS的环境解释器位于 `venv/bin/python`；其他参数相同。验收覆盖仓库外导入、两个安装命令、路由、专利骨架、来源摄入、技术文档制作和软著prepare。输入明确标记为合成材料；不调用模型或知识服务，不填写审阅通过记录，未审阅定稿必须失败。结果保存在输出目录的 `installed-delivery.json`，原始命令和实际退出码可回查。

GitHub Actions配置执行Linux/Python 3.10、3.12与Windows/Python 3.12的结构检查、完整确定性回归、依赖检查及隔离wheel验收；另一个Linux任务实际生成PDF/页图。CI使用公开合成材料，不上传本机案件。配置存在、某次CI通过、人工看图和写作质量分别验收，CI不自动把交付升级为reviewed。字体替代与Word/WPS兼容仍须目标环境实测。

## 总入口与路由

```powershell
python -m word_skills route "请写一份技术报告" --json
python -m word_skills route "只调整 Word 页眉和页码" --json
python -m word_skills route "请准备项目申报书" --json
```

路由结果只声明登记状态和模式范围；`focused` 表示当前重点能力，`baseline` 表示已有结构化契约但仍需项目级验证。路由器不会自动写正文，也不保证用户材料已经齐备。

`skills list` 和 `route --json` 区分 `dependencies`（必需 Skill）与 `optional_dependencies`（按任务选用），不执行安装或环境检查。技术文档和软著的 Word 制作依赖为可选，项目申报仍保留现有制作依赖。文本路由显示 `matched`，表示已选入口；`implemented` 不表示本次写作或验收完成。

## 技术文档与 Word 交付

仅写作或审阅正文时使用上方领域 Skill。需要本项目制作 Word/PDF 时，再读取 `skills/word-document/SKILL.md` 和相应工具流程，填写 JSON 中间稿、证据账本后运行：

```powershell
python -m word_skills ingest "项目材料路径" --case "case"
python -m word_skills template --mode technical-report --out "draft.json"
python -m word_skills lint draft.json --case case
python -m word_skills build draft.json --case case --out delivery --soffice "SOFFICE_EXE" --pdftoppm "PDFTOPPM_EXE"
python -m word_skills review-init delivery
# 实际核对正文和全部页图后，填写 delivery/audit/review.json
python -m word_skills finalize delivery
```

`reviewed` 只表示已记录的内容和版面复核，不表示事实真实性、正式提交、受理或授权。模板支持范围、证据契约和交付状态见 `skills/word-document/references/`。

技术报告、设计说明的新稿需填写 `task_requirements`（用户任务、验收条件和正文块映射）；旧稿仍可构建草稿，补齐后才能定稿。审阅时逐项填写 `task_coverage`、逐事实块填写 `semantic_support`，总体内容和全部页图仍需实际核对。此记录证明已记载的审阅，不是自动语义认证。

技术报告和设计说明还提供可选的 `freeze-content`、`format-content`、`build-locked` 入口，用于冻结正文与来源、应用允许的格式修改并重新制作。它只保护指定入口中的内容一致性，不代替事实审阅或系统权限隔离；使用方法见 [技术文档流程](skills/oh-my-technology/references/workflow.md)。

固定资料入口为 `word-skills kb build/verify/search/context`。无 RAG 配置的资料包可本地查询；已导入的包可调用本机 RAGFlow，返回片段须匹配固定原文，失败不静默切换后端。资料、服务与凭据不随安装包分发，具体配置及证据边界见 [知识接入说明](docs/knowledge-integration.md)。

## 项目申报与软著准备

软著直接复用 Fokkyp 2.6 的分析、业务理解、源码候选、申请字段与手册流程，继续使用共享 Word 后端；手册保留章节、表格、命令和真实图片：

```powershell
python -m word_skills copyright prepare SOURCE_ROOT --out CASE --name NAME --version VERSION
# Agent填写上游业务模型和workflow/草稿/代码文件选择.json，形成manual.md及申请字段。
python -m word_skills copyright select CASE/copyright.json --workflow-selection CASE/workflow/草稿/代码文件选择.json --reviewed-by REVIEWER
python -m word_skills copyright package CASE/copyright.json --out DELIVERY --draft --soffice SOFFICE_EXE --pdftoppm PDFTOPPM_EXE
```

`--draft` 明确允许权属/完成日期等字段待确认，两个子文档保持 draft，不能定稿。字段齐备后去掉该开关，重新构建正式准备包；分别对 `DELIVERY/source` 和 `DELIVERY/manual` 执行共享 `review-init`、实际复核与 `finalize`，再运行 `copyright package-finalize DELIVERY`。

包内有独立源码/手册 DOCX 和 PDF、申请信息辅助 TXT、实际页数、待核对事项和审计。TXT 不是官方申请表；页数不证明完整程序范围、每页行数或登记资格。Fokkyp 的具体复用取舍见 [吸收记录](docs/05-fokkyp-reuse.md)，现行 v1 与业务状态见 [契约说明](docs/06-contracts-and-states.md)。

```powershell
python -m word_skills proposal template --profile nsfc-2026-general --out proposal.json
# 先摄入真实指南、事实、人员和附件并填写草稿；历史 Profile 只作回归。
python -m word_skills proposal lint proposal.json --case case --allow-expired
python -m word_skills proposal build proposal.json --case case --out proposal-delivery --allow-expired --soffice "SOFFICE_EXE" --pdftoppm "PDFTOPPM_EXE"

python -m word_skills copyright scan "SOURCE_ROOT" --out source-manifest.json
python -m word_skills copyright template --out copyright.json
# 填入原始源码行段、权属声明及真实手册后：
python -m word_skills copyright lint copyright.json
python -m word_skills copyright extract copyright.json --out "MATERIALS_OUTSIDE_SOURCE"
python -m word_skills copyright build copyright.json --out copyright-delivery --soffice "SOFFICE_EXE" --pdftoppm "PDFTOPPM_EXE"
```

`proposal build` 和 `copyright build` 使用相同的 DOCX/PDF/页图审阅门禁，产物只有在实际审阅后才能 `finalize`。软著抽取不估页、不改写代码；页面材料的真实操作和登记规则仍需按项目及当期要求另行核对。

## 专利兼容入口

规范入口位于 [skills/oh-my-patent/SKILL.md](skills/oh-my-patent/SKILL.md)。旧调用继续有效：

```powershell
python tools/patent.py template invention -o outputs/draft.md
python tools/patent.py lint outputs/draft.md
python tools/patent.py build outputs/draft.md -o outputs/review.docx --strict
python tools/patent.py env                     # 官方 XML 工具与宿主是否就绪
python tools/patent.py env --com               # 再启动 Word 实测插件加载
python -m word_skills patent template invention -o outputs/draft.md
```

专利 Skill、prompts、references 和六个领域模块的规范路径是 `skills/oh-my-patent/`；旧的 Python 包、`tools/patent.py` 和 `oh-my-patent` 命令继续可用。专利门禁和原 Python 包没有被通用技术文档渲染器反向依赖。

### 专利制作器：默认 auto

自 2026-10-24 起，`build` 的默认制作器为 `auto`：发明/实用新型调用固定上游 handsomestWei 的完整 Word 转换模块（MIT，提交 `6935a14d`，原件逐字节保存在 `oh_my_patent/render/_vendor/patent_application/`，每次制作前校验 SHA256），外观设计仍用本地受控排版。

```powershell
oh-my-patent build 稿件.md -o 申请文件.docx                   # auto：发明/实用新型走上游
oh-my-patent build 稿件.md -o 申请文件.docx --renderer local  # 草稿占位稿/强制本地
oh-my-patent build 稿件.md -o 申请文件/ --split               # 每个部分独立成文件
```

适配层只做三件事：把稿件投影成上游认识的 Markdown 文书、调用上游 `convert_md_to_docx`、在边界套用本项目 A4 / 黑色标题与正文 / 宋体 / 1.25 倍行距（判据见 [CNIPA 规则](skills/oh-my-patent/references/cnipa-2026.md#版面硬规则)）/ 2 字符首行缩进。有效公式生成原生 OMML；**缺图、公式回退为原文、普通括号误写 LaTeX 会明确失败并提示 `--renderer local`**，不会写成「制作成功」。含未登记图件的草稿（如 `examples/invention-example.md`）请显式加 `--renderer local` 生成带占位句的审阅稿。

`handoff` 与 `build` 使用同一个 `--renderer` 选择（默认 `auto`），并在交接包 `manifest.json` 的 `renderer` 字段记录实际使用的制作器；如需旧版面仍可显式 `--renderer local`。

官方 XML 转换已实机验证（2026-10-25）：Windows 11 + Microsoft 365 + 官方 WORD 转 XML 编辑器 V4.3，交接包拆出的四书分别转成 `100001`~`100004` XML 并全部通过官方 `cn-application-body-20080416.dtd`；权利要求 17/17 项、摘要 258 字逐字一致。安装与插件加载有两个坑：MSI 启动条件要求传 `SETUPEXEDIR`（直装报「只能从 bootstrapper 运行」），且发行方清单证书 2026-07-14 到期、无时间戳，全新安装默认不信任，需要当前用户级 VSTO 信任项。检测用 `python tools/patent.py env`，安装/修复用 `python tools/cnipa_install.py`，完整步骤与故障速查见 [官方工具安装与转换](skills/oh-my-patent/references/cnipa-official-tool.md)。

交接说明已按官方手册提示：`摘要附图` 文书仅供审阅，转换前删除（系统改为在请求书里指定图号）。转换必须**逐份单书**做「一键添加标记 → 单书XML转换」；把五书合进一个单节文档时工具会把整篇当成权利要求书。

限制：外观设计不走该路径；`latex2mathml`、`docxcompose` 为运行依赖；WPS 12.1 与 Word 365 均已完成打开/导出/编辑往返；官方 XML 转换已验证，**正式提交仍未验证**（需申请人账号、请求书与电子签名）。固定原件、边界差异与验证范围见 [复用决策](docs/upstream-reuse.md)。

## 验证

```powershell
python tools/check_word_skills.py
python tools/check_skills.py
python -m pytest -q
python tools/check_full_dependencies.py
```

`check_word_skills.py` 和 `check_skills.py` 只证明结构、路径和声明一致；测试证明确定性代码行为。真实写作质量、事实语义、全部 Word/WPS 版本和用户页面体验仍需按对应材料和环境独立复核。

`check_full_dependencies.py` 使用同一解释器执行 pytest 全部测试并记录依赖版本、测试数和跳过项；缺依赖、失败、skip、xfail 或 xpass 均使验收失败。报告保存在本地 `outputs/acceptance/`。

`tools/check_installed_delivery.py` 在仓库外安装 wheel 后，会用纯文本发明稿分别执行默认本地制作器与 `--renderer upstream`，核对固定原件哈希、A4 版面、权利要求书/说明书/说明书摘要三类文书与正文标记，并确认默认路径未变。CI 的 Linux 3.10/3.12、Windows 3.12 矩阵与隔离 wheel 任务都执行该步骤。

默认 `pytest` 和完整依赖检查器均只收集 `tests/` 和 `evals/`，避免 `outputs/` 中摄入的外部项目测试被误收集。完整依赖检查器同时记录依赖与测试执行结果，拒绝skip/xfail/xpass；公共采集工具的测试还需安装 `beautifulsoup4`。这些测试不会启动模型跑批或 RAGFlow 部署。

## 许可与来源

代码使用 MIT 许可。共享写作规则、依赖、固定来源和改编范围见 [THIRD_PARTY.md](THIRD_PARTY.md)。官方 Word 转 XML 工具只是专利交接路径的外部依赖，不随仓库发布，也不由本项目自动提交文件。
