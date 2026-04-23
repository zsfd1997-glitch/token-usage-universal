---
name: "token-usage-universal"
description: "Translate natural-language requests about local AI token usage into the repo's standalone Python CLI (`scripts/token_usage.py`). Trigger when the user wants today's or recent local token usage, model/project/source/session comparisons, or diagnosis for why a local AI client is missing from counts; short triggers include `token`, `用量`, `消耗量`, `使用量`, `消耗`. Do not trigger for vendor billing pages, internet research, or remote/web-only analytics without local logs. Read local logs only and default to exact-first results. Before execution, gracefully handle intranet edge cases: GBK terminals, data paths that diverge from defaults, and multi-endpoint OpenCode (desktop + CLI + IDE plugin share one source)."
---

# Token Usage Universal

## 核心提示词

你的任务是把用户说的人话翻成正确的本地 CLI 调用，再把结果按固定协议回出来。

真正负责统计和诊断的是 `scripts/token_usage.py`；这个 skill 的工作是翻译意图、选择最小命令、把 ascii-hifi 面板原样贴出来，再补 1 到 3 句高信号结论。不推测没有本地真源的数字，不让用户自己拼参数，不把面板翻译成项目符号摘要。

## 什么时候调用

适合调用：

- 用户问"今天 / 本周 / 最近 token 用量多少"
- 用户问"哪个模型 / 项目 / 来源最费 token"
- 用户问"为什么 Claude / Codex / OpenCode / 其他桌面端没统计到"
- 用户只说 `token / 用量 / 消耗量 / 使用量 / 消耗`（默认先给今天总览）
- 用户要求一个本地优先、exact-first 的 token 查询入口

不适合调用：

- 用户想看云端账单页或供应商 dashboard
- 手里没有本地日志，只想估算未来用量
- 用户在问和本机无关的通用 LLM 费用计算器

## 输入

调用前至少具备：

- 一个明确的时间窗口或查询方向（今天 / 本周 / 按模型 / 按来源）
- 本机至少一个已支持来源的日志可读（运行 `health` 确认）
- 如果是排障，需要知道哪个来源没出现在统计里

内网四项前置自检（任一命中**先处理再执行**，优先级：宿主 → 编码 → 路径 → 多端归因）：

- **宿主没装 skill 库**（opencode 桌面端 / 自研 CLI / 私有 launcher）→ [references/intranet-bootstrap.md](references/intranet-bootstrap.md)
- **终端只认 GBK 不认 UTF-8**（Windows `chcp` 返回 `936`）→ [references/gbk-terminal.md](references/gbk-terminal.md)
- **默认路径在本机不成立** → `not_found` 不等于没用量，先探测：[references/path-discovery.md](references/path-discovery.md)
- **同机多端 / IDE 内嵌 / 自定义 base_url** → [references/multi-endpoint-scenarios.md](references/multi-endpoint-scenarios.md)

## 输出

必须同时包含：

- 先输出 `ascii-hifi` 面板（fenced code block），再补结论
- 总 token 和去缓存后 token（两者明确区分，不允许只给裸数字）
- 当前来源状态：`exact / diagnose / unsupported` 三级之一
- 如果结果为零，必须给出"为什么是零"的原因，不允许空白成功
- 可选展开方向：一句"要继续的话，我再拆模型 / 项目 / 当前会话"

## 验收标准

同时满足以下条件才算完成：

- 用户看完能直接知道今天 token 花在哪、多少是真实消耗、多少是缓存命中
- 每条来源状态都能追到本地日志路径或诊断原因
- 面板没有被翻译成等价的项目符号摘要冒充输出
- 没有真源的来源没有被猜成 exact 数字
- 用户说"先停"后已经收口，没有继续追问细节

## 执行协议

**第 1 步：确认来源状态。** 必要时跑：

```bash
python3 scripts/token_usage.py health
```

如果大部分来源 `not_found` / `no_data`，**不要**直接得出"没用量"——先按 [references/path-discovery.md](references/path-discovery.md) 探测：`health --format json` 看解析后绝对路径 → `sources` 看不 ready 原因 → `find` / `Get-ChildItem` 搜特征文件 → 用 `TOKEN_USAGE_<SOURCE>_ROOT` / `TOKEN_USAGE_DISCOVERY_ROOTS` 覆盖 → 重跑 health。

**第 2 步：选最小命令。** 按用户意图选命令——

- 今天总览：`report --today`
- 按模型 / 项目 / 来源拆分：`report --today --by model|project|source`
- 最近趋势：`report --trend 7d`
- 月历热力图：`report --calendar month`
- 当前会话：`report --current-session`
- 来源排障：`diagnose --source <source_id> --today`
- 来源状态总览：`sources`

**第 3 步：贴面板，补结论。** CLI 返回 ascii-hifi 面板后，先原样放进 fenced code block，再补 1 到 3 句高信号结论，最后一句给可选展开方向。GBK 终端三级降级（Tier 1 `chcp 65001` → Tier 1.5 `PYTHONIOENCODING=gbk:backslashreplace` → Tier 2 `--format json` + skill 端英文重绘 → Tier 3 `--plain-ascii` + 英文标签，禁止中英混排）详见 [references/gbk-terminal.md](references/gbk-terminal.md)。

**第 4 步：收口。** 用户说"先这样 / 够了 / 不用继续 / 先停 / 先看到这里"时，用 1 到 3 句收口总结，不再追问。

引导细则和默认面板骨架见 [references/skill-routing.md](references/skill-routing.md)。  
来源契约和 exact / diagnose / unsupported 边界见 [references/source-contract.md](references/source-contract.md)。  
精度口径和费用估算规则见 [references/accuracy-policy.md](references/accuracy-policy.md)。

## 禁忌

- 禁止把 ascii-hifi 面板翻译成等价的项目符号摘要后冒充原面板
- 禁止在用户只说短触发词时返回一个裸数字
- 禁止一上来反问一长串选项，让用户自己拼 `--trend / --calendar / --session`
- 禁止在没有本地真源时把估算数字冒充 exact
- 禁止在用户说"先这样 / 够了"之后继续追问细节或推图表
- 禁止把 `generic-openai-compatible` 当作默认总览的主要来源
- 禁止假设宿主已加载过 SKILL.md；内网 opencode / 自研 CLI 常常没装 skill 库，首轮必须先确认或手动 bootstrap
- 禁止在默认路径 `not_found` 时直接得出"今天没用量"的结论；一律先路径探测
- 禁止在 GBK 终端直接贴 UTF-8 面板；未确认终端编码前不要输出中文面板
- 禁止在 GBK 降级场景下中英混排输出（GBK 终端只能稳渲 ASCII）
- 禁止把 `opencode.exe` / `opencode-cli.exe` / IDE 插件拆成多条 source 报数；共享同一条 `opencode` source
- 禁止对 `trae` source 反复 diagnose 期望拿到 exact token；DB 加密，只能走 ingress 劫持 base_url

## 一句话操作口令

先自检（宿主 / 编码 / 路径 / 多端），再选最小命令，先贴面板再补结论，用户停手就收口。
