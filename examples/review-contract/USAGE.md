# 功能演示

人工构造的温度采集示例，仅演示证据门禁与构建命令。不是现实发明，不提供查新/授权依据。

在项目根目录：

```bash
python tools/patent.py build examples/review-contract/draft.md -o outputs/demo.docx --final --facts examples/review-contract/TECH_FACTS.json --review examples/review-contract/content-review.json
python tools/patent.py handoff examples/review-contract/draft.md -o outputs/demo-handoff --facts examples/review-contract/TECH_FACTS.json --review examples/review-contract/content-review.json
```

改动任何输入须重新审查；不要只更新哈希。

附demo-review.docx为本示例输出，已检查三页中文渲染。只用于演示输出格式，不能作为现实案件申请。
