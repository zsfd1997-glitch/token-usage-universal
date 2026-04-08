# 安装说明

## 1. 前置条件

- `Python 3.11+`
- 本地可读的 AI 日志目录

## 2. 通过 GitHub 安装

```bash
git clone https://github.com/zsfd1997-glitch/token-usage-universal.git
cd token-usage-universal
```

## 3. 首次自检

```bash
python3 scripts/token_usage.py health
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py targets
python3 scripts/token_usage.py release-gate
python3 scripts/token_usage.py release-gate --output-dir /tmp/token-usage-universal-evidence
```

推荐判断方法：

- `ready`
  - 说明该来源已具备可用真源
- `not-found`
  - 说明来源逻辑支持，但当前路径或真源还没命中
- `detected-no-parser`
  - 说明有痕迹但当前 skill 还没实现解析器
- `not-configured`
  - 说明需要先做显式配置

## 4. 常见配置

### Codex 不在默认路径

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/path/to/codex/sessions"
```

### Claude transcript 或 local-agent 路径不同

```bash
export TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="$HOME/path/to/claude/transcripts"
export TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="$HOME/path/to/local-agent-mode-sessions"
```

说明：

- `Claude` exact 真源不是只认 `timing.json` 这个文件名。
- 现在会接受任何同时带 `total_tokens + executor_end/grader_end` 的 Claude JSON。
- 如果目录里只有 `.claude.json / cowork_settings.json / manifest.json` 这类 session-config 文件，skill 会明确诊断为“有本地布局，但没有 token 真源”。

Windows PowerShell 常见写法：

```powershell
$env:TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="%USERPROFILE%\.claude\transcripts"
$env:TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="%APPDATA%\Claude\local-agent-mode-sessions"
python .\scripts\token_usage.py health
```

### Claude Desktop / Electron 桌面端

```bash
export TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="$HOME/Library/Application Support/Claude"
```

说明：

- `Claude Desktop` 现在是独立 `source_id=claude-desktop`，不再被塞进 `claude-code` 或 generic fallback。
- 当前原生适配会先读 `Cache/Cache_Data`，再把 `IndexedDB / Local Storage` 当作痕迹诊断层。
- 如果 health 提示“desktop traces detected but no exact token payloads”，意思是桌面端痕迹已识别，但当前快照里没有 token-bearing API 响应。

### Generic API exact logs

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/*.jsonl,$HOME/logs/*.json"
export TOKEN_USAGE_DISCOVERY_ROOTS="$HOME/Library/Application Support,$HOME/.local/share"
```

说明：

- 这组配置不只给 `generic-openai-compatible` 用，也会驱动 Top20 provider family source 自动拆分。
- 也就是说，只要 exact log 里带有 `provider / model / usage`，CLI 就会自动分流到 `openai-api / anthropic-api / moonshot-kimi-api / zhipu-glm-api / qwen-api / sensenova-api / baichuan-api / siliconflow-api / spark-api ...` 这类独立来源。
- `generic-openai-compatible` 现在主要用于您手动指定 `--source generic-openai-compatible` 做补漏或诊断。

### OpenCode CLI / 本地 roots

```bash
export TOKEN_USAGE_OPENCODE_BIN="$HOME/.local/bin/opencode"
export TOKEN_USAGE_OPENCODE_ROOTS="$HOME/.config/opencode,$HOME/.local/share/opencode,$HOME/.local/state/opencode"
```

说明：

- `OpenCode` exact 现在优先直读本地 `storage/session + storage/message`。
- 官方 CLI `session list + export` 仍保留为 fallback。
- 本地 roots 会被用来判断“客户端痕迹是否存在”“是不是只有 prompts / logs 没有真源”。
- 如果 CLI 不在 PATH，直接设 `TOKEN_USAGE_OPENCODE_BIN`。

### MiniMax Agent 桌面端

```bash
export TOKEN_USAGE_MINIMAX_AGENT_ROOT="$HOME/Library/Application Support/MiniMax Agent"
```

说明：

- `MiniMax Agent` 当前走桌面端 Chromium `Cache/Cache_Data` 原生解析。
- exact 是否可得，取决于当前客户端缓存里是否落下了带 usage 的 chat/completion JSON。
- 如果 health 里提示“cache detected but no exact token payloads”，意思不是 parser 没做，而是当前缓存快照里确实没有 token 真源。

### Qwen Code CLI / Kimi CLI / Gemini CLI

```bash
export TOKEN_USAGE_QWEN_CODE_ROOT="$HOME/.qwen"
export TOKEN_USAGE_KIMI_CLI_ROOT="$HOME/.kimi"
export TOKEN_USAGE_GEMINI_CLI_ROOT="$HOME/.gemini"
```

说明：

- `qwen-code-cli` 现在会原生读取官方 session JSONL。
- 默认根目录会跟随 `~/.qwen` 或上游 `QWEN_RUNTIME_DIR`；当前优先扫描 `projects/*/chats/*.jsonl`，并兼容旧的 `tmp/*/chats/*.jsonl`。
- `kimi-cli` 现在会原生读取官方 `~/.kimi/sessions/*/*/wire.jsonl`。
- 默认根目录会跟随 `~/.kimi` 或上游 `KIMI_SHARE_DIR`；exact token 来自 `StatusUpdate.token_usage`。
- `gemini-cli` 现在会原生读取官方 `~/.gemini/tmp/*/chats/session-*.json`。
- 默认根目录是 `~/.gemini`；exact token 来自每条 Gemini assistant message 的 `tokens`。

### Chromium / Electron 桌面端

```bash
export TOKEN_USAGE_KIMI_DESKTOP_ROOT="$HOME/Library/Application Support/Kimi"
export TOKEN_USAGE_GLM_DESKTOP_ROOT="$HOME/Library/Application Support/GLM"
export TOKEN_USAGE_QWEN_DESKTOP_ROOT="$HOME/Library/Application Support/Qwen"
export TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT="$HOME/Library/Application Support/DeepSeek"
export TOKEN_USAGE_DOUBAO_DESKTOP_ROOT="$HOME/Library/Application Support/Doubao"
export TOKEN_USAGE_QIANFAN_DESKTOP_ROOT="$HOME/Library/Application Support/Wenxiaoyan"
export TOKEN_USAGE_YUANBAO_DESKTOP_ROOT="$HOME/Library/Application Support/Yuanbao"
export TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT="$HOME/Library/Application Support/Perplexity"
export TOKEN_USAGE_STEPFUN_DESKTOP_ROOT="$HOME/Library/Application Support/StepFun"
export TOKEN_USAGE_SENSENOVA_DESKTOP_ROOT="$HOME/Library/Application Support/SenseNova"
export TOKEN_USAGE_BAICHUAN_DESKTOP_ROOT="$HOME/Library/Application Support/Baichuan"
export TOKEN_USAGE_SILICONFLOW_DESKTOP_ROOT="$HOME/Library/Application Support/SiliconFlow"
export TOKEN_USAGE_SPARK_DESKTOP_ROOT="$HOME/Library/Application Support/Spark"
export TOKEN_USAGE_CHATGPT_DESKTOP_ROOT="$HOME/Library/Application Support/ChatGPT"
export TOKEN_USAGE_GEMINI_DESKTOP_ROOT="$HOME/Library/Application Support/Gemini"
export TOKEN_USAGE_GROK_DESKTOP_ROOT="$HOME/Library/Application Support/Grok"
export TOKEN_USAGE_MISTRAL_DESKTOP_ROOT="$HOME/Library/Application Support/Mistral"
```

说明：

- 这批来源现在已经拆成独立 `source_id`，分别是 `kimi-desktop / glm-desktop / qwen-desktop / deepseek-desktop / doubao-desktop / qianfan-desktop / yuanbao-desktop / perplexity-desktop / stepfun-desktop / sensenova-desktop / baichuan-desktop / siliconflow-desktop / spark-desktop / chatgpt-desktop / gemini-desktop / grok-desktop / mistral-desktop`。
- 它们统一走原生 `Chromium / Electron` 桌面适配框架，现在会同时读取 `Cache_Data / IndexedDB / Local Storage`，不再只依赖 `generic-openai-compatible`。
- 这整批桌面生态当前都已是 fixture-backed 的 `exact-ready`，不再停留在 `detect-ready`。
- 如果默认目录没命中，直接设对应 env override；如果命中但没有 exact，health 会明确告诉您“有桌面痕迹但当前没有 token 真源”。

### IDE / 内网 launcher / 自定义 base_url

先看内置 bootstrap profile：

```bash
python3 scripts/token_usage.py ingress profiles
```

```bash
python3 scripts/token_usage.py ingress bootstrap \
  --profile deepseek \
  --editor vscode
```

说明：

- `ingress bootstrap` 会直接打印 Continue 的 `VS Code / JetBrains` 配置片段、CLI shell env 示例，以及 companion 的本地代理地址。
- `ingress profiles` 会列出内置 profile，目前包括 `openai / anthropic / gemini / openrouter / perplexity / xai / mistral / stepfun / qwen / kimi / glm / doubao / minimax / openai-compatible / anthropic-compatible / deepseek / qianfan / hunyuan / sensenova / baichuan / siliconflow / spark`。
- `ingress config` 仍然保留，适合您要手动指定 provider/base URL 时单独查看本地代理地址。
- `ingress serve` 会启动本地 companion，把 exact usage 响应落成 JSONL，供 provider family 自动发现。
- 这条链路优先面向 `IDE / 私有 launcher / 企业内网封装 CLI`，不要求对方一定有 `skills` 目录。

实际启动：

```bash
python3 scripts/token_usage.py ingress serve \
  --provider deepseek \
  --upstream-base-url https://api.deepseek.com \
  --protocol openai \
  --project-path "$PWD"
```

## 5. 验证主命令

```bash
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py release-gate --format json
python3 scripts/token_usage.py release-gate --format json --output-dir /tmp/token-usage-universal-evidence
python3 scripts/token_usage.py diagnose --source codex --today
python3 scripts/token_usage.py diagnose --source qwen-code-cli --today
python3 scripts/token_usage.py diagnose --source kimi-cli --today
python3 scripts/token_usage.py diagnose --source claude-desktop --today
python3 scripts/token_usage.py diagnose --source minimax-agent --today
python3 scripts/token_usage.py ingress profiles
python3 scripts/token_usage.py ingress bootstrap --profile deepseek --editor vscode
python3 scripts/token_usage.py ingress config --provider deepseek --upstream-base-url https://api.deepseek.com --protocol openai
```
