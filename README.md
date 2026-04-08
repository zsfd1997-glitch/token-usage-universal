# Token Usage Universal

[![CI](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml/badge.svg)](https://github.com/zsfd1997-glitch/token-usage-universal/actions/workflows/ci.yml)

一个面向本地 AI 工作流的 `token usage CLI / skill runtime`。

它回答的不是“账单页上写了什么”，而是：

- 今天到底用了多少 token
- 哪个来源 / 项目 / 模型最消耗
- 哪些 token 是缓存命中，哪些更接近真实消耗
- 为什么某个本地 AI 客户端没有被统计到

## 成品定位

- 对外成品：`独立 Python CLI`，可被不同 agent / skill / launcher 复用
- 兼容形态：`Codex skill` 只是可选包装层，不是唯一运行方式
- 内部运行时：`Python CLI core`

`Task Master` 不是本 skill 的运行时依赖。
它最多只是可选的内部规划工具，用来把 PRD 拆成任务；即使完全不装 `Task Master`，这个 skill 也可以安装、健康检查、统计和诊断。

## 适用场景

- 查看今天或最近几天的本地 token 用量
- 对比 `codex / claude-code / claude-desktop / minimax-agent / desktop clients / provider API logs` 等来源
- 统计经由 `MiniMax / Kimi / GLM / Qwen / OpenAI / Anthropic` 等 provider 返回的 exact usage
- 按项目、模型、会话做 usage 归因
- 诊断为什么某个本地客户端或日志来源当前没有被统计到

## 快速安装

推荐直接把仓库 clone 到任意工作目录：

```bash
git clone https://github.com/zsfd1997-glitch/token-usage-universal.git
cd token-usage-universal
```

如果您确实要把它挂进 Codex skills，也可以额外复制一份过去，但这不是必需步骤。

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

## 快速开始

默认从仓库根目录运行：

```bash
python3 scripts/token_usage.py health
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py targets
python3 scripts/token_usage.py release-gate
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py report --trend 7d
python3 scripts/token_usage.py report --calendar month
python3 scripts/token_usage.py report --current-session
python3 scripts/token_usage.py diagnose --source codex --today
```

如果您是通过别的 agent / skill / launcher 调用，只需要让对方执行这个脚本即可：

```bash
python3 /absolute/path/to/token-usage-universal/scripts/token_usage.py health
```

建议第一次先跑 `health`，它会告诉您：

- 哪些来源已经 ready
- 哪些来源还需要路径配置
- 哪些来源缺的是真源，而不是命令本身有问题

如果您在推进 Top20 主线交付，建议再跑一次：

```bash
python3 scripts/token_usage.py release-gate --format json
```

它会直接给出当前自动化门禁结果：Top20 覆盖率、中国优先覆盖率、`exact-ready` surface 覆盖率、结构性误报 ready、默认 report 的重复计数 probe，以及全部 root-aware source 的 `Windows + macOS` 路径矩阵。

如果您本地没有 `Windows/macOS` host，现在也可以直接走 GitHub 托管 runner：

- workflow: [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)
- 行为：在 `windows-latest` 和 `macos-latest` 上分别跑全量单测、导出 release evidence bundle，并上传 artifact
- 本地触发脚本: [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)

如果您要在真实机器上留存可交接证据，可以直接导出证据包：

```bash
python3 scripts/token_usage.py release-gate \
  --format json \
  --output-dir /tmp/token-usage-universal-evidence
```

它会落出：

- `release_gate.json`
- `health.json`
- `sources.json`
- `targets.json`
- `report_today.json`
- `report_recent_30d.json`
- `diagnose/*.json`
- `SUMMARY.md`

## 当前支持来源

Top20 执行主线文档：

- [Top20 Execution Plan](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_EXECUTION_PLAN.md)
- [Top20 Surface Matrix](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_SURFACE_MATRIX.md)
- [Simulated Machine Testing](/Users/guokeyu/AI/codex/token-usage-universal/docs/SIMULATED_MACHINE_TESTING.md)
- [VM Runbook](/Users/guokeyu/AI/codex/token-usage-universal/docs/VM_RUNBOOK.md)

- `native clients`
  - `codex`
  - `claude-code`
  - `claude-desktop`
  - `opencode`
  - `minimax-agent`
- `official coding CLI`
  - `qwen-code-cli`
  - `kimi-cli`
  - `gemini-cli`
- `desktop-native closed clients`
  - `kimi-desktop`
  - `glm-desktop`
  - `qwen-desktop`
  - `deepseek-desktop`
  - `doubao-desktop`
  - `qianfan-desktop`
  - `yuanbao-desktop`
  - `perplexity-desktop`
- `top provider families`
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
- `generic fallback`
  - `generic-openai-compatible`
  - 保留给手动 diagnose / 补漏，不再默认参与总览，避免和已拆分的 provider family 重复计数

- `codex`
  - 默认读取 `~/.codex/sessions/**/*.jsonl`
  - 支持 env override：`TOKEN_USAGE_CODEX_ROOT`
- `claude-code`
  - transcript 默认路径：`~/.claude/transcripts`
  - exact total 默认根目录：`~/Library/Application Support/Claude/local-agent-mode-sessions`（Windows 常见等价目录是 `%APPDATA%\Claude\local-agent-mode-sessions`）
  - exact 文件支持旧版 `timing.json`，也支持任何同时带 `total_tokens + executor_end/grader_end` 的 Claude JSON
  - 支持 env override：`TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT`、`TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT`
- `claude-desktop`
  - 原生解析桌面端 `Chromium Cache_Data / IndexedDB` 痕迹
  - 当前 exact 依赖 Claude Desktop 是否把 token-bearing API 响应缓存到本地
  - mac 默认根目录：`~/Library/Application Support/Claude`
  - Windows 常见根目录：`%APPDATA%\Claude`
  - 支持 env override：`TOKEN_USAGE_CLAUDE_DESKTOP_ROOT`
- `opencode`
  - 现在优先直读本地 `storage/session` + `storage/message` 的 assistant token JSON
  - 官方 `opencode session list` + `opencode export [sessionID]` 仍保留为 fallback
  - 本地会同时扫描 `~/.config/opencode`、`~/.local/share/opencode`、`~/.local/state/opencode`、桌面端 app data，用于判断“有没有会话/有没有真源/CLI 是否缺失”
  - 支持 env override：`TOKEN_USAGE_OPENCODE_BIN`、`TOKEN_USAGE_OPENCODE_ROOTS`
- `qwen-code-cli`
  - 原生读取官方 project-scoped session JSONL
  - 当前布局优先扫 `~/.qwen/projects/*/chats/*.jsonl`，兼容旧布局 `~/.qwen/tmp/*/chats/*.jsonl`
  - 如果上游设了 `QWEN_RUNTIME_DIR`，默认也会跟随该目录；我们自己的 override 是 `TOKEN_USAGE_QWEN_CODE_ROOT`
- `kimi-cli`
  - 原生读取官方 `~/.kimi/sessions/*/*/wire.jsonl`
  - exact token 来自 `StatusUpdate.token_usage`
  - 如果上游设了 `KIMI_SHARE_DIR`，默认也会跟随该目录；我们自己的 override 是 `TOKEN_USAGE_KIMI_CLI_ROOT`
- `gemini-cli`
  - 原生读取官方 `~/.gemini/tmp/*/chats/session-*.json`
  - exact token 来自每条 Gemini assistant message 的 `tokens`
  - 默认根目录是 `~/.gemini`；我们自己的 override 是 `TOKEN_USAGE_GEMINI_CLI_ROOT`
- `minimax-agent`
  - 原生解析桌面端 `Chromium Cache_Data` 里的 MiniMax Agent HTTP JSON 响应
  - 当前 exact 依赖客户端是否把 token-bearing chat/completion 响应缓存到本地
  - mac 默认根目录：`~/Library/Application Support/MiniMax Agent`
  - Windows 常见根目录：`%APPDATA%\MiniMax Agent`
  - 支持 env override：`TOKEN_USAGE_MINIMAX_AGENT_ROOT`
- `kimi-desktop / glm-desktop / qwen-desktop / deepseek-desktop / doubao-desktop / qianfan-desktop / yuanbao-desktop / perplexity-desktop / stepfun-desktop / sensenova-desktop / baichuan-desktop / siliconflow-desktop / spark-desktop / chatgpt-desktop / gemini-desktop / grok-desktop / mistral-desktop`
  - 现在已经是独立 `source_id`，不再混进 generic fallback
  - 统一走原生 `Chromium / Electron` 桌面适配框架：现在会同时读取 `Cache_Data / IndexedDB / Local Storage`
  - 这一整批桌面 source 现在都已经有 fixture-backed 的 exact-native 覆盖，不再停留在 `detect-ready`
  - 支持 env override：`TOKEN_USAGE_KIMI_DESKTOP_ROOT`、`TOKEN_USAGE_GLM_DESKTOP_ROOT`、`TOKEN_USAGE_QWEN_DESKTOP_ROOT`、`TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT`、`TOKEN_USAGE_DOUBAO_DESKTOP_ROOT`、`TOKEN_USAGE_QIANFAN_DESKTOP_ROOT`、`TOKEN_USAGE_YUANBAO_DESKTOP_ROOT`、`TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT`、`TOKEN_USAGE_STEPFUN_DESKTOP_ROOT`、`TOKEN_USAGE_SENSENOVA_DESKTOP_ROOT`、`TOKEN_USAGE_BAICHUAN_DESKTOP_ROOT`、`TOKEN_USAGE_SILICONFLOW_DESKTOP_ROOT`、`TOKEN_USAGE_SPARK_DESKTOP_ROOT`、`TOKEN_USAGE_CHATGPT_DESKTOP_ROOT`、`TOKEN_USAGE_GEMINI_DESKTOP_ROOT`、`TOKEN_USAGE_GROK_DESKTOP_ROOT`、`TOKEN_USAGE_MISTRAL_DESKTOP_ROOT`
- `generic-openai-compatible`
  - 当前显示名是 `Generic API Compatible`
  - 兼容 OpenAI-compatible / Anthropic-compatible exact usage 结构
  - 可自动扫描常见目录，也可通过 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式配置 JSON / JSONL 日志 glob
  - 当日志不在标准位置时，可设置 `TOKEN_USAGE_DISCOVERY_ROOTS`
- `ingress companion`
  - 面向 `IDE / 内网 launcher / 自定义 base_url` 的本地 companion
  - 当前已经支持 `openai / anthropic / generic` 三种协议模式
  - 它会把 exact usage 响应落成 JSONL，供 provider family 和 generic adapter 自动发现
  - 当前已经内置 bootstrap profiles：`openai / anthropic / gemini / openrouter / perplexity / xai / mistral / stepfun / qwen / kimi / glm / doubao / minimax / openai-compatible / anthropic-compatible / deepseek / qianfan / hunyuan / sensenova / baichuan / siliconflow / spark`

Top20 provider family 的适配规则是统一的：

- 每个 provider family 都是独立 `source_id`
- 它们共用同一套 exact log 发现机制：`TOKEN_USAGE_GENERIC_LOG_GLOBS` + `TOKEN_USAGE_DISCOVERY_ROOTS`
- 解析时按 `provider` 字段优先，其次按 `model` 名回退识别
- `generic-openai-compatible` 只在您显式点名时才参与，避免默认 report 把同一批 API log 重复算两遍

闭源桌面端这条线现在不是“拍脑袋猜目录”，而是：

- 先识别客户端本地真实数据目录
- 再走客户端对应的原生真源路径
- Electron/Chromium 类桌面端优先解析本地 HTTP cache JSON
- Claude / MiniMax / Kimi / GLM / Qwen / Doubao / Perplexity / StepFun / SenseNova / Baichuan / SiliconFlow / Spark / ChatGPT / Gemini / Grok / Mistral 这类桌面端现在都是独立 source，不再只靠 generic log 兜底
- 拿不到 exact 时明确告诉您是“没 parser”还是“当前缓存里确实没有 token 真源”

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

如果您要手动控制 provider / base URL，也可以继续直接用 `ingress config`：

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

如果您想先理解结构和后续怎么维护，也可以看：

- [Architecture](./docs/ARCHITECTURE.md)
- [Contributing](./CONTRIBUTING.md)
- [Changelog](./CHANGELOG.md)

如果您想从当前本机 skill 目录导出一个干净的 GitHub 发布目录，可以运行：

```bash
python3 scripts/build_release.py --output-dir /path/to/token-usage-universal --validate --force
```
