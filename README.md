# Token Usage Universal

[![CI](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml/badge.svg)](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml)

**一站式本地 Token 使用监控工具**  
把散落在本机各个 AI 客户端、CLI 工具和 API 日志中的 token 消耗记录，自动汇总成清晰、直观的本地面板。

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
- **额外支持**：自带自然语言触发层（Codex skill 包装）

可以单独使用它，也可以把它集成到自己的 AI 工作流、skill 或 launcher 中。

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

### 用自然语言触发

把仓库里的 [SKILL.md](/Users/guokeyu/AI/codex/token-usage-universal/SKILL.md) 挂进 Codex skill 体系后，用户不需要记命令，直接说下面这些话就行：

- `token`
- `用量`
- `帮我看今天 token 用量`
- `帮我按模型看看今天哪个最消耗 token`
- `为什么 Claude 没统计到`

## 你会得到什么

- 本地优先，不依赖云端账单页
- `exact-first`，没有真源就明确说没有
- 可以按来源、项目、模型、会话拆分
- 可以诊断“为什么没统计到”
- 可以导出证据包，方便交接和留档

## GitHub 交付契约

这个仓库上传到 GitHub 给别人用时，默认交互契约以仓库根目录的 [SKILL.md](/Users/guokeyu/AI/codex/token-usage-universal/SKILL.md) 为准。

这意味着：

- 不依赖 `~/.codex/skills/...` 里的本机覆盖文件
- 不依赖某台机器上的全局提示词或临时记忆
- 别人 clone 仓库后，随仓库一起拿到同一套触发词和输出协议

当前约定已经随仓库固化：

- 短触发词 `token / 用量 / 消耗量 / 使用量 / 消耗` 默认都视为“先看今天总览”
- 默认成品不是一句话摘要，而是 `ascii-hifi` 终端面板
- 只要底层 CLI 已返回 `ascii-hifi` 面板，聊天输出就应先原样贴面板，再补 1 到 3 句高信号结论

如果后面有人改了这套契约，仓库内测试会直接报错，避免 GitHub 版和某台开发机的私有配置漂移。

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

如果本地没有 `Windows/macOS` host，也可以直接走 GitHub 托管 runner：

- workflow: [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)
- 行为：在 `windows-latest` 和 `macos-latest` 上分别跑全量单测、导出 release evidence bundle，并上传 artifact
- 本地触发脚本: [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)

## Coverage

当前覆盖面分成五类：

### Native Clients

- `codex`
- `claude-code`
- `claude-desktop`
- `opencode`
- `minimax-agent`

### Coding CLI

- `qwen-code-cli`
- `kimi-cli`
- `gemini-cli`

### Desktop Clients

- `kimi-desktop`
- `glm-desktop`
- `qwen-desktop`
- `deepseek-desktop`
- `doubao-desktop`
- `qianfan-desktop`
- `yuanbao-desktop`
- `perplexity-desktop`
- `stepfun-desktop`
- `sensenova-desktop`
- `baichuan-desktop`
- `siliconflow-desktop`
- `spark-desktop`
- `chatgpt-desktop`
- `gemini-desktop`
- `grok-desktop`
- `mistral-desktop`

### Provider / API Families

- `openai-api`
- `anthropic-api`
- `google-gemini-api`
- `moonshot-kimi-api`
- `zhipu-glm-api`
- `qwen-api`
- `deepseek-api`
- `minimax-api`
- `xai-grok-api`
- `cohere-api`
- `mistral-api`
- `perplexity-api`
- `openrouter-api`
- `togetherai-api`
- `fireworks-api`
- `azure-openai-api`
- `baidu-qianfan-api`
- `tencent-hunyuan-api`
- `stepfun-api`
- `doubao-api`
- `sensenova-api`
- `baichuan-api`
- `siliconflow-api`
- `spark-api`

### Fallback and Ingress

- `generic-openai-compatible`
- `ingress companion`

`generic-openai-compatible` 保留给手动 diagnose / 补漏，不再默认参与总览，避免和已拆分的 provider family 重复计数。

Top20 执行主线文档：

- [Top20 Execution Plan](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_EXECUTION_PLAN.md)
- [Top20 Surface Matrix](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_SURFACE_MATRIX.md)
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
| 旧布局 / exact JSON | 是 | `timing.json` 或其他带 `total_tokens + executor_end/grader_end` 的 JSON | `~/Library/Application Support/Claude/local-agent-mode-sessions/**` | `%APPDATA%\Claude\local-agent-mode-sessions\**` | skill 会直接统计 total token |
| 新布局 / 只有 session-config | 否，先 diagnose | `.claude.json`、`cowork_settings.json`、`manifest.json` | `~/Library/Application Support/Claude/local-agent-mode-sessions/**` | `%APPDATA%\Claude\local-agent-mode-sessions\**` | 说明本地目录存在，但当前没有 token 真源 |
| transcript only | 否，先 diagnose | `~/.claude/transcripts/*.jsonl` | `~/.claude/transcripts` | `%USERPROFILE%\.claude\transcripts` | transcript 是文本，不含 exact token 字段 |

## 环境变量

| Variable | Purpose |
|---|---|
| `TOKEN_USAGE_CODEX_ROOT` | 覆写 Codex session 根目录 |
| `TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT` | 覆写 Claude transcript 目录 |
| `TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT` | 覆写 Claude local-agent-mode-sessions 目录 |
| `TOKEN_USAGE_CLAUDE_DESKTOP_ROOT` | 覆写 Claude Desktop app-data 目录 |
| `TOKEN_USAGE_MINIMAX_AGENT_ROOT` | 覆写 MiniMax Agent 桌面端数据目录 |
| `TOKEN_USAGE_KIMI_DESKTOP_ROOT` | 覆写 Kimi Desktop app-data 目录 |
| `TOKEN_USAGE_GLM_DESKTOP_ROOT` | 覆写 GLM Desktop app-data 目录 |
| `TOKEN_USAGE_QWEN_DESKTOP_ROOT` | 覆写 Qwen / DashScope app-data 目录 |
| `TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT` | 覆写 DeepSeek Desktop app-data 目录 |
| `TOKEN_USAGE_DOUBAO_DESKTOP_ROOT` | 覆写 Doubao Desktop app-data 目录 |
| `TOKEN_USAGE_QIANFAN_DESKTOP_ROOT` | 覆写 Qianfan / 文心 / 文小言 app-data 目录 |
| `TOKEN_USAGE_YUANBAO_DESKTOP_ROOT` | 覆写 Yuanbao / Hunyuan app-data 目录 |
| `TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT` | 覆写 Perplexity Desktop app-data 目录 |
| `TOKEN_USAGE_STEPFUN_DESKTOP_ROOT` | 覆写 StepFun Desktop app-data 目录 |
| `TOKEN_USAGE_SENSENOVA_DESKTOP_ROOT` | 覆写 SenseNova Desktop app-data 目录 |
| `TOKEN_USAGE_BAICHUAN_DESKTOP_ROOT` | 覆写 Baichuan Desktop app-data 目录 |
| `TOKEN_USAGE_SILICONFLOW_DESKTOP_ROOT` | 覆写 SiliconFlow Desktop app-data 目录 |
| `TOKEN_USAGE_SPARK_DESKTOP_ROOT` | 覆写 Spark / Xinghuo Desktop app-data 目录 |
| `TOKEN_USAGE_CHATGPT_DESKTOP_ROOT` | 覆写 ChatGPT Desktop app-data 目录 |
| `TOKEN_USAGE_GEMINI_DESKTOP_ROOT` | 覆写 Gemini Desktop app-data 目录 |
| `TOKEN_USAGE_GROK_DESKTOP_ROOT` | 覆写 Grok Desktop app-data 目录 |
| `TOKEN_USAGE_MISTRAL_DESKTOP_ROOT` | 覆写 Mistral / Le Chat Desktop app-data 目录 |
| `TOKEN_USAGE_QWEN_CODE_ROOT` | 覆写 Qwen Code CLI runtime root |
| `TOKEN_USAGE_KIMI_CLI_ROOT` | 覆写 Kimi CLI share root |
| `TOKEN_USAGE_GEMINI_CLI_ROOT` | 覆写 Gemini CLI runtime root |
| `TOKEN_USAGE_OPENCODE_BIN` | 覆写 OpenCode CLI 可执行文件路径 |
| `TOKEN_USAGE_OPENCODE_ROOTS` | 覆写 OpenCode 本地 roots 列表 |
| `TOKEN_USAGE_GENERIC_LOG_GLOBS` | 配置兼容 API exact log 的逗号分隔 glob |
| `TOKEN_USAGE_DISCOVERY_ROOTS` | 覆写兼容 API 日志自动发现根目录 |
| `TOKEN_USAGE_CACHE_ROOT` | 覆写本地增量缓存目录 |

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

如果想先理解结构和后续怎么维护，也可以看：

- [Architecture](./docs/ARCHITECTURE.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

如果想从当前本机 skill 目录导出一个干净的 GitHub 发布目录，可以运行：

```bash
python3 scripts/build_release.py --output-dir /path/to/token-usage-universal --validate --force
```
