# 工具流程

仅在选择本项目的结构校验或 Word/PDF 制作时使用本页。正文起草与审阅可以直接按领域写法进行，不需要安装这些依赖；进入本页后原有 JSON、证据、渲染和审阅要求仍须满足。

从本技能文件向上三级找到仓库根目录；完整目录安装是当前受支持形态，不能只复制 SKILL.md。用可用 Python 3.10+ 安装 `pip install -e ".[ingest,templates]"`；外部程序需要 LibreOffice 和 Poppler。Codex 桌面环境优先使用其 bundled Python；命令示例中的 `python` 替换为实际解释器。工具不会自动下载外部程序。

```text
python -m word_skills ingest SOURCE_PATH [MORE_PATHS ...] --case CASE_DIR
python -m word_skills template --mode technical-report --out draft.json
python -m word_skills lint draft.json --case CASE_DIR
python -m word_skills build draft.json --case CASE_DIR --out NEW_OUTPUT_DIR --soffice SOFFICE_PATH --pdftoppm PDFTOPPM_PATH
python -m word_skills review-init NEW_OUTPUT_DIR
# 实际阅读正文及每页图像后，填写 audit/review.json
python -m word_skills finalize NEW_OUTPUT_DIR
```

设计说明使用 `--mode design-spec`。输出目录必须是新路径，避免旧 PDF/审查结果被混入。摄入仅读取本地资料，关闭 MarkItDown 插件，不上传文件，不执行项目或 Office 宏。

## 摄入

`source-index.json` 记录原件快照、SHA、提取文本、定位段落和告警。MD/TXT/代码按行定位，DOCX 按 body/row 定位，PDF 按页定位。未知格式、转换失败和扫描页必须查看 skipped/notices；不要声称未读材料已核验。未知语言扩展名可作为单独 UTF-8 文本副本提供，同时保留原件对应关系。

## 起草

先填写 `evidence.json`，再写 `draft.json`。JSON 对象的例子见 [证据与中间稿契约](../../word-document/references/evidence.md)。每个段落或表格有稳定 id、intent 和 claim_ids。所有重要事实按原件核对；分析段也不能绕过数字检查。

技术报告与设计说明需按实际用户目标填写 `task_requirements`，映射正文及可见缺口。来源名称和定位以 source-index.json 为准，不另维护重复注册表。需要读者可见出处时，将资料名称及用途写入正文的参考来源说明；内部 claim ID 留在审计中。标题先用具体主题，含版本的事实放正文，当前数字标题门禁仍适用。

初始模板有待补充占位符，不能直接交付。必要章节可以明确说明“尚无性能实测材料”，不能留空或伪造结果。补充章节使用独立 ID，层级只支持连续的一级至三级。

## 内容审查与渲染

lint 失败先修证据或内容。没有证据时移除无依据陈述，或写明缺口；不能把真实事实改写成分析段来绕过验证。机器只检查引用、变化和数字覆盖，全文语义仍需实际审查。

`--no-preview` 只用于调试，交付状态是 draft。正式路径输出 DOCX、PDF、页图与 audit。所有 warning 逐项检查；在 review.json 的 accepted_warnings 中填入 `digest(warning)` 和理由。digest 是对 JSON 按键排序、UTF-8 序列化计算的 SHA256，可调用 `word_skills.common.digest`。

finalize 只验证审阅记录齐全和哈希仍一致，不证明审阅人真的看过文件。不得自动生成 pass；应逐页记录观察和内容审阅依据。

### 可选：锁定内容后排版

技术报告和设计说明完成正文与证据机械校验后，可先冻结输入，再由排版步骤应用受限 patch。用户要求继续改正文时，回到草稿修改并建立新锁；不要重写旧 bundle。

```text
python -m word_skills freeze-content draft.json --case CASE_DIR --out NEW_LOCK_DIR
python -m word_skills format-content NEW_LOCK_DIR --patch layout.json --out NEW_FORMATTED.json
python -m word_skills build-locked NEW_LOCK_DIR --patch layout.json --out NEW_BUILD_DIR --soffice SOFFICE_PATH --pdftoppm PDFTOPPM_PATH
python -m word_skills review-init NEW_BUILD_DIR/delivery
# 实际审阅后仍通过原有 finalize 门禁
```

`format-content` 供单独查看排版后的 JSON；`build-locked` 自己应用同一 patch，不接收外部改写的 JSON。patch 示例：`{"blocks":{"methods-table":{"widths":[1,3],"style":"Table Grid"},"intro":{"inline_format":"markdown"}}}`。仅允许表格 widths/style 和段落 inline_format；正文、来源、claim_ids、intent、标题及版本不在可修改范围。行内 Markdown 只支持普通文本、行内代码和软换行，其他结构报错；表格单元格仍为字面文本。

锁定文件保存正文、账本、登记来源快照/定位及图片哈希，发现变化时拒绝排版/构建；失败产物保留供诊断，换新输出目录重试。现有来源验证仍可能核对 source-index 中存在的原件路径，原件变动会阻止构建，锁定不能绕过该检查。本地清单可被主动重建，不是签名、权限隔离或语义认证。

`locked-build-manifest.json` 是构建时快照，其 finalized=false/semantic_review=not_performed 不随之后的审阅更新；后续审阅状态以 `delivery/manifest.json` 为准。渲染成功仍是 awaiting-review；不渲染为 draft。逐事实块检查对象、关系方向、条件、人群、时间及“提案/已交付”的区别，不能因引文命中就填写 supported。关系模型只作建议，不自动改 verified。

`review-init` 生成的 `task_coverage` 和 `semantic_support` 均为 pending。实际核对后，任务项填 covered/partial/gap/not-applicable 和具体位置、依据或理由；partial/gap 不能定稿，not-applicable 必须确实不属于本次任务，不能用来隐藏缺失要求。事实块填 supported/unsupported，并在 notes 中核对整段的对象、条件和来源支持；unsupported 不能定稿。即使引文和数字全部命中，也应检查无数字的用途、效果或因果是否被无依据加入。所有正文（含 analysis/gap）仍需总体内容审阅。

预览在独立临时目录生成，manifest.renderer.provenance 保存 DOCX/PDF/页图哈希、工具身份和调用参数。PDF 内容提取检查标题、章节、段落及表格单元格是否保留；这不代替分页、重叠及截图对应关系的视觉审阅。技能资源指纹与生成器指纹分别记录；改稿、技能或来源变化后重新构建。
