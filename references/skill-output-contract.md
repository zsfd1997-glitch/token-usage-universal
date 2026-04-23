<!-- Copyright (c) 2026 token.skill v1.1 -->
<!-- SPDX-License-Identifier: MIT -->

# Skill Output Contract

Use this file when formatting the final chat answer, deciding whether to stay in panel mode, or deciding whether to stop.

## Default Artifact

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

## Panel-First Rules

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
- 最近趋势
- 月历热力图

默认展示口径：

- `费用` 默认按“去缓存后 token”估算，不把缓存 token 算进费用里
- 模型 / 项目 / 趋势 / 月历默认优先看“去缓存后 token”
- 如果同时展示 `总 token`，要把它和 `去缓存后 token` 明确区分开，不允许只丢一个裸数字

推荐的默认回复骨架：

1. 先输出 `ascii-hifi` 面板
2. 再补 1 到 3 句高信号结论
3. 最后补一句可选展开方向，例如“要继续的话，我再拆模型 / 项目 / 当前会话”

## Plain-Text Downgrade

只有当用户明确说下面这些话，才允许降级成不带图的简版说明：

- “看不懂图”
- “简单说”
- “先给结论”
- “不用图”
- “纯文字版本”

## Exit And Stop

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

## Validation Gate

- 至少跑通：`health`
- 至少跑通：`report --today`
- 至少跑通：`sources`
- 至少跑通：`diagnose --source codex`
- 如果结果为 0，也必须给出“0 的原因”，而不是空白成功
