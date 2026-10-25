---
name: word-skills
depends_on: [word-document, oh-my-patent, oh-my-copyright, oh-my-proposal, oh-my-technology]
description: 根据用户目标选择技术文档、专利、项目申报、软件著作权或 Word 制作能力，并在多份文档任务中组合共享的来源、事实和交付链路；业务状态以注册表和验证证据为准。
---

# word-skills 总入口

这是仓库级路由入口，不替业务 Skill 起草正文。先根据用户请求选择一个或多个已登记能力，再读取对应的 `SKILL.md`。能力状态以 [注册表](../../registry/skills.yaml) 和对应测试/试运行证据为准；文件存在本身不代表业务事实或法律资格已经验证。

产品、材料、事实、文稿及交付完成含义按 [共用语义与状态](../../docs/06-contracts-and-states.md)。注册表的 `dependencies` 是必需 Skill，`optional_dependencies` 只在选定相关路径时使用；两者都不表示已加载或已执行。路由匹配成功后仍由 Agent 读材料、写作与复核，不能把 `implemented` 当作本次任务已通过。

## 路由规则

| 用户目标 | 读取能力 | 当前状态 |
| --- | --- | --- |
| 技术报告、设计说明、需求、接口、测试、用户或运维文档 | `skills/oh-my-technology/SKILL.md` | 已实现七种模式；每种仍需内容和页面复核 |
| 已组织内容的 Word 排版、模板样式或页图检查 | `skills/word-document/SKILL.md` | 已实现：基本单节样式与受限插槽 |
| 专利交底、申请审阅稿、事实/权项检查和 XML 交接 | `skills/oh-my-patent/SKILL.md` | 已实现；沿用旧入口与六领域模块 |
| 项目申报书、可研和预算 | `skills/oh-my-proposal/SKILL.md` | 已实现指南/要求/附件/预算准备；当前示例 Profile 为历史资料 |
| 软件著作权材料 | `skills/oh-my-copyright/SKILL.md` | 已实现源码清单/身份/手册/摘录准备；登记页数和权属仍需人工核对 |

明确的业务请求可以直接进入对应技能。请求同时包含多个交付物时，先分别确定每份文档的来源和状态，再共享经过核对的事实；不要把一个文档的结论、审阅状态或权利要求自动复制到另一个文档。

## 共享边界

- 少量、版本明确的原件直接阅读；同案修改复用已核实来源与记录，只补查变化和缺口。资料过多、跨来源定位困难或用户明确要求检索时，再使用已有知识入口。材料选择和复用遵循 [材料使用与按需检索](../word-document/references/knowledge.md)。
- Agent 负责阅读材料、选择章节、组织正文和语义审查。
- Python 工具负责来源快照、哈希、结构/数值门禁、Word 生成和交付状态。
- 用户保留项目事实、权属、申报资格以及最终提交判断。
- 脚手架状态只能返回缺口和下一步，不能把空模板当成可交付材料。
- `reviewed` 只表示已记录的内容/版面复核，不表示事实真实性、提交、受理或授权。

## CLI

```text
word-skills skills list
word-skills route "写一份技术报告"
word-skills route "只调整 Word 页眉和页码"
word-skills patent template invention -o outputs/draft.md
```

先读取被选技能的写法和来源参考；是否使用工具按本次产物和该技能支持的路径决定。需要 Word 或结构校验时再读对应工具流程。需要专利工具时保留旧的 `python tools/patent.py ...` 与 `oh-my-patent ...` 入口；总入口只是兼容调度器，不改变既有专利门禁。
