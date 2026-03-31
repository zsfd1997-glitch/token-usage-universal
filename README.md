# Token Usage Universal

[![CI](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml/badge.svg)](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml)

一个面向本地 AI 工作流的 `token usage skill`。

它回答的不是“账单页上写了什么”，而是：

- 今天到底用了多少 token
- 哪个来源 / 项目 / 模型最消耗
- 哪些 token 是缓存命中，哪些更接近真实消耗
- 为什么某个本地 AI 客户端没有被统计到

## 成品定位

- 对外成品：`Codex skill`
- 内部运行时：`Python CLI core`
- 非目标：不把 v1 包装成独立品牌 CLI 产品

`Task Master` 不是本 skill 的运行时依赖。
它最多只是可选的内部规划工具，用来把 PRD 拆成任务；即使完全不装 `Task Master`，这个 skill 也可以安装、健康检查、统计和诊断。

## 适用场景

- 查看今天或最近几天的本地 token 用量
- 对比 `codex / claude-code / generic-openai-compatible` 等来源
- 按项目、模型、会话做 usage 归因
- 诊断为什么某个来源当前没有被统计到

## 快速安装

最直接的安装方式，是把这个仓库 clone 到您的 Codex skills 目录：

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
git clone https://github.com/zsfd1997-glitch/token-usage-universal.git \
  "$CODEX_HOME/skills/token-usage-universal"
```

如果您已经在本地拿到源码目录，也可以直接复制过去：

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
cp -R ./token-usage-universal "$CODEX_HOME/skills/token-usage-universal"
```

## 快速开始

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export TOKEN_USAGE_SKILL="$CODEX_HOME/skills/token-usage-universal"

python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" sources
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --trend 7d
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --calendar month
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --current-session
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" diagnose --source codex --today
```

建议第一次先跑 `health`，它会告诉您：

- 哪些来源已经 ready
- 哪些来源还需要路径配置
- 哪些来源缺的是真源，而不是命令本身有问题

## 当前支持来源

- `codex`
  - 默认读取 `~/.codex/sessions/**/*.jsonl`
  - 支持 env override：`TOKEN_USAGE_CODEX_ROOT`
- `claude-code`
  - transcript 默认路径：`~/.claude/transcripts`
  - exact total 默认根目录：`~/Library/Application Support/Claude/local-agent-mode-sessions`（Windows 常见等价目录是 `%APPDATA%\Claude\local-agent-mode-sessions`）
  - exact 文件支持旧版 `timing.json`，也支持任何同时带 `total_tokens + executor_end/grader_end` 的 Claude JSON
  - 支持 env override：`TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT`、`TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT`
- `generic-openai-compatible`
  - 通过 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式配置 JSON / JSONL 日志 glob

## Claude Code 真源矩阵

| 布局版本 | 是否可 exact | 典型文件 | macOS 默认位置 | Windows 默认位置 | 说明 |
|---|---|---|---|---|---|
| 旧布局 / exact JSON | 是 | `timing.json` 或其他带 `total_tokens + executor_end/grader_end` 的 JSON | `~/Library/Application Support/Claude/local-agent-mode-sessions/**` | `%APPDATA%\Claude\local-agent-mode-sessions\**` | skill 会直接统计 total token |
| 新布局 / 只有 session-config | 否，先 diagnose | `.claude.json`、`cowork_settings.json`、`manifest.json` | 同上 | 同上 | 说明本地目录存在，但当前没有 token 真源 |
| transcript only | 否，先 diagnose | `~/.claude/transcripts/*.jsonl` | `~/.claude/transcripts` | `%USERPROFILE%\.claude\transcripts` | transcript 是文本，不含 exact token 字段 |

## 环境变量

| Variable | Purpose |
|---|---|
| `TOKEN_USAGE_CODEX_ROOT` | 覆写 Codex session 根目录 |
| `TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT` | 覆写 Claude transcript 目录 |
| `TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT` | 覆写 Claude local-agent-mode-sessions 目录 |
| `TOKEN_USAGE_GENERIC_LOG_GLOBS` | 配置 generic exact log 的逗号分隔 glob |

示例：

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/work/codex-sessions"
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/openai/*.jsonl,$HOME/logs/openai/*.json"
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health
```

Windows PowerShell 常见写法：

```powershell
$env:TOKEN_USAGE_CODEX_ROOT="%USERPROFILE%\.codex\sessions"
$env:TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="%APPDATA%\Claude\local-agent-mode-sessions"
$env:TOKEN_USAGE_GENERIC_LOG_GLOBS="%USERPROFILE%\logs\*.jsonl"
python "$env:CODEX_HOME\skills\token-usage-universal\scripts\token_usage.py" health
```

## 关键命令

```bash
python3 scripts/token_usage.py health
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py report --today --by day
python3 scripts/token_usage.py report --last 7d --by model
python3 scripts/token_usage.py report --trend 7d
python3 scripts/token_usage.py report --trend 30d --plain-ascii
python3 scripts/token_usage.py report --calendar month --month 2026-03
python3 scripts/token_usage.py report --current-session
python3 scripts/token_usage.py report --session 019d3d50-b44c-77a3-a817-08a4ffd4dd19
python3 scripts/token_usage.py explore
python3 scripts/token_usage.py report --today --by project
python3 scripts/token_usage.py diagnose --source claude-code --today
```

## 终端控制面能力

当前 CLI 已经覆盖 Tokdash 的核心数据面，但仍保持纯终端模式：

- `by source / model / project / session / day`
- `trend_7d / trend_30d`
- `calendar_month`
- `current_session`
- `session_detail`
- `estimated cost`

设计原则：

- token 继续 `exact-first`
- `estimated cost` 只做本地价格表估算，永远不当作账单真源
- 图形统一用 CLI 语法表达，不引入 HTML/TUI 前端

常用图形视图：

```bash
python3 scripts/token_usage.py report --trend 7d
python3 scripts/token_usage.py report --calendar month --month 2026-03
python3 scripts/token_usage.py report --today --plain-ascii
```

## 开发与验证

```bash
python3 -m unittest discover -s scripts -t . -p 'test_*.py'
python3 scripts/token_usage.py --help
python3 scripts/token_usage.py health --format json
```

CI 也会执行这些基础验证，见 `.github/workflows/ci.yml`。

## 仓库结构

```text
token-usage-universal/
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── SKILL.md
├── LICENSE
├── docs/
├── examples/
├── references/
├── scripts/
└── .github/workflows/ci.yml
```

## 发布到 GitHub

详见 [INSTALL.md](./docs/INSTALL.md) 和 [PUBLISH.md](./docs/PUBLISH.md)。

公开仓库地址：

- https://github.com/zsfd1997-glitch/token-usage-universal

如果您想先理解结构和后续怎么维护，也可以看：

- [Architecture](./docs/ARCHITECTURE.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

如果您想从当前本机 skill 目录导出一个干净的 GitHub 发布目录，可以运行：

```bash
python3 scripts/build_release.py --output-dir /path/to/token-usage-universal --force
```
