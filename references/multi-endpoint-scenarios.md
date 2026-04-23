<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# Multi-Endpoint Scenarios

面向**同机多端并存**、**IDE 内嵌 CLI**、**IDE 直连第三方 URL** 这类容易漏统计或误统计的场景。`health` 输出看着正常、但用户觉得数字不对时，优先对照本文档三条分支。

## Scenario A：opencode 桌面端 + CLI + IDE 插件 三端共存

同一台机器上 OpenCode 可能以三种形态同时存在：

1. **桌面端**：Windows `opencode.exe`、macOS `OpenCode.app`、Linux `opencode` 可执行文件
2. **CLI 端**：Windows `opencode-cli.exe`、*nix shell 里的 `opencode` 命令
3. **IDE 插件**：VS Code / Cursor / JetBrains / Trae 里的 OpenCode 扩展

### 结论先行

**三端都有可能落到同一个 `opencode` source，也有可能分散到多个目录。**统计时必须把三端的目录都覆盖进去，缺一条就会出现"一端看着 0，另一端看着正常"的错觉。

所以正常情况下**不要**把三端拆成三条 source 报数，也不要在用户问"今天总消耗"时只看其中一端。**尤其不允许说 CLI 端 0 token——默认视图是全机聚合，不是单端**。

### 三端的落盘规律

不同形态落盘位置不同，不能一刀切：

| 形态 | Windows 常见根 | macOS 常见根 | Linux 常见根 | 是否在默认扫描里 |
|---|---|---|---|---|
| 桌面端 `opencode.exe` | `%APPDATA%\OpenCode`、`%APPDATA%\ai.opencode.desktop` | `~/Library/Application Support/OpenCode`、`~/Library/Application Support/ai.opencode.desktop` | `~/.config/opencode`、`~/.local/share/opencode` | ✅ 是 |
| CLI `opencode-cli.exe` | `%APPDATA%\opencode`、`%LOCALAPPDATA%\opencode` | `~/.config/opencode`、`~/.opencode` | `~/.config/opencode`、`~/.local/state/opencode`、`~/.opencode` | ✅ 是（但 `%APPDATA%\opencode-cli` 这种带 `-cli` 后缀的变体**不**在默认里） |
| IDE 插件 | `%APPDATA%\Code\User\globalStorage\<pub>.opencode-*\`、`%APPDATA%\JetBrains\...\opencode\` | `~/Library/Application Support/Code/User/globalStorage/...`、同上 JetBrains | `~/.config/Code/User/globalStorage/...` | ❌ **插件根都不在默认扫描里** |

### 插件端怎么定位

VS Code / Cursor / JetBrains 插件把状态写到 IDE 自己的扩展存储里，而不是 OpenCode 通用目录。**如果插件是"调外部 `opencode-cli` 子进程"那种架构，token 会写到 CLI 的 `storage/session`，照常被覆盖**；只有插件自己直连 API 或自己落盘时才需要额外接入。

让用户跑一次定位扫描：

```powershell
# Windows：VS Code / Cursor / JetBrains 扩展根里找 opencode 相关子目录
Get-ChildItem -Path "$env:APPDATA\Code\User\globalStorage", `
  "$env:APPDATA\Cursor\User\globalStorage", `
  "$env:APPDATA\JetBrains" -Recurse -Depth 4 -Directory `
  -Filter "*opencode*" -ErrorAction SilentlyContinue | Select-Object FullName

# 在命中的每个目录里，看有没有类似 storage/session 的痕迹或 *.jsonl / *.log
Get-ChildItem -Path <命中目录> -Recurse -Depth 4 -File `
  -Include "*.jsonl","*.json","*.log" -ErrorAction SilentlyContinue |
  Select-Object FullName, Length | Sort-Object Length -Descending | Select-Object -First 20
```

```bash
# macOS / Linux
find "$HOME/.config/Code/User/globalStorage" \
     "$HOME/.config/Cursor/User/globalStorage" \
     "$HOME/Library/Application Support/Code/User/globalStorage" \
     "$HOME/Library/Application Support/Cursor/User/globalStorage" \
     "$HOME/.config/JetBrains" \
  -maxdepth 5 -type d -name "*opencode*" 2>/dev/null
```

三种可能：

1. **没命中任何路径** → 插件是 CLI 子进程模式，token 已经被 CLI 端覆盖，不需要额外动作
2. **命中目录里是配置但没 `storage/session`** → 插件不落 token 真源，只能走 ingress（让用户在插件里把 `base_url` 指到本地 companion）
3. **命中目录里有 `storage/session` 或 token-bearing JSONL** → 追加到 `TOKEN_USAGE_OPENCODE_ROOTS`，让 `opencode` adapter 把它扫进来

### 默认扫描覆盖

`default_opencode_roots()` 已经覆盖：

| 平台 | 默认根 |
|---|---|
| Windows | `%APPDATA%\OpenCode`、`%APPDATA%\ai.opencode.desktop`、`%APPDATA%\opencode`、`%LOCALAPPDATA%\opencode` |
| macOS | `~/Library/Application Support/OpenCode`、`~/Library/Application Support/ai.opencode.desktop`、`~/.config/opencode`、`~/.local/state/opencode`、`~/.local/share/opencode`、`~/.opencode` |
| Linux | `~/.config/opencode`、`~/.local/state/opencode`、`~/.local/share/opencode`、`~/.opencode` |

### 什么时候会漏

- `opencode-cli.exe` 和 `opencode.exe` **写到不同的 `%APPDATA%` 子目录**（常见组合：桌面端 `%APPDATA%\OpenCode`、CLI 端 `%APPDATA%\opencode` 或 `%APPDATA%\opencode-cli`）。前两个变体在默认列表里，`opencode-cli` 这种命名变体**不在**默认列表，会漏
- 用户 CLI 走 **WSL / Git Bash** 但 `$HOME` 指向 `/home/<user>`，而本工具在 Windows 侧跑 → Windows 默认根里没这个 Linux-风格目录
- 用户魔改了 OpenCode 的 `--config` 或 `OPENCODE_STORAGE_DIR`，写到了非标准路径
- 企业机把 `%APPDATA%` 重定向到 OneDrive / 网络盘，desktop 写进去了但扫描时没 mount

### Windows 上的快速自查

让用户跑：

```powershell
# 看两个 exe 分别在哪
Get-Command opencode, opencode-cli -ErrorAction SilentlyContinue | Select-Object Name, Source

# 看 APPDATA / LOCALAPPDATA 下所有 opencode 相关目录
Get-ChildItem -Path $env:APPDATA, $env:LOCALAPPDATA -Directory `
  -Filter "*opencode*" -ErrorAction SilentlyContinue | Select-Object FullName

# 对每个命中的目录再看是否含 storage/session
Get-ChildItem -Path <命中目录> -Recurse -Depth 3 -Directory -Filter session `
  -ErrorAction SilentlyContinue | Select-Object FullName
```

任何命中 `storage\session` 的目录都是真源，补进 env 即可。

### 引导动作

1. 先确认是不是真的漏。让用户跑 `report --today --by session`，看 session 数量和他记忆中的是否一致。如果对得上就**不用动**。
2. 数不对时，跑 `find`（macOS/Linux）/ `Get-ChildItem`（Windows）按 `storage/session` 路径签名广搜一遍（模板见 [path-discovery.md](path-discovery.md)）。
3. 发现有漏的根，**追加**到 `TOKEN_USAGE_OPENCODE_ROOTS`（逗号分隔多个）。注意这个 env 是**替换**默认列表，不是追加——要保留默认根，得手动把它们一起写进 env：

Windows PowerShell（同时覆盖桌面端、CLI、插件扩展三种根）：

```powershell
$env:TOKEN_USAGE_OPENCODE_ROOTS = @(
    "$env:APPDATA\OpenCode",                 # 桌面端
    "$env:APPDATA\ai.opencode.desktop",      # 桌面端（Electron bundle id）
    "$env:APPDATA\opencode",                 # CLI 默认
    "$env:APPDATA\opencode-cli",             # CLI 带后缀命名
    "$env:LOCALAPPDATA\opencode",            # CLI 有些版本落 Local
    "$env:LOCALAPPDATA\opencode-cli",
    "$env:APPDATA\Code\User\globalStorage\<pub>.opencode-<name>",  # VS Code 插件（替换为真实目录）
    "$env:APPDATA\Cursor\User\globalStorage\<pub>.opencode-<name>"  # Cursor 插件
) -join ","
python .\scripts\token_usage.py health
```

macOS / Linux（含 WSL 跨挂载兜底）：

```bash
export TOKEN_USAGE_OPENCODE_ROOTS="$HOME/.config/opencode,$HOME/.local/share/opencode,$HOME/.opencode,/mnt/c/Users/<name>/AppData/Roaming/OpenCode,/mnt/c/Users/<name>/AppData/Roaming/opencode-cli"
python3 scripts/token_usage.py health
```

完整默认列表在 [path-discovery.md](path-discovery.md) 里能直接复制。

### 禁忌

- **不要**把桌面、CLI、插件拆成三条 source 分别汇报；它们共享同一个 `opencode` source
- **不要**在 CLI 端（或插件端）说"本次对话消耗 0"来代表 OpenCode 总消耗；这些端看到的是**本机所有 OpenCode session**的总和，不是当前 IDE / 终端 session
- **不要**默认跳过插件根；即使只看桌面 + CLI，也要先明确告诉用户"插件端未纳入"，别让他们以为已经全量了

## Scenario B：Trae 自身 token 统计

### 结论先行

**Trae 原生对话（用它内置模型 + 内置 chat UI）目前无法 exact 统计**。必须靠"人工协同"把 token 引出来，下面四条路按可行性排序。

### 为什么拿不到 exact token（说给用户听的版本）

Trae 把所有聊天记录存在本地加密 SQLite：`<root>/ModularData/ai-agent/database.db`。这个 DB 用 AES 加密，密钥托管在操作系统 keychain（macOS Keychain / Windows DPAPI / Linux libsecret），**我们没有合法的解密路径**。

能拿到的只有：

- 安装检测（目录 + `database.db` 是否存在）
- session ID（workspace state.vscdb 里的 MongoDB ObjectID）
- 每个 session 用的模型名（`ai-chat:sessionRelation:modelMap`）
- 粗略时间戳（ObjectID 前 4 字节编码的 Unix epoch）

**拿不到的**就是每次请求的 input / output / cache / total token——这些字段全在加密 DB 里。所以 `TraeAdapter.accuracy_level = "unsupported"`，`diagnose --source trae` 永远返回"要 exact 就走 ingress"。

### 人工协同方案

按工作量从小到大排序。**每个方案都需要用户动手配合一次**，没有真正的"零操作"路径。

#### 方案 1：Trae 里自定义 `base_url` → 本地 ingress companion（推荐，覆盖面最大）

Trae 允许用户在「模型设置」里配置**自定义模型**，填自己的 API key 和 base URL。这是**唯一不需要第三方抓包工具**的办法：

1. 问用户现在 Trae 里跑的是哪个上游：
   - "连百炼 / Qwen / 通义" → 上游 `https://dashscope.aliyuncs.com/compatible-mode/v1`
   - "连 Kimi / Moonshot" → `https://api.moonshot.cn/v1`
   - "连 DeepSeek / GLM" → 对应官方 URL
   - "连公司内网网关" → 内网地址
2. 生成 bootstrap 和启动代理：

```bash
# 百炼 / DashScope（现成 profile）
python3 scripts/token_usage.py ingress bootstrap --profile qwen --editor trae
python3 scripts/token_usage.py ingress serve \
  --provider qwen \
  --upstream-base-url https://dashscope.aliyuncs.com/compatible-mode/v1 \
  --protocol openai \
  --project-path "$PWD"

# 内网网关
python3 scripts/token_usage.py ingress serve \
  --provider generic \
  --upstream-base-url http://your-internal-gateway/v1 \
  --protocol openai \
  --project-path "$PWD"
```

3. 到 **Trae → 设置 → 模型管理 → 添加自定义模型**：base URL 填本地 companion 地址（形如 `http://127.0.0.1:8787/v1` 或 `/compatible-mode/v1`），模型名用上游允许的（`qwen3-coder-plus` / `qwen-max` 等）。
4. 把 Trae 的默认模型切到这个自定义模型。
5. 用户聊两三轮后，跑 `report --today --by source` 确认 `qwen-api` 或 `generic-openai-compatible` 里出现数据。

**局限**：Trae 的**内置模型**（它自己托管的那套）没法自定义上游，这条路管不到。只能管"用户自己配的 base_url"。

#### 方案 2：系统代理抓包（mitmproxy / Fiddler / Charles，覆盖 Trae 全流量）

内置模型也要统计时，只能在网络层劫持。适合愿意装抓包工具的用户：

1. 装 mitmproxy（跨平台、免费）：`brew install mitmproxy` / `pip install mitmproxy` / Windows 安装包
2. 写一个 addon 把 `/v1/chat/completions` 响应的 `usage` 字段落成 JSONL：

```python
# ~/trae_usage_addon.py
import json, time, pathlib
OUT = pathlib.Path.home() / "trae_usage.jsonl"
def response(flow):
    if "/chat/completions" not in flow.request.path and "/messages" not in flow.request.path:
        return
    try:
        body = json.loads(flow.response.get_text())
        usage = body.get("usage")
        if not usage:
            return
        record = {
            "timestamp": time.time(),
            "provider": "trae-captured",
            "base_url": flow.request.scheme + "://" + flow.request.host,
            "endpoint": flow.request.path,
            "model": body.get("model"),
            "usage": usage,
        }
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
```

3. 启动 mitmproxy：`mitmproxy -s ~/trae_usage_addon.py --mode regular@8080`
4. 让 Trae 走这个代理：Windows 在系统代理设置填 `127.0.0.1:8080`；macOS 在网络设置加 HTTP/HTTPS 代理；Linux 用 `HTTP_PROXY=http://127.0.0.1:8080 trae`
5. 安装并信任 mitmproxy 的 CA 证书（`mitm.it` 下载），否则 HTTPS 握手失败
6. 配本工具把落盘的 JSONL 当 generic 源扫进来：

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/trae_usage.jsonl"
python3 scripts/token_usage.py health
python3 scripts/token_usage.py report --today
```

**局限**：

- 需要用户自己装 mitmproxy + 信任 CA 证书，企业机可能被安全策略拦
- 只覆盖装代理之后的流量，历史对话捞不回来
- 如果 Trae 用 cert pinning（目前没观察到，但未来可能变），这条路会断

#### 方案 3：Trae 内置 export（如果版本支持）

部分 Trae 版本在 chat 界面右键有「导出对话」或类似按钮，导出 `.md` / `.json`。**但 token 字段是否包含在导出里，取决于 Trae 版本**——老版本只导出文本，没有 usage。

**指引**：

1. 让用户在 Trae 里右键某条对话，看有没有「Export / 导出」选项
2. 导出成 JSON 后看是否有 `usage` / `input_tokens` / `output_tokens` 之类字段
3. 有的话：把导出的文件放进 `$HOME/trae_exports/*.json`，用 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 扫进来
4. 没有的话：退回方案 1 或 2

**局限**：Trae 版本差异大，本工具无法预判某个用户的版本支持不支持。让用户实测。

#### 方案 4：解密 SQLite（**不推荐**）

理论上 Trae 的 AES 密钥在 OS keychain，可以用 keychain-dump 工具拿出来解 DB。**我们明确不支持这条路**，原因：

- 违反 Trae ToS，企业合规不过关
- 密钥格式和加密算法随版本变，抗升级能力差
- 涉及绕过用户数据保护机制，出问题用户自己背

遇到用户问"能不能解密出来"，回"不行，建议走方案 1 或 2"，不要给技术细节。

### 汇总：Trae 场景决策

| 用户情况 | 推荐方案 |
|---|---|
| Trae 里**能**改自定义 `base_url`，愿意走代理 | 方案 1（ingress companion） |
| Trae 里**不能**改 base_url（公司锁定），但可以装工具 | 方案 2（mitmproxy 系统代理抓包） |
| 公司机连 mitmproxy 都装不了，只想粗估 | 方案 3（如果版本支持 export），或接受"Trae 部分统计不到" |
| Trae 在 terminal 里跑 opencode 子进程 | 忽略 Trae，走 `opencode` source（详见本文档 Scenario A 插件部分） |

### 禁忌

- **不要**对 `trae` source 反复 diagnose 期望拿到 exact；它是 unsupported，诊断结论永远是"上面四条路选一条"
- **不要**在没启 ingress / 没装代理的情况下，给用户一个"Trae 今天消耗"的估算数字冒充 exact
- **不要**建议用户解密 DB

## 汇总决策表

| 用户描述 | 落到哪个 source | 需要额外操作吗 |
|---|---|---|
| 同机用 `opencode.exe` + `opencode-cli.exe` | `opencode`（自动聚合） | 非默认根 / 插件目录时扩 `TOKEN_USAGE_OPENCODE_ROOTS` |
| 同机桌面 + CLI + IDE 插件三端 | `opencode`（自动聚合，前提扫到插件根） | 要先跑插件定位扫描，把插件根加进 env |
| Trae IDE 里跑 opencode 子进程 | `opencode` | 无（Trae 自身永远 unsupported，不挣扎） |
| Trae **自定义 base_url** 连阿里百炼 | `qwen-api` | 必须先起 `ingress serve --profile qwen` |
| Trae **自定义 base_url** 连内网网关 | `generic-openai-compatible` 或按 provider 参数归因 | 必须先起 `ingress serve --upstream-base-url <网关>` |
| Trae 用**内置模型**（不改 base_url） | 默认拿不到 exact | 方案 2（mitmproxy 系统代理抓包） |
| Trae 导出对话文件带 `usage` 字段 | `generic-openai-compatible` | 用 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 指到导出文件 |
