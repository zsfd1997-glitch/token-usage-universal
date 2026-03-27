# 发布说明

## 目标

把当前 skill 整理成一个适合直接推到 GitHub 的仓库目录。

## 方式一：直接把当前目录作为仓库根

如果您就在 skill 根目录操作：

```bash
cd ~/.codex/skills/token-usage-universal
git init
git add .
git commit -m "Prepare token-usage-universal skill for GitHub"
```

然后：

```bash
gh repo create token-usage-universal --public --source=. --remote=origin
git push -u origin main
```

如果本机没有 `gh` 或未登录，也可以手动创建仓库后再推：

```bash
git remote add origin https://github.com/zsfd1997-glitch/token-usage-universal.git
git branch -M main
git push -u origin main
```

## 方式二：导出一个干净目录再推

```bash
python3 scripts/build_release.py \
  --output-dir /tmp/token-usage-universal-github \
  --force
```

然后：

```bash
cd /tmp/token-usage-universal-github
git init
git add .
git commit -m "Prepare token-usage-universal skill for GitHub"
git branch -M main
```

## 发布前核对

- `python3 -m unittest discover -s scripts -t . -p 'test_*.py'`
- `python3 scripts/token_usage.py --help`
- `python3 scripts/token_usage.py health --format json`
- `python3 scripts/token_usage.py sources --format json`

## Task Master 说明

`Task Master` 不是发布门槛，也不是运行时依赖。

如果您后续想把需求文档拆成任务，它可以作为可选规划工具；如果完全不使用它，这个 skill 仍然可以正常发布和使用。
