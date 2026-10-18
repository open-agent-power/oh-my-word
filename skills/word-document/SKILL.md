---
name: word-document
description: 将已组织好的专业文档内容制作成 Word，导入基本参考样式或显式 docxtpl 插槽模板，生成 PDF 预览并检查结构、版面和交付清单。用于 Word 排版、模板适配和文件质量验证；不代替业务写作、事实判断或专利专用格式规则。
---

# Word 文档制作

使用成熟库完成 DOCX 操作，保留可追溯输入和实际预览。当前通用生成以 python-docx 为主，显式插槽模板使用 docxtpl；专利继续使用原独立工具，本技能不修改专利格式。

1. 读取 [证据与中间稿契约](references/evidence.md)，核对输入格式。
2. 用户有参考 Word 时读取 [模板支持范围](references/templates.md)，先 fingerprint，再选择 style 或 slots 模式。
3. 调用 `python -m word_skills build`。没有模板时默认 A4、中文正文、黑色标题、可换行表格和页码。
4. 检查 audit/validation.json、audit/layout.json，实际打开 DOCX/PDF 和全部 page 图；修订后生成新的输出目录。
   核对标题、正文、表格和页码在预览中保留，并确认页图与同包 PDF 对应；哈希完整不能代替视觉核对。
   `PDF_CONTENT_REVIEW` 表示提取未确认正文或表格内容（含重复行计数），可能是丢失，也可能是跨页或交错；逐项核对实际页面并说明接受依据，不能机械忽略警告。
5. 按 [工具流程](../oh-my-technology/references/workflow.md) 完成 review-init、真实审阅和 finalize。

DOCX 能打开、PDF 页数非零、机器检查通过、人工/Agent 语义与视觉复核是不同事实。对缺失字体、复杂模板、扫描 PDF 或无法运行的转换器如实记录，不自动降级为通过。

交付正式文件保持正文干净；审计材料放 audit。页图用于核对，不要求用户逐个处理。不得自动上传或提交到外部系统。
