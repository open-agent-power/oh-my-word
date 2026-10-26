# 分支与合并流程

仓库的默认分支是 `codex/oh-my-word-integration`，不是 `main`。所有对外可见的改动最终都落在这个分支上；`main` 只是历史名，不参与当前发布。

## 现状与约定

- 外部贡献从各自 fork 拉分支，向默认分支发 Pull Request（PR #1、#2 都是这个形态）。
- 本仓库自己的日常改动也应走同样的路径：从默认分支切 `codex/<主题>`，推分支，开 PR，CI 通过后合并。
- 默认分支已开启保护：必须经 PR、必须通过下列必需检查、禁止强推和删除。管理员账号保留绕过能力，仅用于修复 CI 基础设施或清理误推，不用于日常提交。

## 必需检查

保护规则要求的检查项来自 `.github/workflows/ci.yml`，名称固定为：

- `checks (ubuntu-latest, 3.10)`
- `checks (ubuntu-latest, 3.12)`
- `checks (windows-latest, 3.12)`
- `preview`

其中 `checks` 矩阵会依次运行 `python -m pip check`、`python tools/check.py --all`、`python tools/check_full_dependencies.py`（不允许 skip/xfail），并校验 wheel 在检出目录外的隔离安装；`preview` 用 LibreOffice + Poppler 真实生成 PDF 和页图。

## 提 PR 之前

在本地按下面顺序自查，避免把 CI 当作第一次运行：

```powershell
.\.venv\Scripts\python.exe tools\check.py --all
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

`tools/check.py --all` 只跑轻量静态检查（skills、word-skills、规则出处、跨 skill 重复、skill 依赖、行尾）。依赖相关、知识库、材料等检查需要显式指定分组，CI 里的完整回归由 `tools/check_full_dependencies.py` 承担。

写 PR 描述时记录：问题、改动、实际执行的验证命令与结果、以及明确不宣称的边界（例如结构校验通过不等于内容质量或业务受理通过）。PR 描述里的数字应当能在对应提交上复现；主干后来新增检查时，以合并后重跑的结果为准，并把这些差异写在评论里。

## 合并方式

- 单个提交的 PR 用 **squash**，保持默认分支线性历史。
- 需要保留多个提交的独立意义时才用 merge commit，并在 PR 里说明理由。
- 合并时不要顺手删除对方 fork 上的分支（本仓库无权限，也没有必要）。
- 合并后在本机 `git pull --ff-only`，确认 HEAD 与远端一致；需要时在 PR 上补一条合并后复核评论。

## 合并后

- 检查合并后提交的 CI 结果；失败时按日志修复，而不是跳过检查。
- 记录验证范围：`tools/check.py --all`、定向测试与全量测试的差别应当写清楚，不能用局部通过代替全量结论。
- 真实材料、机器路径和生成的 Office 文件不进入提交；证据留在被忽略的本地目录。
