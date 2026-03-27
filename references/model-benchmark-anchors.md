# 最新模型口径与官方案例锚点

核验日期：`2026-03-25`

## 最新模型口径

### OpenAI / Codex
- [Introducing GPT-5.4](https://openai.com/index/introducing-gpt-5-4/)
  - 发布日期：`2026-03-05`
  - 官方口径：`GPT-5.4` 正在 `ChatGPT, the API, and Codex` 推出，并吸收 `GPT-5.3-Codex` 的 frontier coding capabilities。
- [GPT-5.3-Codex System Card](https://deploymentsafety.openai.com/gpt-5-3-codex/gpt-5-3-codex.pdf)
  - 发布日期：`2026-02-05`
  - 官方口径：`GPT-5.3-Codex` 被定义为当时最强的 agentic coding model。

### Anthropic / Claude Code
- [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
  - 核验日期：`2026-03-25`
  - 官方口径：最新模型对比列出 `Claude Opus 4.6`、`Claude Sonnet 4.6`、`Claude Haiku 4.5`，其中 `Opus 4.6` 被描述为最新一代、适合 coding 与 reasoning 的模型。
- [Model system cards](https://www.anthropic.com/system-cards/)
  - 官方口径：公开列出 `Claude Opus 4.6`（`2026-02`）与 `Claude Opus 4.5`（`2025-11`）的 system cards。
- [Manage costs effectively](https://code.claude.com/docs/en/costs)
  - 核验日期：`2026-03-25`
  - 官方口径：Claude Code 成本页当前以 `Sonnet 4.6` 作为平均成本说明口径。

## 官方案例

### OpenAI
- 来源机构：OpenAI
  - 事件日期：`2026-03-05`
  - 来源链接：[Introducing GPT-5.4](https://openai.com/index/introducing-gpt-5-4/)
  - 原始口径类型：直接事实
  - 说明：`GPT-5.4` 已进入 `Codex`，并吸收 `GPT-5.3-Codex` 的 coding 能力。
- 来源机构：OpenAI
  - 事件日期：`2025 report`
  - 来源链接：[The state of enterprise AI 2025 report](https://openai.com/business/guides-and-resources/the-state-of-enterprise-ai-2025-report/)
  - 原始口径类型：直接事实
  - 说明：超过 `9,000` 个组织处理过 `100 亿+` tokens，近 `200` 个组织超过 `1 万亿` tokens。
- 来源机构：OpenAI
  - 事件日期：`2025-10-06`
  - 来源链接：[Codex is now generally available](https://openai.com/index/codex-now-generally-available/)
  - 原始口径类型：直接事实
  - 说明：OpenAI 官方写明“几乎所有工程师都在用 Codex”，并披露 `GPT-5-Codex` 上线后三周已服务 `40 万亿+` tokens。

### Anthropic
- 来源机构：Anthropic
  - 事件日期：`accessed 2026-03-25`
  - 来源链接：[Manage costs effectively](https://code.claude.com/docs/en/costs)
  - 原始口径类型：直接事实
  - 说明：Claude Code 平均每位开发者每天约 `$6`，`90%` 用户低于 `$12/day`，团队月均成本说明以 `Sonnet 4.6` 为口径。
- 来源机构：Anthropic
  - 事件日期：`accessed 2026-03-25`
  - 来源链接：[Manage costs effectively](https://code.claude.com/docs/en/costs)
  - 原始口径类型：直接事实
  - 说明：团队 TPM 建议为 `1-5 用户 200k-300k TPM/user`，`500+ 用户 10k-15k TPM/user`。
- 来源机构：Anthropic
  - 事件日期：`accessed 2026-03-25`
  - 来源链接：[Rakuten customer story](https://claude.com/customers/rakuten)
  - 原始口径类型：直接事实
  - 说明：Rakuten 披露 Claude Code 实现过 `7 小时` 持续自治编码，并把新功能平均上市时间从 `24 天` 压到 `5 天`。
- 来源机构：Anthropic
  - 事件日期：`accessed 2026-03-25`
  - 来源链接：[Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
  - 原始口径类型：直接事实
  - 说明：最新模型对比页明确展示 `Opus 4.6 / Sonnet 4.6 / Haiku 4.5`，用于当前 Claude Code 语境下的模型锚点。

## 等级映射

| 等级 | 日等效 token | 岗位对标 | 典型团队场景 | 参考模型 | 商务解释 |
|---|---:|---|---|---|---|
| `练气` | `< 10M/day` | 初级工程师 / 普通员工 | 轻量、日常、基础辅助 | Claude Code Sonnet 4.6 | 适合建立基础使用习惯，把 AI 纳入查询、拆解和轻量编码。 |
| `筑基` | `10M - < 100M/day` | 中级工程师 | 稳定进入工程主流程 | Claude Opus 4.5 / Sonnet 4.6 | 代表 AI 已稳定进入日常工程流程。 |
| `金丹` | `100M - < 500M/day` | 资深工程师 | 高强度个人生产 | GPT-5.3-Codex / Claude Opus 4.6 | 适合持续编码、测试、重构与方案比对。 |
| `元婴` | `500M - < 2B/day` | Staff / Tech Lead | 多线程、高密度交付 | GPT-5.4 / Claude Opus 4.6 | 更适合多线工作流、并行实验和跨项目交付。 |
| `化神` | `>= 2B/day` | Principal / AI 平台负责人 | 平台级、组织级火力 | GPT-5.4 + 公司级 Claude Code / agent 编排 | 更接近组织级 AI 工程能力，不再是单个工程师的常规强度。 |
