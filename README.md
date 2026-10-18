# oh-my-word / word-skills

`word-skills` 是一个可安装的 Word Skills monorepo：它把中文技术文档制作、可追溯的 Word 交付和既有中国专利审阅稿工具放在同一套可验证的来源、渲染与交付边界中。

当前实现包括：

- `word-skills`：总入口、技能注册表和确定性路由；
- `oh-my-technology`：以技术报告、设计说明为重点的技术文档 Skill，并保留需求规格、接口说明、测试报告、用户手册和运维手册五种有契约约束的扩展模式；
- `word-document`：基本单节样式与受限 `docxtpl` 插槽模板；
- `oh-my-patent`：原有发明、实用新型、外观设计 CLI、六个领域模块和 final/handoff 门禁；
- `oh-my-proposal`：版本化指南、要求/章节/附件映射、人员材料和预算一致性检查；
- `oh-my-copyright`：源码清单、原文选段、手册/申请字段一致性及材料生成。

项目申报与软件著作权已接入 CLI 和共享交付链。附带的 NSFC Profile 只用于过期历史案例，不能当作当前开放渠道；真实申请仍须当期官方指南、申请人资料及人工核查。目标架构和能力边界见 [docs/02-architecture.md](docs/02-architecture.md)、[docs/03-roadmap.md](docs/03-roadmap.md) 和 [registry/skills.yaml](registry/skills.yaml)。

## 安装

需要 Python 3.10+。基础安装包含专利和技术文档的结构检查、Word 生成与来源校验；读取 DOCX/PDF 材料和插槽模板使用可选依赖。

```powershell
python -m pip install -e ".[dev,ingest,templates]"
python -m word_skills skills list --json
python tools/check_word_skills.py
```

安装包不包含真实案卷、`outputs/`、本机证据、LibreOffice、Poppler 或字体。完整 monorepo 是受支持的 Skill 安装形态，不能只复制一个 `SKILL.md` 就声称共享资源已安装。

## 总入口与路由

```powershell
python -m word_skills route "请写一份技术报告" --json
python -m word_skills route "只调整 Word 页眉和页码" --json
python -m word_skills route "请准备项目申报书" --json
```

路由结果只声明登记状态和模式范围；`focused` 表示当前重点能力，`baseline` 表示已有结构化契约但仍需项目级验证。路由器不会自动写正文，也不保证用户材料已经齐备。

## 技术文档与 Word 交付

将 `skills/oh-my-technology/SKILL.md` 和 `skills/word-document/SKILL.md` 交给 Agent，阅读来源后填写 JSON 中间稿和证据账本，再运行：

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
python -m word_skills patent template invention -o outputs/draft.md
```

专利 Skill、prompts、references 和六个领域模块的规范路径是 `skills/oh-my-patent/`；旧的 Python 包、`tools/patent.py` 和 `oh-my-patent` 命令继续可用。专利门禁和原 Python 包没有被通用技术文档渲染器反向依赖。

## 验证

```powershell
python tools/check_word_skills.py
python tools/check_skills.py
python -m pytest tests -q
python tools/check_full_dependencies.py
```

`check_word_skills.py` 和 `check_skills.py` 只证明结构、路径和声明一致；测试证明确定性代码行为。真实写作质量、事实语义、全部 Word/WPS 版本和用户页面体验仍需按对应材料和环境独立复核。

`check_full_dependencies.py` 使用同一解释器执行 pytest 全部测试并记录依赖版本、测试数和跳过项；缺依赖、失败、skip、xfail 或 xpass 均使验收失败。报告保存在本地 `outputs/acceptance/`。

## 许可与来源

代码使用 MIT 许可。共享写作规则、依赖、固定来源和改编范围见 [THIRD_PARTY.md](THIRD_PARTY.md)。官方 Word 转 XML 工具只是专利交接路径的外部依赖，不随仓库发布，也不由本项目自动提交文件。
