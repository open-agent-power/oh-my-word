# 第三方来源与复用记录

更新日期：2026-10-15。本项目使用成熟库处理 Word、模板与材料；本地胶水代码实现证据契约、模式校验及交付状态。没有复制 Anthropic DOCX、字体文件或外部专利实现代码。

## 已改编的写作规则

| 来源与固定提交 | 许可 | 实际落地 | 修改范围 |
|---|---|---|---|
| [Fenng/Tech-Doc-Style-Chinese](https://github.com/Fenng/Tech-Doc-Style-Chinese/tree/b119d01c9bb7cd132b3c62fafdff34227c4410d1) | [MIT](third_party/licenses/fenng-MIT.txt) | shared/references/chinese-writing.md | 精简为事实保真、术语和机器标识符原则，不继承个人标点偏好 |
| [riekelt/technical-writer](https://github.com/riekelt/technical-writer/tree/85e53729dd959a2795d593d6769068e342cf3486) | [MIT](third_party/licenses/technical-writer-MIT.txt) | skills/oh-my-technology/references/design-spec.md、technical-report.md | 改编事实/提案区分、设计取舍、受众/目的先行、逐结论来源及按缺陷最小修订；不复制英文文风限制 |
| [handsomestWei/patent-disclosure-skill](https://github.com/handsomestWei/patent-disclosure-skill/tree/6935a14d342ed9c7a07440c999d1b7bf1852a701) | [MIT](third_party/licenses/patent-disclosure-MIT.txt) | skills/oh-my-patent/references/drafting-method.md | 选择性适配交底到各文稿部分的材料映射及逐权项/实施方式/附图对照；不引入其执行代码、目录/YAML协议、固定对比文件数或交付政策 |

以上实际改编项及运行依赖版本记录在 [upstream.lock.json](upstream.lock.json)，并保留完整许可证。

2026-10-24 技术写作参考另提供 [Google Audience](https://developers.google.com/tech-writing/one/audience)、[Documents](https://developers.google.com/tech-writing/one/documents) 的阅读入口，不复制课程（页面通常为 CC BY 4.0，例外依原页）。报告组织与审阅方法参考 Carol A. Vidoli，1992，[NASA-TM-105419](https://ntrs.nasa.gov/citations/19930013813)；原始记录标注美国政府作品、允许公共使用。新增示意案例为本项目编写，不代表实验结果；未引入两者代码、图像或行政要求。

专利方法参考：世界知识产权组织（2023），[《产权组织专利撰写手册》第二版中文PDF](https://www.wipo.int/edocs/pubdocs/zh/wipo-pub-867-23-zh-wipo-patent-drafting-manual.pdf)，[出版记录](https://www.wipo.int/publications/en/details.jsp?id=4706)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。来源页按章节路由，本地方法页由本项目选择、概括及适配，不是官方背书或对中国规则的替代，不复制其商标/图像。依原文要求：“对于原始内容的转换或翻译，产权组织秘书处不承担任何责任。”官方规则按来源页引用原文，不整篇收录；自编示意与官方案例分开。

## 方法参考，未复制源码或文案

[official-document-drafting](https://github.com/zhaohui-yang/official-document-drafting/tree/6b4166a50b96733684b36da6336ea85a847cf3be) 的 `skills/document-qa/SKILL.md` 用于比较章节检查与人工语义复核的边界，取舍见 [docs/04-reuse-and-poc.md](docs/04-reuse-and-poc.md)。仓库 LICENSE 为 [MIT，资产除外](third_party/licenses/official-document-MIT.txt)；本项目的检查程序独立实现，未导入公文格式、字体或文种模板。仅方法对照不伪称代码集成。

## 运行库

| 库 | 本轮验证版本 | 使用方式与许可 |
|---|---|---|
| python-docx | 1.2.0 | 直接依赖，MIT；DOCX 对象与样式 |
| docxtpl | 0.20.2 | 可选依赖，LGPL-2.1；受限插槽模板 |
| docxcompose | 1.4.1 | docxtpl 子文档辅助，MIT |
| MarkItDown | 0.1.8 | 可选依赖，MIT；本地 DOCX/PDF 摄入 |
| PyYAML | 6.0.3 | 直接依赖，MIT；章节契约 |
| markdown-it-py | 运行时版本记入测试环境 | 直接依赖，MIT；复用Markdown解析而不自写语法处理器 |
| pdfplumber | 0.11.9 | 直接依赖，MIT；PDF 文本位置与版面启发式检查 |
| pypdf | 6.10.0 | 直接依赖，BSD-3-Clause；页数及按页文本 |
| LibreOffice | 具体运行版本记入 manifest | 外部程序，不随代码发行；遵循其原有许可 |
| Poppler | 具体运行环境提供 | 外部程序，不随代码发行；遵循其原有许可 |

第三方库通过包管理器安装，不复制源码或重新许可。发行安装器、捆绑二进制或修改库前，另核对相应版本完整许可及间接依赖声明。`requirements-tested.txt` 记录本轮主要运行版本，不代表全部传递依赖锁定。

## 业务技能复用核查

以下固定提交用于申报/软著技能，均为 MIT。Fokkyp 当前直接复用阶段脚本，其余按表中范围使用。

| 来源与固定提交 | 核查文件 | 本地落点 | 复用决策 |
|---|---|---|---|
| [Fokkyp/SoftwareCopyright-Skill](https://github.com/Fokkyp/SoftwareCopyright-Skill/tree/e78f746e0254ed4be7e9a561ce0acc7180d5370a) | `software-copyright-materials/SKILL.md`; `scripts/extract_code_material.py`; `LICENSE` | `word_skills/copyright.py`; `skills/oh-my-copyright/` | 直接复用2.6分析、业务理解、候选、字段、手册、确认和截图清单脚本；原件及哈希在 word_skills/_vendor/fokkyp；不采用 OfficeCLI 执行器 |
| [suling-fun/software-copyright-materials-skill](https://github.com/suling-fun/software-copyright-materials-skill/tree/d7b49eea8f6e455ef3547c0d16d1945e204bc8a7) | `SKILL.md`; `verify_materials.py`; `LICENSE` | `word_skills/copyright.py`; `skills/oh-my-copyright/` | 采用机械校验与人工语义复核的边界；不复制黑名单或登记器 |
| [caolonghao/nsfc-grant-assistant-skill](https://github.com/caolonghao/nsfc-grant-assistant-skill/tree/a694ab4cfbf8bad64357c6803e5f39c4b0eda47a) | `ndrc-bid-assistant/`; `LICENSE` | `word_skills/proposal.py`; `skills/oh-my-proposal/` | 采用渠道/指南/条件证据先行；不复制评审模型或 Agent 编排 |

每项的固定提交、许可证文本和核查结果也记录在 [upstream.lock.json](upstream.lock.json)。候选调查仍在 [docs/upstream-sources.json](docs/upstream-sources.json)，不能把候选列表当作已集成依赖。

2026-10-17 从2.5流程改编升级到2.6原脚本复用。原件、许可证和固定哈希保留；适配代码位于copyright_workflow.py，不修改上游文件；仍保留源码原文、共享Word后端和实际分页检查。逐项对照见 [docs/05-fokkyp-reuse.md](docs/05-fokkyp-reuse.md)。

## 本轮新增候选但未集成

| 仓库 | 固定 SHA | 实际核查与决策 |
|---|---|---|
| [docling-project/docling](https://github.com/docling-project/docling) | 6fadbae317b09c4dd4051c0f1fc1746c6baf04bc | GitHub 识别 MIT，目录已核查；暂不安装模型和复杂输入后端，模型许可尚待具体选型 |

OpenAI skill-creator 使用当前环境提供的初始化/元数据/校验工具，未复制到本仓库。初轮来源继续见 docs/upstream-sources.json；它是候选调查记录，不是实际依赖锁。

## 未复制资源

Anthropic docx 明确列为受限材料；doc-coauthoring 的通用协作方法可比较，原文未复制。未明确授权的技术标书与 Pandoc 模板仓库不导入。字体使用运行环境已有字体，本仓库不分发字体二进制。
