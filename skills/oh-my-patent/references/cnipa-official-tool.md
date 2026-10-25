# 官方 WORD 转 XML 编辑器：安装、转换、提交

2026 年起电子申请只收 XML。这份文档只写**实机验证过**的步骤与故障处置，
依据是本项目 2026-10-25 在 Windows 11 + Microsoft 365 + 官方 V4.3 上跑通的一次完整转换
（四书 XML 全部通过官方 DTD）。

## 0. 先检测，再动手

```bash
python tools/patent.py env          # 人读：缺什么、下一步做什么
python tools/patent.py env --json   # 脚本判断用
python tools/patent.py env --com    # 真的启动 Word，确认插件 Connect（较慢）
python tools/patent.py env --fix-trust   # 当前用户级补信任项，不需要管理员
```

退出码：`0` 就绪 / `2` 降级（能用但有坑）/ `1` 未就绪 / `3` 非 Windows。

检测项与故障的对应关系：

| 检查 | 不通过时的真实症状 |
| --- | --- |
| 宿主（Word 2013+ 或 WPS 专业版 2015+） | 装完 Word 里没有「专利处理」；个人版 WPS 不加载 VSTO |
| 插件安装 | 无菜单、ARP 里没有「WORD转XML编辑器」 |
| 插件注册 | `HKCU\Software\Microsoft\Office\Word\Addins\CNIPR.PatentTool` 缺失或 `LoadBehavior≠3` |
| 清单签名 / VSTO 信任 | 事件日志 VSTO 4.0 报「签名清单或证书未知，自定义项不在信任列表中」 |
| DTD/XSL 资源 | 预览报「拒绝访问 …/dtdandxsl/cn-application-body-20080416.dtd」 |

## 1. 安装：必须管理员，且 MSI 要传 SETUPEXEDIR

```bash
python tools/cnipa_install.py --package <word转xml-安装包-*.zip 或解包目录>
python tools/cnipa_install.py --verify-only
```

脚本会做四件事：解包 → 清掉失败半装残留 → `msiexec /i ... SETUPEXEDIR=<目录> ALLUSERS=1 /qn`
→ 写 VSTO 信任项并复检。需要管理员时它会自己请求一次 UAC。

手装时记住两个坑：

1. **启动条件**：MSI 的 LaunchCondition 是 `SETUPEXEDIR OR (REMOVE="ALL")`，
   直接 `msiexec /i` 会报「This package can only be run from a bootstrapper」。传 `SETUPEXEDIR` 即可。
2. **共享数据目录**：安装要写 `C:\ProgramData\PatentTool`（Users 只读）。
   非管理员跑到一半 1603 回滚，还会留下 1.4 万个只读文件；
   下次安装必须在管理员下 `rd /s /q` 清干净，否则同一批文件报 1310/1603。

## 2. 插件信任：发行方证书已过期，必须补信任项

`PatentTool.vsto` 的 ClickOnce 清单签名证书 **2026-07-14 到期，且没有时间戳**，
所以 2026-07-14 之后的全新安装默认不加载插件。这是发行方打包缺陷，不是本机问题。

当前用户级解法（不需要管理员）：

```
HKCU\Software\Microsoft\VSTO\Security\Inclusion\{GUID}
    Url       = file:///C:/Users/<user>/AppData/Local/CNIPR/PatentTool_<ver>/PatentTool.vsto
    PublicKey = 清单 Signature/KeyInfo/KeyValue/RSAKeyValue 里的 <RSAKeyValue>…</RSAKeyValue>
    Name      = PatentTool
```

两个**必须**：`Url` 指到 `.vsto` 文件（指目录无效）；`PublicKey` 用清单 KeyInfo 的 RSAKeyValue
（用证书公钥无效）。`python tools/patent.py env --fix-trust` 就是干这件事。

## 3. 转换：先标记，再逐份「单书」

官方流程是「一键添加标记」→「单书XML转换」，产物落在 docx 同级的 `100001`~`100004` 目录
（XML + 附图 JPG），工具还会自动打一个同名 zip。

- **一次只放一本书**。实测把五书合进一个单节文档时，「五书XML转换」会把整篇当权利要求书，
  说明书/附图/摘要全塞进 claims。单节合订本点「制作压缩包」只得到 22 字节空包。
- **摘要附图不再单独收**：官方系统改为在请求书里指定图号，不要转 `摘要附图`。
- 附图 PNG 会被自动转成 JPG，图片保持 inline。
- 标记是私用区字符（U+E000–U+F8FF），转换后从 XML 里剥掉；做正文保真比对前要先剥。

### 3.1 自动点按钮（实验性，可选）

官方编辑器没有命令行，`python tools/patent.py convert <单书.docx> --validate` 用 UI Automation
替人点「一键添加标记 → 单书XML转换」，产物仍是官方工具生成，并可用官方 DTD 校验。

- 只在 Windows + Word 2013+ / WPS 专业版、插件已加载时可用；先 `patent.py env --com`。
- 依赖 `pip install -e ".[windows]"`（pywin32、comtypes）。
- 属于**辅助手段**：界面语言、菜单折叠、弹窗都可能让它失败，失败信息会说明卡在哪一步；
  交付前仍以官方工具里人工预览 + 系统预览为准。

## 4. 图号必须是正文文字，不能画在图片里

官方《文件格式建议》：图号以文字形式放在图片外。图号画进 PNG 时，工具找不到图号标记，
直接弹「请先添加标记」，转换中止。

修法（本项目对真实案卷做过）：擦掉图片内的「图N」像素 → 在图后插入正文「图N」段落。
插入段落时字体的 `w:ascii`/`w:hAnsi`/`w:eastAsia` **三处都要写宋体**，只写 `font.name`
（西文）会让中文回落到主题字体，标题看起来“字体乱了”。

## 5. 转换后必查（脚本可做）

| 检查 | 做法 | 本次实测值 |
| --- | --- | --- |
| DTD | `lxml.etree.DTD(官方 cn-application-body-20080416.dtd).validate()` | 四书全过 |
| 正文保真 | 剥标记后与源 docx 逐字比对 | 权要 17/17、说明书 7,772 字、摘要 258 字一致 |
| 摘要字数 | 汉字数 ≤ 300 | 239 |
| 权项引用 | 每项引用的编号必须小于自身编号 | 12 项无倒挂 |
| 段号残留 | 正文里不应有 `[0001]` 这类段号 | 0 处 |
| 附图 | `figure num=0001…`、`img inline=yes` | 3 幅 |

`cn-application-body-20080416.dtd` 对 `cn-drawings` 的建模本身 nondeterministic，
校验器会给一条 `DTD_CONTENT_NOT_DETERMINIST` 告警；`valid=True` 时它不是文档错误。

## 6. 提交（系统里做，脚本到不了）

依据官方《提交 XML 文件常见问题解答》问题 10：

1. 登录 `cponline.cnipa.gov.cn` → 「国家申请」→ 选发明专利 → 「新申请办理」。
2. 「上传」整个 XML 压缩包（目录结构 `100001/100001.xml`、`100003/…jpg`），
   或在页面里逐项导入单书 XML。
3. 请求书**在系统里逐栏录入**（不上传）；摘要附图在第 24 栏选「图1」。
4. 点「预览」核对（系统渲染 PDF 才是权威预览），无误后电子签名、提交、缴费。
5. 保存受理回执、申请号、缴费记录。

本地想看 XML 内容：官方 XSL 用的是站点绝对路径（`/dtdandxsl/showxml.xsl`），
浏览器直接打开 XML 会白屏；把 `dtdandxsl` 放在旁边并用本地 http 服务打开，
或预渲染成 HTML 再看。

## 7. 故障速查

| 症状 | 处置 |
| --- | --- |
| 安装 1603 / 「只能从 bootstrapper 运行」 | 管理员 + 传 `SETUPEXEDIR` |
| 1310 写入 `scaleimage.js` 失败 | `C:\ProgramData\PatentTool` 有只读残留，管理员 `rd /s /q` 后重装 |
| 装完没有「专利处理」 | 先查 VSTO 事件日志的签名错误 → `env --fix-trust` |
| 「请先添加标记」 | 该文书没加到标记：确认是单书文档、图号是正文文字 |
| 预览「拒绝访问 …dtdandxsl…」 | 文档同级或上级放 `dtdandxsl`（安装目录的 `dtdandxsl.zip` 解出） |
| 制作压缩包得到空 zip | 合订本没被识别成五书；改为逐份单书转换后自己打包 |
