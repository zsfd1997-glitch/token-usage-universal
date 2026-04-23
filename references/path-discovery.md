<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# Path Discovery

面向**默认路径在本机不成立**的场景：内网企业机改了用户目录、会话存在共享盘、客户端被重装到非默认位置、Windows 企业策略把 `AppData` 重定向。本文档给定位真源的标准流程。

## 什么时候走本文档

出现以下任一情况，按本流程走：

- `health` 里大部分来源标 `not_found` 或 `no_data`
- 用户自己说"我 Claude / codex / opencode 明明在用，为什么没统计"
- 用户说"我的会话存在 D 盘 / 共享盘 / 网盘"
- 首次接入、但默认路径表全部扑空

## Step 1：先看机器已解析的绝对路径

不要凭默认表猜，直接让 CLI 打印当前机器的解析结果：

```bash
python3 scripts/token_usage.py health --format json
```

JSON 里每条来源都会带 `default_path` / `resolved_path` / `override_env`，先看这三项是不是指到了用户实际使用的客户端目录。不一致就进 Step 2 搜。

## Step 2：按来源搜真源文件

每条来源的特征文件不一样。如果不知道从哪开始，先从**文件签名**反推，再缩范围。

### 特征文件表

| 来源 | 特征文件 | 常见根目录线索 |
|---|---|---|
| `codex` | `sessions/**/*.jsonl` | `~/.codex`、`%USERPROFILE%\.codex` |
| `claude-code` | `projects/**/*.jsonl`（含 `message.usage`）、`transcripts/*.jsonl` | `~/.claude`、`%USERPROFILE%\.claude` |
| `claude-desktop` | `Cache_Data/`、`IndexedDB/`、`Local Storage/` | `~/Library/Application Support/Claude`、`%APPDATA%\Claude` |
| `opencode` | `storage/session/*.json`、`storage/message/*.json` | `~/.config/opencode`、`~/.local/share/opencode`、`%APPDATA%\opencode` |
| `qwen-code-cli` | `projects/*/chats/*.jsonl` | `~/.qwen` |
| `kimi-cli` | `sessions/*/*/wire.jsonl` | `~/.kimi` |
| `gemini-cli` | `tmp/*/chats/session-*.json` | `~/.gemini` |
| `minimax-agent` | `Cache_Data/` | `~/Library/Application Support/MiniMax Agent`、`%APPDATA%\MiniMax Agent` |
| `desktop-*`（glm/doubao/perplexity/deepseek/qianfan/yuanbao） | `Cache_Data/`、`IndexedDB/` | 同名桌面客户端的 `Application Support` / `%APPDATA%` |
| `generic-openai-compatible` | 用户自定义 jsonl/json | 用户日志目录，需要 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式配置 |

### 搜索模板

```bash
# macOS/Linux：按特征文件名广撒网
find "$HOME" -maxdepth 6 -type f \
  \( -name "*.jsonl" -o -name "session-*.json" -o -name "wire.jsonl" \) \
  -path "*/claude*" -o -path "*/codex*" -o -path "*/opencode*" 2>/dev/null | head -50

# macOS/Linux：找 Chromium/Electron 客户端缓存
find "$HOME/Library/Application Support" -maxdepth 3 -type d \
  -name "Cache_Data" 2>/dev/null

# Linux：同上，但 Application Support 改成 .config / .local/share
find "$HOME/.config" "$HOME/.local/share" -maxdepth 4 -type d \
  \( -name "storage" -o -name "Cache_Data" -o -name "IndexedDB" \) 2>/dev/null
```

```powershell
# Windows PowerShell：按特征文件名
Get-ChildItem -Path $HOME, $env:APPDATA, $env:LOCALAPPDATA -Recurse -Depth 5 `
  -Include "*.jsonl", "session-*.json", "wire.jsonl" `
  -ErrorAction SilentlyContinue | Select-Object FullName -First 50

# Windows PowerShell：找桌面端缓存目录
Get-ChildItem -Path $env:APPDATA -Recurse -Depth 3 -Directory `
  -Filter "Cache_Data" -ErrorAction SilentlyContinue | Select-Object FullName
```

搜到疑似路径后，用 `ls` / `Get-ChildItem` 看里面有没有**今天日期**的文件。有才说明用户真在这个目录下用这个客户端。

## Step 3：用环境变量覆盖默认路径

搜到真源后，不要让用户每次都跑搜索。按来源设一次环境变量，后续 `health` / `report` 自动走新路径。

### 完整覆盖清单

```bash
# 核心 CLI / Desktop
export TOKEN_USAGE_CODEX_ROOT="..."
export TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="..."
export TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="..."
export TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="..."

# 其他 CLI
export TOKEN_USAGE_OPENCODE_BIN="..."
export TOKEN_USAGE_OPENCODE_ROOTS="path1,path2"   # 逗号分隔
export TOKEN_USAGE_QWEN_CODE_ROOT="..."
export TOKEN_USAGE_KIMI_CLI_ROOT="..."
export TOKEN_USAGE_GEMINI_CLI_ROOT="..."

# 其他 Desktop
export TOKEN_USAGE_MINIMAX_AGENT_ROOT="..."
export TOKEN_USAGE_KIMI_DESKTOP_ROOT="..."
export TOKEN_USAGE_DEEPSEEK_DESKTOP_ROOT="..."
export TOKEN_USAGE_QIANFAN_DESKTOP_ROOT="..."
export TOKEN_USAGE_YUANBAO_DESKTOP_ROOT="..."

# 兜底：宽泛扫描
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/logs/**/*.jsonl"
export TOKEN_USAGE_DISCOVERY_ROOTS="$HOME/Library/Application Support,$HOME/.local/share"
```

Windows PowerShell 写法参考 `README.md` 的「环境变量」节。

完整 env 清单自动生成，真源在：[docs/ENV.md](../docs/ENV.md)。

## Step 4：OpenCode / Trae / 内网 launcher 的特殊情况

这类客户端如果支持自定义 `base_url`，优先不要硬搜它的私有日志，改走 **ingress companion**——在本机拉一个透明代理，自动把 exact token 响应落成 JSONL：

```bash
# 列可用的 profile
python3 scripts/token_usage.py ingress profiles

# 生成 IDE bootstrap（含 base_url、VS Code / JetBrains 片段、env 示例）
python3 scripts/token_usage.py ingress bootstrap --profile deepseek --editor vscode

# 启动代理
python3 scripts/token_usage.py ingress serve \
  --provider generic \
  --upstream-base-url http://内网API地址/v1 \
  --protocol openai \
  --project-path "$PWD"
```

代理起来后，把 IDE / 内网 CLI 的 `base_url` 指到 `http://127.0.0.1:8787/v1`，token 会自动进 generic-openai-compatible，`report --today` 能直接看到。

## Step 5：真源不在本机的兜底

如果用户的会话文件存在**远端共享盘/网盘**：

- Linux: `mount` 到本地，再把挂载点作为 `TOKEN_USAGE_*_ROOT`
- macOS: `smb://` / `afp://` 挂到 `/Volumes/...`，同上
- Windows: 映射为盘符（如 `Z:\opencode-sessions`），再设 env var

注意：远端挂载会显著拖慢 `health` / `report`，建议加 `--since/--until` 或 `--today` 缩小扫描范围。

## Step 6：确认闭环

改 env 后**重新**跑一次 `health`，确认原来 `not_found` 的来源变成 `ready`。再跑 `report --today` 看有没有真实数据。如果还是空，进诊断：

```bash
python3 scripts/token_usage.py diagnose --source <source-id> --today
```

`diagnose` 会逐步说明：路径有没有找到 → 有没有今天的文件 → 有没有 token-bearing payload → 哪一步断了。
