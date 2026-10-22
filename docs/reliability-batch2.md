# 内容冻结与证据关系检查

本轮增加技术报告/设计说明的可选内容冻结入口，把“确定正文”与“修改排版”分开。来源、账本、正文及登记资产由本地哈希清单绑定；排版 patch 仅能调整表格 widths/style、段落 inline_format。新 `build-locked` 复用既有制作及审阅门禁，输出后核对实际 audit 输入，发现变化时失败。用法见 [工具流程](../skills/oh-my-technology/references/workflow.md)。

它提高格式步骤的输入完整性，不证明引文支持结论，不提供不可篡改签名或 OS 隔离。需要改正文时改原稿并建立新锁；新机制保持可选，旧 build 兼容。状态仍是 draft/awaiting-review，关系模型不能自动变成 verified。

回归 474 项及 185 个子测试通过；公开材料的两个模式经真实 CLI/LibreOffice 生成各两页，四页全部实际查看。正文 patch 与 evidence 篡改反例均被阻止。最终产物未定稿，短尾页留白仍在。16 次预冻、已曝光机制小样 A/B 均命中 7/8，无整体提升证据；其中一个错配是重叠标签，不应误称事实幻觉。未改默认提示词。

详细结果与原始证据在 [第二轮结果](D:/XiangMuLuoDi/Development/word-skills-reliability-batch2/RESULT.md)。本地路径用于当前工作区复查，发布仓库前应另行提供可移植的证据存储。代码 identity `40e91761aac19855bc5b020763af3ebc7298ad986fe0e33246aa394cd3f80a3f`，Skill identity `9f738b26dffeb75d05bb8a3371bae18cbb6adc661d19bb7fb368344d01eeb805`。没有提交、推送或使用保密材料。
