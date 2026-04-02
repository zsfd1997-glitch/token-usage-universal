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

### Generic API exact logs

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/*.jsonl,$HOME/logs/*.json"
export TOKEN_USAGE_DISCOVERY_ROOTS="$HOME/Library/Application Support,$HOME/.local/share"
```

### OpenCode CLI / 本地 roots

```bash
export TOKEN_USAGE_OPENCODE_BIN="$HOME/.local/bin/opencode"
export TOKEN_USAGE_OPENCODE_ROOTS="$HOME/.config/opencode,$HOME/.local/share/opencode,$HOME/.local/state/opencode"
```

说明：

- `OpenCode` exact 优先依赖官方 CLI `session list + export`。
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

## 5. 验证主命令

```bash
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py diagnose --source codex --today
```
