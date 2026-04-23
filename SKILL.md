---
name: "token-usage-universal"
description: "Translate natural-language requests about local AI token usage into the repo's standalone Python CLI (`scripts/token_usage.py`). Trigger when the user wants today's or recent local token usage, model/project/source/session comparisons, or diagnosis for why a local AI client is missing from counts; short triggers include `token`, `用量`, `消耗量`, `使用量`, `消耗`. Do not trigger for vendor billing pages, internet research, or remote/web-only analytics without local logs. Read local logs only and default to exact-first results. Before execution, gracefully handle intranet edge cases: GBK terminals, data paths that diverge from defaults, and multi-endpoint OpenCode (desktop + CLI + IDE plugin share one source)."
---

<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->
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

**第 1 步（happy path，**就一条命令**）**。用户说短触发词或询问今天 / 本周 token，**直接跑**：

```bash
python "$HOME/.opencode/skills/token.skill"*/scripts/token_usage.py report --today
```

关键：

- 用 **bash glob 绝对路径**，不要假设 cwd 是 skill 目录（opencode 常把 cwd 设成用户项目目录）。
- `token.skill*` 能匹配 `token.skill` / `token.skill v1.2` / 其他后缀变体，不要为目录名探路、ls、glob 找位置。
- **不要**先跑 `health` / `chcp` / `ls`——上面这条直接出面板；失败了才进下面的分支。
- Windows Git Bash 同样支持 `$HOME` 和 glob；PowerShell 环境下改用 `python "$env:USERPROFILE\.opencode\skills\token.skill\scripts\token_usage.py" report --today`。

按用户意图换命令（路径前缀不变）：

- 今天总览 → `report --today`（默认）
- 按模型/项目/来源 → `report --today --by model|project|source`
- 趋势 → `report --trend 7d` / `--trend 30d`
- 月历 → `report --calendar month`
- 当前会话 → `report --current-session`
- 排障 → `diagnose --source <source_id> --today`

**第 2 步：贴面板，补结论。** CLI 返回后，原样把 ascii-hifi 面板放进 fenced code block，补 1-3 句高信号结论，末句给可选展开方向。

**第 3 步：只在命令失败时才排障。** 上面那条命令成功就停，不要画蛇添足再跑 health。失败时按错误归类：

- `No such file or directory` → skill 目录不在默认路径，先跑 `ls ~/.opencode/skills/` 定位
- 中文乱码 / `UnicodeEncodeError` → [references/gbk-terminal.md](references/gbk-terminal.md)
- 结果 0 token 但用户说明明用了 → [references/path-discovery.md](references/path-discovery.md) + [references/multi-endpoint-scenarios.md](references/multi-endpoint-scenarios.md)
- 宿主不加载 skill 库 → [references/intranet-bootstrap.md](references/intranet-bootstrap.md)

**第 4 步：收口。** 用户说"先这样 / 够了 / 不用继续 / 先停"时，1-3 句收口，不追问。

路由细则：[references/skill-routing.md](references/skill-routing.md) · 来源契约：[references/source-contract.md](references/source-contract.md) · 精度：[references/accuracy-policy.md](references/accuracy-policy.md)

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

短触发词**一条绝对路径命令**直接出面板，不要先跑 health / chcp / ls；失败了才排障。
