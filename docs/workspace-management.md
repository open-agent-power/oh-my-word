# 工作区管理

开发工作区和发布检出承担不同职责：开发工作区保存持续修改，发布检出只用于验证一个明确的提交。发布检出可以是临时目录，但不能作为长期状态记录的事实源。

## 唯一开发入口与历史目录

当前工作区的活动仓库是 `oh-my-patent/`，项目名称为 `oh-my-word` / `word-skills`。同级 `oh-my-technology/` 是早期 0.1.0 孵化目录，历史内容归档到同级 `.archive/oh-my-technology-0.1.0/`；原位置只保留迁移说明，不保留可导入的 `word_skills` 包或同名发行元数据。

在活动仓库根目录使用项目解释器，避免全局 Python 和历史目录改变模块解析：

```powershell
.\.venv\Scripts\python.exe -m word_skills --help
.\.venv\Scripts\python.exe -c "import word_skills; print(word_skills.__file__, word_skills.__version__)"
```

第二条命令应显示当前仓库中的 `word_skills` 路径。历史目录的源码、环境和产物保留供查阅；若需要独立运行历史版本，请使用隔离环境，不要把归档路径加入活动环境的 `PYTHONPATH`，也不要在活动环境安装归档中的同名包。

## 开始工作前

在开发工作区记录以下三项身份：

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote --symref origin HEAD
```

已有工作区以 GitHub 默认分支及当前分支的 upstream 为准，不假设默认分支名为 `main`。如果工作区没有 Git 元数据，先确认活动仓库位置，再建立检出；不要在历史归档中初始化新的活动仓库。已有改动应保留并逐项审阅；不要用远端提交号代替工作树身份。

## 发布前

发布验证必须从明确的提交创建干净检出，并记录：

- 开发工作区的提交、工作树状态和未提交文件；
- 发布检出的提交、远端分支指向和工作树状态；
- 两个目录的用途，以及哪些证据只适用于其中一个目录。

本地代码清单用 `python tools/check_code_manifest.py` 校验。首次用 `--refresh --include <相对路径>` 创建清单，后续用 `--refresh` 更新哈希；新增文件必须显式用 `--include` 纳入。完整依赖验收用 `python tools/check_full_dependencies.py`，它通过 pytest 运行全部测试并记录解释器、依赖版本、测试总数与结果，出现 skip、xfail 或 xpass 均失败。
