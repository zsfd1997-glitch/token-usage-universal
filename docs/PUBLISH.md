# 发布说明

## 目标

把当前仓库整理成一个适合直接推到 GitHub 的独立 CLI / skill runtime 项目目录。

## 方式一：直接把当前目录作为仓库根

如果您就在仓库根目录操作：

```bash
cd /path/to/token-usage-universal
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
  --zip-path ./dist/token-usage-universal-windows.zip \
  --zip-root-name token-usage-universal \
  --validate \
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
- `python3 scripts/token_usage.py release-gate --format json`
- `python3 scripts/token_usage.py release-gate --format json --output-dir /tmp/token-usage-universal-evidence`

说明：

- `build_release.py --validate` 会先跑全量单测，再跑一次 `release-gate`。
- `--zip-path` 会额外产出标准 ZIP；这是普通 Windows 资源管理器能直接解压的格式，不是 `tar.gz`。
- 当前导出会自动排除 `.git / .claude / .superchain / 输出 / dist / AGENTS_CHANGELOG.md / GITEE_UPLOAD.md / examples/vm-testing/output` 这类本地工作痕迹。
- `release-gate` 现在会实跑默认 report 的重复计数 probe，并验证所有 root-aware source 的 `Windows + macOS + Linux` 默认根路径矩阵。
- `release-gate --output-dir ...` 可以把当前机器的 `health / sources / targets / report / diagnose / gate` 一次性落盘；配合 `--baseline <prev_bundle_dir>` 还能额外产出 `diff.json`，适合做趋势化交接证据。
- 如果本地没有 `Windows/macOS/Linux` host，可直接使用 [hostless-evidence.yml](../.github/workflows/hostless-evidence.yml) 在 GitHub-hosted runners 上导出三平台 evidence artifact。
- 如果您已经把当前分支 push 到 GitHub，可直接运行 [run-hostless-evidence.sh](../examples/vm-testing/run-hostless-evidence.sh) 自动触发 workflow、等待完成并把 artifact 拉回本地。
- 真实多机 E2E 与大样本重复计数实测仍建议在正式对外发布前补跑。

## Task Master 说明

`Task Master` 不是发布门槛，也不是运行时依赖。

如果您后续想把需求文档拆成任务，它可以作为可选规划工具；如果完全不使用它，这个 skill 仍然可以正常发布和使用。
