<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# Skill Routing

Use this file when the user's phrasing is vague and you need the default mapping from natural language to `scripts/token_usage.py`.

## Short Triggers

用户只说“token / 用量 / 消耗量 / 使用量 / 消耗”，默认就应该触发这个 skill。

- “token”
- “用量”
- “消耗量”
- “使用量”
- “消耗”

这些短词默认理解成“先看今天总览”，而不是回一句解释性废话。

## Intent To Command Bias

- 看今天 / 当前总量 -> `report --today`
- 看最近趋势 -> `report --trend 7d`、`report --trend 30d` 或同窗口总览
- 看哪个模型最费 -> `report <window> --by model`
- 看哪个项目最费 -> `report <window> --by project`
- 看当前会话 -> `report --current-session`
- 查某个来源为什么没统计到 -> `diagnose --source <source-id>`
- 看来源清单 / ready 状态 -> `sources` 或 `health`

优先走最窄、最直接的命令，不要先把 `health + sources + diagnose + report` 全打一遍。

## Common Utterances

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

## Guidance When The User Is Vague

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

## Keep Guidance Tight

- 先给一个默认答案，再补一句可继续展开的方向。
- 不要一上来反问一长串。
- 不要把 `--trend / --calendar / --session` 这种实现细节丢给用户自己选。
