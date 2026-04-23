---
team: 用户流量策略科
type: tool
name: token-usage-universal
contributor: 郭珂宇
created: 2026-03-25
version: 1.0
status: 已整理
tags: [token使用监控, 本地优先, exact-first, 多来源适配, 跨平台, 中文版, opencode, trae]
usage_count: 0
effect: 把散落在本机各 AI 客户端、CLI 工具和 API 日志中的 token 消耗，自动汇总成可直接决策的本地面板
---

# Token Usage Universal

![CI](./docs/images/ci-badge.svg)

## 简介

一站式本地 token 使用监控工具。把散落在本机各个 AI 客户端、CLI 工具和 API 日志中的 token 消耗记录，自动汇总成清晰、直观的本地面板。不依赖云端账单页，exact-first，没有真源就明确说没有。

## 用途

- 面向人类阅读、复盘对齐与成本评审讨论。
- 适用于"今天 token 用了多少 / 哪个模型最费 / 为什么某个客户端没统计到"等日常查询、趋势复盘和来源排障场景。
- 作为可复用工具资产沉淀，便于后续统一维护和接入其他 agent / launcher。

## 使用方法

1. 阅读当前目录下的 `README.md`，快速理解本工具的定位和上手顺序。
2. 运行 `python3 scripts/token_usage.py health` 检查本机哪些数据源已就绪。
3. 运行 `python3 scripts/token_usage.py report --today` 查看今日使用总览。
4. 如需自然语言触发，可参考 `SKILL.md` 中的触发词配置（可选）。

## 适用版本

- 当前版本：`中文版 + 独立 Python CLI`
- 核心入口：`scripts/token_usage.py`
- 自然语言触发描述：`SKILL.md`（可选，适用于支持系统提示词的 AI 工具）
- 补充说明：在日常查询或排障前先跑 `python3 scripts/token_usage.py health` 确认本机哪些来源已 ready。
- 补充说明：不依赖任何 skills 目录或特定 AI 客户端框架，直接运行 Python 脚本即可使用。
- 补充说明：如需接入其他 agent / launcher，直接调用 `scripts/token_usage.py` 即可。

## 效果

- 通过标准化目录与说明文档，降低查找和复用成本。
- 让 token 使用监控从"每次手动查"升级为"有说明、有入口、可维护、可诊断"的工具资产。

## 使用记录

| 日期 | 使用者 | 场景 | 效果 |
|------|--------|------|------|
|      |        |      |      |

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0 | 2026-03-25 | 初始版本，覆盖 codex / claude-code / claude-desktop / opencode / minimax-agent / qwen-code-cli / kimi-cli / gemini-cli + chromium-desktop-family + provider-api-family + generic |

---

## 核心价值

再也不用在不同客户端之间来回切换、手动统计。  
这个工具帮你快速回答以下关键问题：

- 今天、本周或本月一共消耗了多少 token
- 哪个模型、哪个项目或哪个来源最费 token
- 哪些消耗来自真实请求，哪些是缓存命中
- 为什么某些客户端明明在使用，却没有出现在统计里

它完全在本地运行，不依赖任何云端账单页面，专注于把机器上已有的真实日志、缓存和会话数据整理成统一、可验证的结果。

## 这是一个什么工具

- **核心**：独立、轻量的 Python 命令行工具
- **入口脚本**：`scripts/token_usage.py`
- **额外支持**：附带自然语言触发描述（`SKILL.md`），可选集成到支持系统提示词的 AI 工具中

可以单独使用它，也可以把它集成到自己的 AI 工作流或 launcher 中。

## 主要功能

- 查看今天、本周、最近 30 天或任意时段的 token 用量
- 按模型、项目、来源、会话维度进行分组统计
- 显示缓存命中情况与真实消耗对比
- 智能诊断：快速定位某个客户端或来源未被统计的原因
- 生成清晰的终端面板，支持趋势图和日历视图
- 为团队交接或个人复盘提供可追溯的 usage 报告

## 快速开始

第一次上手，先跑下面这几步：

```bash
git clone https://github.com/zsfd1997-glitch/token-usage-universal.git
cd token-usage-universal

# 第一步：检查本机支持情况
python3 scripts/token_usage.py health

# 第二步：查看今天使用概览
python3 scripts/token_usage.py report --today

# 第三步：如果某个来源没统计到，直接诊断
python3 scripts/token_usage.py diagnose --source codex --today
```

`health` 用来看本机哪些来源已经 ready。  
`report --today` 用来看今天总览。  
`diagnose` 用来查“为什么没统计到”。  

## OpenCode CLI 用户最短路径（对话式一键装）

**不想跑命令？直接对话装。** 把下面这段贴到 opencode CLI 的首条消息里回车，AI 会自动找仓库、跑安装脚本、告诉你什么时候可以用：

```
请帮我把 token-usage-universal 这个 skill 装进 opencode CLI。按下面四步操作，不要反问，直接跑：

步骤 1：在本机找仓库路径。macOS / Linux 跑：
    find "$HOME" -maxdepth 6 -type d -name token-usage-universal -not -path "*/.*" 2>/dev/null | head -1
Windows PowerShell 跑：
    Get-ChildItem -Path $HOME -Recurse -Depth 6 -Directory -Filter token-usage-universal -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName

步骤 2：拿到路径（记为 $REPO），跑安装脚本：
    python3 "$REPO/scripts/install_to_opencode.py"
Windows 用 `python` 代替 `python3`。

步骤 3：原样贴出安装脚本的输出到我的对话里。

步骤 4：最后告诉我：『重启一次 opencode CLI，下次说 token 或 用量 就会自动出面板』。

如果步骤 1 找不到仓库，先提示我告诉你仓库在哪，不要猜。
```

贴一次就好。第一次装完以后，重启 opencode CLI，后面每次对话说 `token` / `用量` / `今天 token 用了多少` 都会直接触发面板，不用再贴任何指令。

这段提示词也可以命令行生成（不用手动从 README 复制）：

```bash
python3 scripts/install_to_opencode.py --print-prompt
```

### 一条命令装（不走对话）

如果你更习惯直接跑命令：

```bash
python3 scripts/install_to_opencode.py
```

脚本会：
- 自动探测 opencode skills 目录（macOS/Linux: `~/.config/opencode/skills/`；Windows: `%APPDATA%\opencode\skills\`）
- 把仓库软链进去（Windows 无开发者模式时自动降级到目录联接或完整拷贝）
- 验证 SKILL.md 可达，打印下一步操作

装完**重启一次 opencode CLI**，再对话里说 `token`、`用量`、`今天 token 用了多少` 就会直接出面板。

卸载 / 换位置：
```bash
python3 scripts/install_to_opencode.py --dry-run    # 只看计划不动手
python3 scripts/install_to_opencode.py --uninstall  # 拆掉软链
python3 scripts/install_to_opencode.py --target DIR # 指定 skills 目录
```

## OpenCode / Trae 用户快速上手

如果你在使用 **OpenCode** 或 **Trae** 等内网/私有部署 AI 工具，通常不需要配置 skills 目录，直接按以下步骤找到你的数据源：

### 第一步：检查工具是否被识别

```bash
python3 scripts/token_usage.py health
```

输出中每个来源会标注 `ready` / `no_data` / `not_found`。如果 `opencode` 或你的工具显示 `not_found`，继续往下看。

### 第二步：OpenCode 数据源定位

OpenCode 的会话数据默认存放在：

| 平台 | 默认路径 |
|------|----------|
| macOS/Linux | `~/.config/opencode/storage/` 或 `~/.local/share/opencode/storage/` |
| Windows | `%APPDATA%\opencode\storage\` 或 `%LOCALAPPDATA%\opencode\storage\` |

子目录结构：
- `storage/session/` — 会话列表（含模型、时间戳）
- `storage/message/` — 消息明细（含 token 消耗字段）

如果默认路径不对，用环境变量覆盖：

```bash
export TOKEN_USAGE_OPENCODE_ROOTS="$HOME/.config/opencode,$HOME/.local/share/opencode"
python3 scripts/token_usage.py health
```

### 第三步：Trae 及其他内网工具的数据源

对于 Trae 或其他支持 OpenAI-compatible / Anthropic-compatible API 的内网 AI 工具，推荐使用 **ingress companion** 模式——在本地启动一个透明代理，自动把 exact token 数据落盘：

```bash
# 查看内置 profile 列表
python3 scripts/token_usage.py ingress profiles

# 启动本地代理（以自定义内网 API 为例）
python3 scripts/token_usage.py ingress serve \
  --provider generic \
  --upstream-base-url http://your-internal-api-host/v1 \
  --protocol openai \
  --project-path "$PWD"
```

启动后，把你的 IDE / 工具的 API base URL 改为代理输出的本地地址（如 `http://127.0.0.1:8787/v1`），之后 token 数据会自动落盘并被 `report` 和 `diagnose` 命令读取。

### 第四步：确认数据已进来

```bash
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py report --today
```

如果某个来源仍未统计到，运行诊断：

```bash
python3 scripts/token_usage.py diagnose --source opencode --today
```

---

## 常见用法

### 看今天总览

```bash
python3 scripts/token_usage.py report --today
```

会直接看到：

- 总 token
- 去缓存后 token
- 当前会话
- 按模型
- 按项目
- 最近趋势
- 月历热力图

### 看最近趋势

```bash
python3 scripts/token_usage.py report --trend 7d
python3 scripts/token_usage.py report --calendar month
```

### 查某个来源为什么没统计到

```bash
python3 scripts/token_usage.py diagnose --source claude-desktop --today
python3 scripts/token_usage.py diagnose --source minimax-agent --today
```

### 只看当前会话

```bash
python3 scripts/token_usage.py report --current-session
```

### 用自然语言触发（可选）

如果你的 AI 工具支持系统提示词或自定义指令（如 Claude Code、Cursor、Continue 等），可以把 `SKILL.md` 的内容作为系统提示词注入，然后直接说下面这些话触发：

- `token`
- `用量`
- `帮我看今天 token 用量`
- `帮我按模型看看今天哪个最消耗 token`
- `为什么 Claude 没统计到`

> **注意**：这一步是可选的。不配置系统提示词也可以直接用 CLI 命令完成所有操作。

## 你会得到什么

- 本地优先，不依赖云端账单页
- `exact-first`，没有真源就明确说没有
- 可以按来源、项目、模型、会话拆分
- 可以诊断“为什么没统计到”
- 可以导出证据包，方便交接和留档

## 使用契约

这个工具完全独立运行，不依赖任何特定 AI 客户端的私有配置目录：

- 不依赖 `~/.codex/skills/...` 或任何 skills 目录
- 不依赖某台机器上的全局提示词或临时记忆
- clone 仓库后，直接运行 Python 脚本即可使用

`SKILL.md` 是可选的自然语言接口描述文件，仅供有需要的用户集成到支持系统提示词的 AI 工具中。输出行为约定：

- 短查询（`token / 用量 / 消耗量 / 使用量`）默认先看今天总览
- 默认输出为 `ascii-hifi` 终端面板，附 1 到 3 句高信号结论
- 详细触发映射见 [skill-routing.md](./references/skill-routing.md)，输出协议见 [skill-output-contract.md](./references/skill-output-contract.md)

## Start Here

如果只想开始用，先记住这几条：

```bash
python3 scripts/token_usage.py health
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py diagnose --source codex --today
python3 scripts/token_usage.py release-gate --format json
```

- `health`：看本机哪些来源已经 ready
- `report --today`：看今天总览
- `sources`：看所有来源当前状态
- `diagnose`：查为什么没统计到
- `release-gate`：看当前仓库是否达到发布门槛

如果是通过别的 agent / skill / launcher 调用，直接执行这个脚本即可：

```bash
python3 /absolute/path/to/token-usage-universal/scripts/token_usage.py health
```

如果要在真实机器上留存可交接证据，可以直接导出证据包：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --output-dir /tmp/token-usage-universal-evidence
```

证据包会包含：

- `release_gate.json`
- `health.json`
- `sources.json`
- `targets.json`
- `report_today.json`
- `report_recent_30d.json`
- `diagnose/*.json`
- `SUMMARY.md`

如果要和上一次证据包做趋势对比，可以再加 `--baseline`：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --baseline /path/to/prev-bundle \
  --output-dir /tmp/token-usage-universal-evidence
```

这时会额外产出：

- `diff.json`
- `release_gate.json` 里的 `baseline.diff`
- `SUMMARY.md` 顶部的状态对比摘要

如果本地没有 `Windows/macOS/Linux` host，也可以直接走 GitHub 托管 runner：

- workflow: [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)
- 行为：在 `ubuntu-latest`、`windows-latest` 和 `macos-latest` 上分别跑全量单测、导出 release evidence bundle，并上传 artifact
- 本地触发脚本: [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)

## Coverage

覆盖面不再手写维护，详细 source matrix 统一看自动生成文档：

- [COVERAGE.md](./docs/COVERAGE.md)
- [Top20 Execution Plan](./docs/TOP20_EXECUTION_PLAN.md)
- [Top20 Surface Matrix](./docs/TOP20_SURFACE_MATRIX.md)

这里保留一条总规则：

- `generic-openai-compatible` 只做 fallback / diagnose 补漏，默认不参与总览，避免和已拆分 provider family 重复计数。

配套文档：

- [Simulated Machine Testing](/Users/guokeyu/AI/codex/token-usage-universal/docs/SIMULATED_MACHINE_TESTING.md)
- [VM Runbook](/Users/guokeyu/AI/codex/token-usage-universal/docs/VM_RUNBOOK.md)

## Source Notes

如果只想理解“这个项目怎么判断某个来源能不能被记进去”，先看这几个重点：

- `codex`
  - 默认读取 `~/.codex/sessions/**/*.jsonl`
  - 支持 env override：`TOKEN_USAGE_CODEX_ROOT`
- `claude-code`
  - transcript 默认路径：`~/.claude/transcripts`
  - project exact usage 默认路径：`~/.claude/projects/**/*.jsonl`
  - exact total 默认根目录：`~/Library/Application Support/Claude/local-agent-mode-sessions`
  - 支持 env override：`TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT`、`TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT`
- `claude-desktop`
  - 原生解析桌面端 `Chromium Cache_Data / IndexedDB` 痕迹
  - 当前 exact 依赖 Claude Desktop 是否把 token-bearing API 响应缓存到本地
  - 支持 env override：`TOKEN_USAGE_CLAUDE_DESKTOP_ROOT`
- `opencode`
  - 优先直读本地 `storage/session` + `storage/message`
  - 官方 `opencode session list` + `opencode export [sessionID]` 仍保留为 fallback
  - 支持 env override：`TOKEN_USAGE_OPENCODE_BIN`、`TOKEN_USAGE_OPENCODE_ROOTS`
- `qwen-code-cli`
  - 原生读取官方 project-scoped session JSONL
  - 默认优先扫 `~/.qwen/projects/*/chats/*.jsonl`
  - override：`TOKEN_USAGE_QWEN_CODE_ROOT`
- `kimi-cli`
  - 原生读取官方 `~/.kimi/sessions/*/*/wire.jsonl`
  - exact token 来自 `StatusUpdate.token_usage`
  - override：`TOKEN_USAGE_KIMI_CLI_ROOT`
- `gemini-cli`
  - 原生读取官方 `~/.gemini/tmp/*/chats/session-*.json`
  - exact token 来自 assistant message 的 `tokens`
  - override：`TOKEN_USAGE_GEMINI_CLI_ROOT`
- `minimax-agent`
  - 原生解析桌面端 `Chromium Cache_Data`
  - exact 依赖客户端是否把 token-bearing 响应缓存到本地
  - override：`TOKEN_USAGE_MINIMAX_AGENT_ROOT`
- `desktop-*`
  - 已拆成独立 `source_id`
  - 统一走 `Chromium / Electron` 桌面适配框架
  - 现在会同时读取 `Cache_Data / IndexedDB / Local Storage`
- `generic-openai-compatible`
  - 兼容 OpenAI-compatible / Anthropic-compatible exact usage 结构
  - 可自动扫描常见目录，也可通过 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式配置
- `ingress companion`
  - 面向 `IDE / 内网 launcher / 自定义 base_url`
  - 会把 exact usage 响应落成 JSONL，供 provider family 和 generic adapter 自动发现

统一规则：

- 每个 provider family 都是独立 `source_id`
- 它们共用同一套 exact log 发现机制：`TOKEN_USAGE_GENERIC_LOG_GLOBS` + `TOKEN_USAGE_DISCOVERY_ROOTS`
- 解析时按 `provider` 字段优先，其次按 `model` 名回退识别
- 拿不到 exact 时，会明确说明是“没 parser”还是“当前缓存里确实没有 token 真源”
- report 会把“已观测到客户端/模型痕迹，但当前没有 exact token payload”的来源单列出来

## Claude Code 真源矩阵

| 布局版本 | 是否可 exact | 典型文件 | macOS 默认位置 | Windows 默认位置 | 说明 |
|---|---|---|---|---|---|
| project JSONL / assistant usage | 是 | `session-*.jsonl` 里的 `message.usage` | `~/.claude/projects/**` | `%USERPROFILE%\\.claude\\projects\\**` | 新布局优先走这里，可恢复 input / cache / output / total token |
| 旧布局 / exact JSON | 是 | `timing.json` 或其他带 `total_tokens + executor_end/grader_end` 的 JSON | `~/Library/Application Support/Claude/local-agent-mode-sessions/**` | `%APPDATA%\Claude\local-agent-mode-sessions\**` | 工具会直接统计 total token |
| 新布局 / 只有 session-config | 否，先 diagnose | `.claude.json`、`cowork_settings.json`、`manifest.json` | `~/Library/Application Support/Claude/local-agent-mode-sessions/**` | `%APPDATA%\Claude\local-agent-mode-sessions\**` | 说明本地目录存在，但当前没有 token 真源 |
| transcript only | 否，先 diagnose | `~/.claude/transcripts/*.jsonl` | `~/.claude/transcripts` | `%USERPROFILE%\.claude\transcripts` | transcript 是文本，不含 exact token 字段 |

## 环境变量

完整环境变量表不再手写维护，统一看自动生成文档：

- [ENV.md](./docs/ENV.md)

机器相关的默认路径不要看文档猜，直接运行：

```bash
python3 scripts/token_usage.py health --format json
```

它会返回当前机器解析后的默认值、是否已配置 override，以及下一步建议。

示例：

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/work/codex-sessions"
export TOKEN_USAGE_OPENCODE_BIN="$HOME/.local/bin/opencode"
export TOKEN_USAGE_OPENCODE_ROOTS="$HOME/.config/opencode,$HOME/.local/share/opencode"
export TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="$HOME/Library/Application Support/Claude"
export TOKEN_USAGE_MINIMAX_AGENT_ROOT="$HOME/Library/Application Support/MiniMax Agent"
export TOKEN_USAGE_KIMI_DESKTOP_ROOT="$HOME/Library/Application Support/Kimi"
export TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT="$HOME/Library/Application Support/DeepSeek"
export TOKEN_USAGE_QIANFAN_DESKTOP_ROOT="$HOME/Library/Application Support/Wenxiaoyan"
export TOKEN_USAGE_YUANBAO_DESKTOP_ROOT="$HOME/Library/Application Support/Yuanbao"
export TOKEN_USAGE_QWEN_CODE_ROOT="$HOME/.qwen"
export TOKEN_USAGE_KIMI_CLI_ROOT="$HOME/.kimi"
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/openai/*.jsonl,$HOME/logs/openai/*.json"
export TOKEN_USAGE_DISCOVERY_ROOTS="$HOME/Library/Application Support,$HOME/.local/share"
python3 scripts/token_usage.py health
```

Windows PowerShell 常见写法：

```powershell
$env:TOKEN_USAGE_CODEX_ROOT="%USERPROFILE%\.codex\sessions"
$env:TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="%APPDATA%\Claude\local-agent-mode-sessions"
$env:TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="%APPDATA%\Claude"
$env:TOKEN_USAGE_MINIMAX_AGENT_ROOT="%APPDATA%\MiniMax Agent"
$env:TOKEN_USAGE_KIMI_DESKTOP_ROOT="%APPDATA%\Kimi"
$env:TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT="%APPDATA%\DeepSeek"
$env:TOKEN_USAGE_QIANFAN_DESKTOP_ROOT="%APPDATA%\Wenxiaoyan"
$env:TOKEN_USAGE_YUANBAO_DESKTOP_ROOT="%APPDATA%\Yuanbao"
$env:TOKEN_USAGE_QWEN_CODE_ROOT="%USERPROFILE%\.qwen"
$env:TOKEN_USAGE_KIMI_CLI_ROOT="%USERPROFILE%\.kimi"
$env:TOKEN_USAGE_OPENCODE_BIN="%USERPROFILE%\.local\bin\opencode.exe"
$env:TOKEN_USAGE_OPENCODE_ROOTS="%USERPROFILE%\.config\opencode,%USERPROFILE%\.local\share\opencode"
$env:TOKEN_USAGE_GENERIC_LOG_GLOBS="%USERPROFILE%\logs\*.jsonl"
$env:TOKEN_USAGE_DISCOVERY_ROOTS="%APPDATA%,%LOCALAPPDATA%"
python .\scripts\token_usage.py health
```

## IDE / 内网 Launcher 接入

如果某个客户端支持自定义 `base_url`，优先不要硬逆向它的私有日志，而是先接本地 `ingress companion`。

先看内置 profile：

```bash
python3 scripts/token_usage.py ingress profiles
```

然后直接生成 IDE / CLI bootstrap：

```bash
python3 scripts/token_usage.py ingress bootstrap \
  --profile deepseek \
  --editor vscode
```

上面的命令会打印：

- 本地代理地址，例如 `http://127.0.0.1:8787/v1`
- Continue 的 `VS Code / JetBrains` 配置片段
- CLI shell env 示例
- companion 的 JSONL log 根目录

如果要手动控制 provider / base URL，也可以继续直接用 `ingress config`：

```bash
python3 scripts/token_usage.py ingress config \
  --provider deepseek \
  --upstream-base-url https://api.deepseek.com \
  --protocol openai
```

确认地址后，再启动本地 companion：

```bash
python3 scripts/token_usage.py ingress serve \
  --provider deepseek \
  --upstream-base-url https://api.deepseek.com \
  --protocol openai \
  --project-path "$PWD"
```

这条链路适合：

- IDE 插件
- 企业内网 launcher
- 任何支持 OpenAI-compatible / Anthropic-compatible `base_url` 的 CLI

对这类客户端，我们优先保证“exact usage 能进来”，再按 provider family 自动分流归因，不强依赖它们是否有公开的 skills 库。

目前已经补齐 bootstrap 的中国优先 runtime surface：

- `DeepSeek CLI / IDE`
- `Qianfan CLI / IDE`
- `Hunyuan CLI / IDE`
- `SenseNova CLI / IDE`
- `Baichuan CLI / IDE`
- `SiliconFlow CLI / IDE`
- `Spark CLI / IDE`

## 关键命令

```bash
python3 scripts/token_usage.py health
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py targets
python3 scripts/token_usage.py release-gate
python3 scripts/token_usage.py release-gate --output-dir /tmp/token-usage-universal-evidence
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
python3 scripts/token_usage.py diagnose --source claude-desktop --today
python3 scripts/token_usage.py diagnose --source kimi-desktop --today
python3 scripts/token_usage.py ingress profiles
python3 scripts/token_usage.py ingress bootstrap --profile deepseek --editor vscode
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
python3 scripts/token_usage.py release-gate --format json
```

CI 也会执行这些基础验证，见 `.github/workflows/ci.yml`。

## 仓库结构

```text
token-usage-universal/
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── SKILL.md          # 可选：自然语言触发描述，供系统提示词集成用
├── LICENSE
├── docs/
│   └── images/       # 本地图片资源（含 CI 状态徽章）
├── examples/
├── references/
├── scripts/
└── .github/workflows/ci.yml
```

## 发布到 GitHub

详见 [INSTALL.md](./docs/INSTALL.md) 和 [PUBLISH.md](./docs/PUBLISH.md)。

公开仓库地址：

- https://github.com/zsfd1997-glitch/token-usage-universal

如果想先理解结构和后续怎么维护，也可以看：

- [Architecture](./docs/ARCHITECTURE.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

如果想从当前本机 skill 目录导出一个干净的 GitHub 发布目录，可以运行：

```bash
python3 scripts/build_release.py --output-dir /path/to/token-usage-universal --validate --force
```
