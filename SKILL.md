---
name: "token-usage-universal"
description: "Use when the user asks to view local token usage, summarize today's or recent usage, compare sources/projects, or diagnose why a local AI client is not being counted. Reads local logs only and defaults to exact results."
---

# Token Usage Universal

这是仓库附带的自然语言触发层，用来把“我想看 token”这类人话请求，直接翻成正确的 CLI 调用。

真正负责统计和诊断的是 `scripts/token_usage.py` 这个独立 Python CLI；这个 skill 的工作，是把用户说的人话翻成正确命令，再把结果按固定协议回出来。

## 成品形态

- 产品本体：`独立 Python CLI`
- skill 形态：面向聊天入口的自然语言包装层
- 内部命令入口：`scripts/token_usage.py`

## 这个 skill 解决什么问题

- 想看今天、本周或本月一共用了多少 token，但不想记命令
- 想知道哪个模型、哪个项目、哪个来源最费
- 想看缓存命中和真实消耗的区别
- 想查为什么 `Claude / Codex / MiniMax Agent / 其他桌面端` 没被统计到

它适合当一个本地优先的 token 查询入口，不适合冒充云账单页，也不应该在没有本地真源时瞎猜数字。

## 用途

- 面向“今天 token 用了多少”这类日常查询
- 面向“最近趋势怎么样”这类复盘
- 面向“哪个模型 / 项目 / 来源最费”这类拆分
- 面向“为什么没统计到某个客户端”这类排障
- 面向 skill / agent / launcher 的复用

## 什么时候触发

- 用户问“今天 token 用量多少”
- 用户问“最近 7 天 token 用量”
- 用户问“按来源 / 按项目统计 token”
- 用户问“为什么 Claude / Codex / 其他客户端没统计到”
- 用户问“为什么 OpenCode / MiniMax Agent / 其他桌面端没统计到”
- 用户要求一个极简、可推广、基于本地日志真源的 usage 统计能力
- 用户只说“token / 用量 / 消耗量 / 使用量 / 消耗”

## 短触发词

用户只说“token / 用量 / 消耗量 / 使用量 / 消耗”，默认就应该触发这个 skill。

- “token”
- “用量”
- “消耗量”
- “使用量”
- “消耗”

这些短词默认理解成“先看今天总览”，而不是回一句解释性废话。

## 使用示例

### 示例 1

用户说：

- `token`

skill 默认动作：

- 先给今天总览
- 再带上当前会话、按模型、按项目、最近 7 天趋势和月历热力图

### 示例 2

用户说：

- `帮我按模型看看今天哪个最消耗 token`

skill 默认动作：

- 优先走 `report --today --by model`
- 重点解释哪个模型最高、是否有缓存命中、费用大概多少

### 示例 3

用户说：

- `为什么 Claude 没统计到`

skill 默认动作：

- 优先走 `diagnose --source claude-code` 或 `diagnose --source claude-desktop`
- 如果只是“看到了客户端痕迹，但没有 exact token 真源”，直接说清楚

### 示例 4

用户说：

- `看不懂图，直接告诉我结果`

skill 默认动作：

- 可以降级成简版结论
- 但如果底层已经有完整面板，默认还是先面板后总结，除非用户明确要求不要图

## 常见说法

### 看今天 / 当前总量

- “今日 token”
- “今天的 token”
- “token 用量”
- “AI 用量”
- “我今天 AI 用了多少”
- “今天一共消耗了多少 token”
- “帮我看看今天 token 用量”
- “帮我看今天总量”

### 看最近趋势

- “本周 token”
- “这周 token”
- “最近 token”
- “最近几天用量怎么样”
- “最近 7 天 token 走势”
- “最近 30 天 token 趋势”
- “最近是不是用得很多”

### 看哪个模型或项目最费

- “哪个模型最消耗 token”
- “帮我按模型看看今天哪个最消耗 token”
- “哪个项目 token 用量最高”
- “帮我按项目拆一下”
- “看看项目分布”

### 查为什么没统计到

- “为什么这次没有统计到”
- “Claude 怎么没算进去”
- “为什么没统计到 Claude”
- “哪个来源没被算进去”
- “帮我查一下为什么没有数据”

### 要简单版

- “给我一个最简单的用量概览”
- “别太复杂”
- “看不懂图，直接说结论”
- “不用图，直接告诉我结果”
- “先给我纯文字版本”

## 用户说不清时，怎么引导

默认引导规则：

- 如果用户只说“token”“用量”“消耗量”“使用量”“今日 token”“今天的 token”
  - 默认先给：`今天总览 + 当前会话 + 按模型 + 按项目 + 最近 7 天趋势 + 月历热力图`
- 如果用户只说“本周 token”“这周 token”“最近 token”
  - 优先先给一个短选择：
    - `1. 最近一周 token 消耗情况`
    - `2. 最近一个月 token 消耗情况`
    - `3. 关闭`
  - 如果用户没选，再默认先给：`本周总览 + 按模型 + 按项目 + 最近 7 天趋势 + 最近 30 天趋势 + 月历热力图`
- 如果用户只说“看看最近怎么样”
  - 默认先给：`今天总览 + 最近 7 天趋势 + token 消耗最高的模型/项目`
- 如果用户只说“是不是用太多了”或“最近是不是消耗了很多 token”
  - 默认先给：`今天总量 + 最近 7 天趋势 + 等级判断 + 估算费用`
- 如果用户只说“哪个最消耗 token”或“哪里 token 用量最高”
  - 默认先给：`按模型 + 按项目`
- 如果用户只说“这一轮怎么样”
  - 默认先给：`当前会话`
- 如果用户只说“怎么没统计到”
  - 默认先给：`diagnose`，必要时补 `health / sources`
- 如果用户提到“看不懂图”
  - 默认降级为最简单纯文字版本，不强推图形视图

引导方式要克制：

- 先把默认 `ascii-hifi` 面板打出来，再补 2 到 4 句高信号结论
- 除非用户明确说“简单说”“不要图”，否则不要把默认结果压缩成纯口语摘要
- 优先先给一个默认答案，再补一句“要继续的话，我可以再展开看模型 / 项目 / 当前会话”
- 不要一上来反问一长串
- 不要让用户自己决定 `--trend / --calendar / --session`
- 用户没说清时，先替他走最常见的一步，而不是把选择题全部丢回去

## 默认面板协议

这个 skill 的默认成品不是一句话摘要，而是一个带相关上下文的 `ascii-hifi` 面板。

对短触发词尤其要严格执行，例如：

- “token”
- “用量”
- “消耗量”
- “使用量”
- “消耗”
- “今日 token”
- “本周 token”
- “这周 token”

这些输入都不应该只返回一个数字。

聊天输出协议也要更硬：

- 只要底层 CLI 已返回 `ascii-hifi` 面板，最终回复必须先原样贴出面板，再补简短结论
- 默认把面板放进 fenced code block，避免被二次改写成项目符号摘要
- 不要先写口语总结再省略面板
- 不要把 ASCII 面板“翻译”为另一套表述后冒充等价输出
- 只有用户明确说“简单说 / 不用图 / 纯文字”时，才允许跳过面板

默认至少要包含：

- 当前时间窗口总览
- `总 token` 和 `去缓存后 token`
- 当前会话
- 按模型
- 按项目
- 最近趋势图
- 月历热力图

默认展示口径：

- `费用` 默认按“去缓存后 token”估算，不把缓存 token 算进费用里
- 模型 / 项目 / 趋势 / 月历默认优先看“去缓存后 token”
- 如果同时展示 `总 token`，要把它和 `去缓存后 token` 明确区分开，不允许只丢一个裸数字

只有当用户明确说：

- “简单说”
- “先给结论”
- “不用图”
- “纯文字版本”

才允许降级成不带图的简版说明。

推荐的默认回复骨架：

1. 先输出 `ascii-hifi` 面板
2. 再补 1 到 3 句高信号结论
3. 最后补一句可选展开方向，例如“要继续的话，我再拆模型 / 项目 / 当前会话”

推荐的收口式引导：

- “先看今天总览和最近 7 天趋势；要继续的话，再拆到模型或项目。”
- “先查为什么没统计到；如果是路径或真源问题，直接给下一步。”
- “先给最简单版本，不上复杂图表；要更细再展开。”

## 原则

1. `Local-first`
- 默认只读本地日志，不联网。
- 这意味着在中国本地内网、无法访问百度或外网时，skill 仍然可以使用；前提只是本地日志路径可读。

2. `Exact-first`
- 默认只输出 `exact`。
- 没有本地真源时，不猜，不估算，直接标成 `unsupported` 或 `not configured`。

3. `Source-first`
- 以日志来源适配，不以模型名适配。

4. `Native-client-first`
- 对闭源桌面端优先找本地原生真源，例如 `CLI export`、`Chromium Cache_Data`、本地 session artifacts。
- 如果当前只能确认“客户端存在，但缓存里没有 token 真源”，必须明确报出来，不能伪装成已支持。

5. `Provider-family split`
- 对 Top20 级 API/provider family 要拆成独立 `source_id`，不能长期堆在一个 `generic` 来源里。
- `generic-openai-compatible` 只作为手动 fallback / diagnose 入口，不默认参与总览，避免和独立 provider family 重复计数。

## 维护者命令

这一节是给维护者 / 开发者 / 调试者看的。

用户不需要输入这些命令；直接提需求即可。

```bash
python3 scripts/token_usage.py report --today
python3 scripts/token_usage.py report --today --by model
python3 scripts/token_usage.py report --today --by day
python3 scripts/token_usage.py report --trend 7d
python3 scripts/token_usage.py report --calendar month --month 2026-03
python3 scripts/token_usage.py report --current-session
python3 scripts/token_usage.py report --session <session-id>
python3 scripts/token_usage.py report --today --plain-ascii
python3 scripts/token_usage.py report --last 7d --by source
python3 scripts/token_usage.py report --today --by project
python3 scripts/token_usage.py explore
python3 scripts/token_usage.py health
python3 scripts/token_usage.py sources
python3 scripts/token_usage.py diagnose --source codex --today
```

如果被别的 agent / skill / launcher 复用，直接调用 `scripts/token_usage.py` 即可，不要求宿主一定存在 `~/.codex/skills`。

## 当前支持

- `codex`: `exact`
  - 读取 `~/.codex/sessions/**/*.jsonl`
  - 基于 `token_count.info.total_token_usage` 的累计变化量精确统计
- `generic-openai-compatible`: `exact` when configured or auto-discovered
  - 兼容 OpenAI-compatible / Anthropic-compatible usage 结构
  - 可通过 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式指定日志文件 glob
  - 也可通过 `TOKEN_USAGE_DISCOVERY_ROOTS` 扩展自动发现根目录
  - 只接受带明确 usage 数值和时间戳的 JSON / JSONL
- `claude-code`: `exact` when token-bearing local JSON was captured, otherwise `diagnose`
  - 默认适配 macOS `~/Library/Application Support/Claude/local-agent-mode-sessions/**` 与 Windows `%APPDATA%\Claude\local-agent-mode-sessions\**`
  - 旧版常见 exact 文件叫 `timing.json`，但现在也支持任何同时带 `total_tokens + executor_end/grader_end` 的 Claude JSON
  - 该真源可精确提供 `total_tokens` 与完成时间，但通常不含 `input/output/cache` 拆分
  - 如果只有 `.claude.json / cowork_settings.json / manifest.json` 这类 session-config 文件，明确诊断为“有布局、没 token 真源”
  - 只有 transcript、没有 exact JSON 时，明确降级，不输出伪精确数据
- `claude-desktop`: `exact` when token-bearing desktop API cache exists, otherwise `diagnose`
  - 默认适配 macOS `~/Library/Application Support/Claude` 与 Windows `%APPDATA%\Claude`
  - 原生解析 `Chromium Cache_Data`，并把 `IndexedDB / Local Storage` 当作桌面端痕迹诊断层
  - 如果当前缓存快照没有 token-bearing API 响应，明确报“有桌面痕迹但没有 exact token 真源”
- `minimax-agent`: `exact` when token-bearing desktop API cache exists, otherwise `diagnose`
  - 默认适配 macOS `~/Library/Application Support/MiniMax Agent` 与 Windows `%APPDATA%\MiniMax Agent`
  - 原生解析桌面端 `Chromium Cache_Data`
- `kimi-desktop / glm-desktop / qwen-desktop / doubao-desktop / perplexity-desktop`: `diagnose-first`, `exact` when token-bearing desktop API cache exists
  - 已拆成独立 `source_id`
  - 统一走原生 `Chromium / Electron` 桌面适配框架，不再只靠 generic fallback
  - 默认目录没命中时，分别用 `TOKEN_USAGE_KIMI_DESKTOP_ROOT / TOKEN_USAGE_GLM_DESKTOP_ROOT / TOKEN_USAGE_QWEN_DESKTOP_ROOT / TOKEN_USAGE_DOUBAO_DESKTOP_ROOT / TOKEN_USAGE_PERPLEXITY_DESKTOP_ROOT`

## Windows 支持

- 现在已按跨平台路径处理，不再只按 `/` 解析项目路径，Windows 的 `C:\...` 项目名也能正确显示成最后一级目录。
- `codex` 默认根目录仍是用户主目录下的 `.codex/sessions`，Windows 下也可直接用 `%USERPROFILE%/.codex/sessions` 这类写法。
- `generic-openai-compatible` 现在支持 `%USERPROFILE%`、`%APPDATA%` 这类 Windows 风格环境变量占位，也支持自定义自动发现根目录。
- `claude-code` 默认会优先适配 Windows 常见路径 `%APPDATA%\Claude\local-agent-mode-sessions`；如果安装位置不同，仍然建议用 env override 指明。
- `claude-desktop / minimax-agent / kimi-desktop / glm-desktop / qwen-desktop / doubao-desktop / perplexity-desktop` 也都按 Windows 常见 app-data 路径做了默认探测；如果安装位置不同，再用各自 env override。
- 结论：Windows 环境不要求联网，也不要求访问百度；只要本地日志可读、Python 可运行，就可以使用。

## Linux 支持

- 现在默认会探测 Linux 常见根目录，不再只写 macOS / Windows 两套路径。
- `claude-code` 的 local-agent-mode-sessions 默认根目录是 `~/.config/Claude/local-agent-mode-sessions`。
- `claude-desktop / kimi-desktop / glm-desktop / qwen-desktop / doubao-desktop / perplexity-desktop / 其他 Chromium/Electron 桌面端` 默认会探测 `~/.config/<App>` 和 `~/.local/share/<App>`。
- `minimax-agent` 默认根目录是 `~/.config/MiniMax Agent`。
- `opencode` 默认会探测 `~/.config/opencode`、`~/.local/state/opencode`、`~/.local/share/opencode` 和 `~/.opencode`。
- `generic-openai-compatible` 默认自动发现根目录是 `~/.config`、`~/.local/state`、`~/.local/share`；日志不在这些地方时，再用 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 或 `TOKEN_USAGE_DISCOVERY_ROOTS` 覆写。

## 当前可复用性结论

- 别人现在可以直接复用 `codex` 路径能力，只要本机也使用标准 `~/.codex/sessions`。
- `generic-openai-compatible` 也能复用；优先靠自动发现，必要时再配置 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 或 `TOKEN_USAGE_DISCOVERY_ROOTS`。
- `claude-code` 现在已同时覆盖 macOS 和 Windows 常见默认真源路径；如果安装位置不同，再用 env override 即可。
- 闭源桌面端这条线现在也有独立 source：`claude-desktop / minimax-agent / kimi-desktop / glm-desktop / qwen-desktop / doubao-desktop / perplexity-desktop`。
- 结论：这个 skill 现在已经具备跨平台路径兼容、env override 和 onboarding `health` 自检，不再要求第二位开发者手改源码才能接入。

## 显式配置 generic 日志

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/path/to/*.jsonl,$HOME/path/to/*.json"
export TOKEN_USAGE_DISCOVERY_ROOTS="$HOME/Library/Application Support,$HOME/.local/share"
python3 scripts/token_usage.py report --today --source generic-openai-compatible
```

## 自检与路径覆写

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/path/to/codex/sessions"
export TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="$HOME/path/to/claude/transcripts"
export TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="$HOME/path/to/local-agent-mode-sessions"
export TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="$HOME/Library/Application Support/Claude"
export TOKEN_USAGE_MINIMAX_AGENT_ROOT="$HOME/Library/Application Support/MiniMax Agent"
export TOKEN_USAGE_KIMI_DESKTOP_ROOT="$HOME/Library/Application Support/Kimi"
python3 scripts/token_usage.py health
```

Windows 常见写法例如：

```powershell
$env:TOKEN_USAGE_CODEX_ROOT="%USERPROFILE%\.codex\sessions"
$env:TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="%APPDATA%\Claude\local-agent-mode-sessions"
$env:TOKEN_USAGE_CLAUDE_DESKTOP_ROOT="%APPDATA%\Claude"
$env:TOKEN_USAGE_MINIMAX_AGENT_ROOT="%APPDATA%\MiniMax Agent"
$env:TOKEN_USAGE_GENERIC_LOG_GLOBS="%USERPROFILE%\logs\*.jsonl"
$env:TOKEN_USAGE_DISCOVERY_ROOTS="%APPDATA%,%LOCALAPPDATA%"
python .\scripts\token_usage.py health
```

## 输出形态

- 默认输出中文 ASCII-HIFI 终端控制面
- 默认带五级结构：`练气 / 筑基 / 金丹 / 元婴 / 化神`
- 主结论按 `日等效 / 缓存率 / 项目分布` 等可测信号判定；模型信息只做观测参考，不参与核心判断
- 主面板中的大数字默认用 `M / B` 紧凑单位展示；`JSON / diagnose / 明细场景` 保留精确整数
- 默认模型参考口径：`OpenAI GPT-5.3-Codex / GPT-5.4；Anthropic Opus 4.5 / Opus 4.6（核验日期：2026-03-25）`
- 默认总览已包含 `estimated cost`，但它永远只是本地价格表估算，不参与 exact 结论
- 默认最近趋势和本月分布右侧摘要会显示 `合计 + 估算费用 / 均值 / 最高`
- 支持 CLI 图形替代：
  - `--by day`
  - `--trend 7d|30d`
  - `--calendar month [--month YYYY-MM]`
  - `--current-session`
  - `--session <id>`
  - `--plain-ascii`
- 支持 `explore` 交互入口；非 TTY 下会提示改用纯命令参数
- 支持 `--format json`
- 当来源没命中时，必须显示诊断原因，不静默消失

## 对外入口与对内入口

- 对外入口：用户说自然语言需求
- 对内入口：skill 内部按需调用底层 CLI core

边界要明确：

- 不应该要求用户自己输入 `python3 ...`
- 不应该要求用户自己拼 `--trend / --calendar / --session`
- 这些都属于 skill 内部实现细节

## 退出与停止

这个 skill 不应该无限展开；用户一旦表达“先到这里”“够了”“不用继续”“停一下”，就应该收口。

退出触发词示例：

- “先这样”
- “够了”
- “不用继续”
- “先停”
- “先看到这里”

退出时的处理规则：

- 用 1 到 3 句收口总结当前已经确认的结果
- 如果还有明显下一步，只补一句“要继续的话，我下一步可以看 xxx”
- 不要在用户已经表示停止后继续追问细节
- 不要强推更多图表或更深层分析

## 验证门禁

- 至少跑通：
  - `health`
  - `report --today`
  - `sources`
  - `diagnose --source codex`
- 如果结果为 0，也必须给出“0 的原因”，而不是空白成功

## 参考文档

- `references/schema.md`
- `references/source-contract.md`
- `references/accuracy-policy.md`
- `references/model-benchmark-anchors.md`
