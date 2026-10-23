# 证据和中间稿 v1

`evidence.json` 结构：

```json
{
  "schema_version": 1,
  "claims": [{
    "id": "C1",
    "statement": "项目使用 Java 17。",
    "source_id": "S001",
    "locators": ["L1"],
    "quote": "java.version=17",
    "status": "verified",
    "verified_by": "实际核验人",
    "verified_at": "实际核验日期"
  }]
}
```

示例不代表任何实际项目。只有核对原件和 statement 的语义支持后才记 verified。未使用的 unverified 记录可以留在账本，正文不能引用它作为依据。数字出现在来源中不是充分条件，还要核对对象、单位、条件及目标/实测状态。

解释源码行为时，核对实际调用入口、参数和分支；不要将下层函数的条件直接套到调用入口。只有逐步核对过的中间值和执行顺序才写进正文；无法确认时只写有依据的结果或保留缺口，区分源码推演与实际运行，不为说明更详细而补造过程。

引文应支持其对应的具体结论。函数签名不能证明某组输入的运行结果，某个成员的单行定义不能证明整个类不存在另一种机制。涉及“没有”“所有”“只执行一次”等范围判断时，核对足够完整的实现与调用条件；材料不完整就限定结论，不用逐字匹配通过代替这一步。

`draft.json` 包含 schema_version=1、mode、title、sections。每节为 `{id,title,level,blocks}`，level 默认 1。

段落：`{id,type:"paragraph",text,intent,claim_ids}`。

表格：`{id,type:"table",headers:[...],rows:[[...]],widths:[1,3],style:"Table Grid",intent,claim_ids}`。widths 是列宽比例，可省略。style 必须存在于参考文档中。

intent：fact 是来源支持的事实；analysis 是有边界的分析/建议；gap 是具体材料缺口。引用只记录在审计材料中，正式正文不印 ID。数字检查同样适用于分析和缺口段；数字和版本放在正文而非标题中。

图片：`{id,type:"image",text,intent,claim_ids,path,sha256}`。仅支持 case 内经哈希核对的 PNG/JPEG，text 是可见图注；不代表任意浮动图、扫描件或复杂布局支持。代码块必须与 source_id 的原件 line_start 至 line_end 行段完全一致。

重点模式增加 `task_requirements:[{id,text,acceptance,block_ids}]`，将每项用户要求及验收条件指向实际正文块，缺口也须在正文可见。该字段不证明任务已被完整拆解；仍须对照原始请求审阅。旧稿缺失该字段时 lint 给 warning，保持草稿构建兼容；定稿前必须补齐。

v1 不支持公式、嵌套表格、任意富文本、修订模式或自动书目排版。需要这些内容时另选可验证的制作路径，不将缺失功能伪装成通用支持。

重要限制：引用逐字匹配、数字集合和哈希校验都无法证明因果关系、语义蕴含、真实性或完整披露。无数字的虚构内容也可能逃过机器检查；语义复核必不可少。
