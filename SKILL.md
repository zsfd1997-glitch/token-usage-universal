---
name: "token-usage-universal"
description: "Use when the user asks to view local token usage, summarize today's or recent usage, compare sources/projects, or diagnose why a local AI client is not being counted. Reads local logs only and defaults to exact results."
---

# Token Usage Universal

一个本地优先、准确优先、来源优先的通用 token usage skill。

## 成品形态

- 对外成品: `token-usage-universal skill`
- 内部实现: `scripts/token_usage.py` 这个 deterministic CLI core
- v1 决策: 不把它作为独立品牌 CLI 单独发布；CLI 只作为 skill 的稳定运行时和后续可提取边界
- `Task Master` 关系: 仅是可选规划工具，不是运行时依赖，也不是发布门槛

## 何时使用

- 用户问“今天 token 用量多少”
- 用户问“最近 7 天 token 用量”
- 用户问“按来源 / 按项目统计 token”
- 用户问“为什么 Claude / Codex / 其他客户端没统计到”
- 用户要求一个极简、可推广、基于本地日志真源的 usage 统计能力

## 原则

1. `Local-first`
- 默认只读本地日志，不联网。

2. `Exact-first`
- 默认只输出 `exact`。
- 没有本地真源时，不猜，不估算，直接标成 `unsupported` 或 `not configured`。

3. `Source-first`
- 以日志来源适配，不以模型名适配。

## 快速命令

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export TOKEN_USAGE_SKILL="$CODEX_HOME/skills/token-usage-universal"

python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today --by model
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --last 7d --by source
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today --by project
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" sources
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" diagnose --source codex --today
```

如果老板后续要把它抽成独立 CLI，应该复用这套 CLI contract，而不是再造一套并行产品入口。

## 当前支持

- `codex`: `exact`
  - 读取 `~/.codex/sessions/**/*.jsonl`
  - 基于 `token_count.info.total_token_usage` 的累计变化量精确统计
- `generic-openai-compatible`: `exact` when configured
  - 通过 `TOKEN_USAGE_GENERIC_LOG_GLOBS` 显式指定日志文件 glob
  - 只接受带明确 usage 数值和时间戳的 JSON / JSONL
- `claude-code`: `exact` when `timing.json` was captured, otherwise `diagnose`
  - 优先读取 `~/Library/Application Support/Claude/local-agent-mode-sessions/**/timing.json`
  - 该真源可精确提供 `total_tokens` 与完成时间，但通常不含 `input/output/cache` 拆分
  - 只有 transcript、没有 `timing.json` 时，明确降级，不输出伪精确数据

## 当前可复用性结论

- 别人现在可以直接复用 `codex` 路径能力，只要本机也使用标准 `~/.codex/sessions`。
- `generic-openai-compatible` 也能复用，但需要自己配置 `TOKEN_USAGE_GENERIC_LOG_GLOBS`。
- `claude-code` 当前更偏 `macOS` 本地用户，因为默认真源路径指向 `~/Library/Application Support/Claude/...`，但现在支持 env override。
- 结论：这个 skill 现在已经具备 env override + onboarding `health` 自检，不再要求第二位开发者手改源码才能接入。

## 显式配置 generic 日志

```bash
export TOKEN_USAGE_GENERIC_LOG_GLOBS="$HOME/path/to/*.jsonl,$HOME/path/to/*.json"
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" report --today --source generic-openai-compatible
```

## 自检与路径覆写

```bash
export TOKEN_USAGE_CODEX_ROOT="$HOME/path/to/codex/sessions"
export TOKEN_USAGE_CLAUDE_TRANSCRIPT_ROOT="$HOME/path/to/claude/transcripts"
export TOKEN_USAGE_CLAUDE_LOCAL_AGENT_ROOT="$HOME/path/to/local-agent-mode-sessions"
python3 "$TOKEN_USAGE_SKILL/scripts/token_usage.py" health
```

## 输出形态

- 默认输出中文 ASCII-HIFI 报表
- 默认带五级结构：`练气 / 筑基 / 金丹 / 元婴 / 化神`
- 主结论按 `日等效 / 缓存率 / 项目分布` 等可测信号判定；模型信息只做观测参考，不参与核心判断
- 主面板中的大数字默认用 `M / B` 紧凑单位展示；`JSON / diagnose / 明细场景` 保留精确整数
- 默认模型参考口径：`OpenAI GPT-5.3-Codex / GPT-5.4；Anthropic Opus 4.5 / Opus 4.6（核验日期：2026-03-25）`
- 支持 `--format json`
- 当来源没命中时，必须显示诊断原因，不静默消失

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
