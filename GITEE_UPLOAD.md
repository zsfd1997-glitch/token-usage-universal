# Gitee Upload Guide

这份目录已经是一个可独立分发的 `token-usage-universal` 项目根目录，可以直接拿去上传到 `Gitee`。

## 当前状态

- 这份包不依赖原来的 `~/.codex/skills` 目录结构。
- 目录里已经包含：
  - `README.md`
  - `SKILL.md`
  - `docs/INSTALL.md`
  - `docs/ARCHITECTURE.md`
  - `docs/releases/v0.2.0.md`
  - `scripts/` 运行时代码与测试
- 当前说明已覆盖 `macOS` 和 `Windows`：
  - `README.md`
  - `docs/INSTALL.md`
  - `SKILL.md`
  里面都已经写了 Windows 路径、`PowerShell` 示例、`%APPDATA% / %USERPROFILE%` 环境变量写法，以及 Claude 的 macOS / Windows 真源路径说明。

## 最推荐的上传方式

### 方式 1：网页上传解压后的内容

如果您只是想把代码放到 Gitee：

1. 在 Gitee 新建一个空仓库。
2. 解压当前 zip 包。
3. 把解压后的 `token-usage-universal` 目录内容上传到仓库根目录。

### 方式 2：本地 git 推送到 Gitee

如果您要保留提交历史从现在重新开始：

```bash
cd token-usage-universal
git init
git add .
git commit -m "Initial import for Gitee"
git branch -M main
git remote add origin https://gitee.com/<您的账号>/<仓库名>.git
git push -u origin main
```

## 给 Gitee 的小提醒

- 这个包本身没有绑定 `.git`，适合直接作为新仓库导入。
- `README.md` 里目前还保留了 GitHub 的徽章和上游仓库地址。
- 如果您想把它变成纯 Gitee 版本，上传后建议顺手改这两类信息：
  - GitHub Actions 徽章
  - GitHub 仓库链接

## 跨平台说明

这份包已经考虑 `macOS` 和 `Windows` 用户：

- `Windows` 用户可以直接参考 `README.md` 和 `docs/INSTALL.md` 里的 `PowerShell` 示例。
- `macOS` 用户可以直接用 `bash/zsh` 示例。
- 代码里已经兼容：
  - Windows 风格路径
  - `%APPDATA% / %USERPROFILE%` 占位展开
  - Claude Windows 默认真源路径
  - macOS Claude `local-agent-mode-sessions` 路径

## 建议您上传后优先检查

```bash
python3 scripts/token_usage.py --help
python3 -m unittest discover -s scripts -p 'test_*.py'
```

如果这两个命令正常，说明这份独立项目目录基本就是可用状态。
