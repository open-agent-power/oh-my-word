# 架构评估：oh-my-word / word-skills（2026-10-25）

目的：回答“现在这套结构值得优化吗、先优化哪几处”。只写看过仓库后能指到具体文件的问题，
以及本轮已经动了什么、建议下一轮做什么。

## 一、现状（事实）

| 层 | 位置 | 说明 |
| --- | --- | --- |
| Skill 入口 | `skills/*/SKILL.md` | 7 个 skill：oh-my-patent、oh-my-copyright、oh-my-proposal、oh-my-technology、word-document、word-skills，加上子目录 |
| 提示词 | `skills/oh-my-patent/prompts/00..08` | 流水线步骤，编号稳定，但无索引或与测试的绑定 |
| 规则/参考 | `skills/oh-my-patent/references/*.md` | cnipa-2026、cnipa-xml-handoff、drafting-method… |
| 代码 | `oh_my_patent/`、`word_skills/` | 只有专利这一支有 Python 实现；其余 skill 基本是提示词 |
| 工具 | `tools/patent.py`（CLI 门面）、`check_*.py`×5、ingest 转换器、`ragflow/` | CLI 只转发；检查脚本各自为政 |
| 文档 | `docs/`20+ 篇 | format-spec / cnipa-format-lessons / skills references 三处都在讲版式规则 |

## 二、值得优化的五处（按收益排序）

### 1. 规则没有单一事实源（最高优先 —— **2026-10-25 已处理**）

“页码下沿距纸底 15mm”“行距 1.25 倍”“字高 4.5mm 上限”同时出现在：

- `docs/format-spec.md`（条款与实现对照）
- `docs/cnipa-format-lessons.md`（实测与踩坑）
- `skills/oh-my-patent/references/cnipa-2026.md`（skill 侧规则）
- `skills/oh-my-patent/prompts/06-specification-build.md`（写作提示）

四处独立维护，本轮就出现过“lessons 说 1.5 倍合规、实测 4.32mm 超标”需要回头订正的情况。

**已落地**：`references/cnipa-2026.md` 声明为唯一事实源（含“版面硬规则”小节），
`docs/format-spec.md` 降为“实现对照”，prompts/06、prompts/07、SKILL.md、README、lessons
改为链接；新增 `tools/check_rule_sources.py`（进 CI）检查“复述数字却没有链接”的文件，
并补了 4 项测试。改规则现在只改一处。

### 2. 检查脚本碎片化

`tools/` 下有 `check_skills.py`、`check_word_skills.py`、`check_delivery_environment.py`、
`check_full_dependencies.py`、`check_installed_delivery.py`、`check_knowledge_pack.py`、
`check_code_manifest.py`。CI 里逐条调用，名字相近、失败信息格式不一。

**建议**：合并成 `tools/check.py --skills --env --delivery --manifest --all`，
内部复用现有函数，CI 一行调用；旧的 check_* 保留为薄壳转发，避免一次性破坏外部脚本。

### 3. 官方工具这一段完全在仓库外

本轮之前，“装官方工具 → 加标记 → 转 XML → DTD 校验”只存在于人的操作里，
仓库没有任何检测/安装/校验代码，踩过的坑（SETUPEXEDIR、证书过期、图号在图内）也没有落点。

**本轮已补**：
- `oh_my_patent/cnipa_env.py`：宿主/插件/签名/信任/DTD 检测，`--com` 实测插件 Connect，`--fix-trust` 修信任项；
- `tools/cnipa_install.py`：UAC 提权装 MSI（传 SETUPEXEDIR）+ 清残留 + 补信任 + 复检；
- `skills/oh-my-patent/references/cnipa-official-tool.md`：整条链与故障速查；
- `SKILL.md` 工具链路第 7 步改为“先 `env` 再转换”。

**仍断在**：Word 里点「一键添加标记 → 单书XML转换」。这一段是 VSTO 加载项，
没有公开命令行；UIA 点击可变但脆弱（本轮实验脚本 `ribbon_click.py` 就是这么干的）。
是否做成 `--auto` 实验路径，建议等官方提供 CLI 或接口，避免把 UI 自动化写进正式交付链。

### 4. 根目录被构建产物污染

仓库根同时有 `build/ dist/ outputs/ outputs.zip pip-build-tracker-*/ pip-install-*/ pytest-of-*/ *.egg-info/`。
它们虽被 `.gitignore` 挡住（`git status` 干净），但会让人误以为仓库结构如此，
也让新同学难判断“哪些是源码”。

**建议**：构建/临时产物统一到 `.cache/` 或 `%TEMP%`；根目录只留源码、文档、配置。

### 5. 六个 skill 的复用边界不清

`oh-my-copyright` / `oh-my-proposal` / `oh-my-technology` 各自有 `agents/` 和 `references/`，
但都依赖 `word-document` 的知识与 `word_skills` 的转换能力；`check_skills` 只校验结构，
不校验“是否重复了同一份规则”。

**建议**：`check_skills` 增加两条规则：①同一段规则文本不得在两个 skill 里复制（命中即提示改成链接）；
②每个 skill 必须声明它依赖的共享 skill 与共享文档。

## 三、本轮动到的文件

| 文件 | 变化 |
| --- | --- |
| `oh_my_patent/cnipa_env.py` | 新增：环境检测 + 信任项修复 + `--com` 实测 |
| `oh_my_patent/cli.py` | 新增 `env` 子命令 |
| `tools/cnipa_install.py` | 新增：原子安装（提权、SETUPEXEDIR、清残留、信任、复检） |
| `skills/oh-my-patent/references/cnipa-official-tool.md` | 新增：安装/转换/图号/校验/提交/故障速查 |
| `skills/oh-my-patent/SKILL.md` | 工具链路第 7 步改为先检测再转换 |
| `tests/test_cnipa_env.py` | 新增 12 项：检测结论、信任项、CLI |

## 四、下一轮建议（按顺序）

1. 规则去重（第二节第 1 条），一次只改 `cnipa-2026.md` 与 `format-spec.md`。
2. 合并检查脚本（第 2 条）。
3. 清理根目录产物（第 4 条）。
4. 把“五书合一文档的正确构造”补进 `cnipa-official-tool.md`（目前只记录了“单节合订本识别失败”）。
5. 如需全自动：等官方提供命令行；否则把 UIA 自动化明确标成实验脚本，不进交付链。
