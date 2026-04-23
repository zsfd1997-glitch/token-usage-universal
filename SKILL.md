---
name: "token-usage-universal"
description: "Local AI token usage reporter. Trigger when the user mentions `token`, `用量`, `消耗量`, `使用量`, `消耗`, or asks how many tokens were used today / by which model / by which project. Default action is `python3 scripts/token_usage.py report --today`; paste the returned ascii-hifi panel and add 1-3 sentences of conclusion. Do not trigger for vendor billing pages or cloud dashboards. Reads local client logs (Codex, Claude Code, OpenCode, Gemini/Kimi CLI, Chromium-family desktop apps) only — exact-first, never estimated. Supports Windows GBK terminals and intranet hosts where data paths diverge from defaults."
---

# Token Usage Universal

## What I do

Turn natural-language token-usage questions into one `scripts/token_usage.py` command, then paste the ascii-hifi panel back with a 1-3 sentence conclusion. I do not estimate, do not reinterpret panels, do not ask users to pick flags.

## When to use me

Trigger me when the user says any of:

- `token` / `用量` / `消耗量` / `使用量` / `消耗` (short triggers → today's overview by default)
- "今天/本周/最近 token 用量多少"
- "哪个模型/项目/来源最费 token"
- "为什么 Claude / Codex / OpenCode / 某某桌面端没统计到"

Do **not** trigger me for: vendor billing pages, cloud dashboards, future-usage estimators, generic LLM cost calculators, anything that doesn't read local logs.

## How I work (happy path)

Four steps. Do them in order. Do not ask clarifying questions on short triggers — run the default.

**Step 1. Run the default command.** For short triggers, run exactly:

```bash
python3 scripts/token_usage.py report --today
```

For other intents, pick from this table:

| User said | Command |
|---|---|
| 今天/当前总量 | `report --today` |
| 本周/最近 / "最近几天" | `report --trend 7d` or `report --last 7d` |
| 按模型/项目/来源拆 | `report --today --by model`（或 `project` / `source`） |
| 当前会话 | `report --current-session` |
| 月历热力图 | `report --calendar month` |
| 某来源没统计到 | `diagnose --source <source_id> --today` |
| 来源就绪状态总览 | `sources` 或 `health` |

**Step 2. Paste the ascii-hifi panel.** The CLI returns a panel (box-drawing text). Put it in a fenced code block **verbatim** — do not summarize, do not translate to bullets, do not drop lines.

**Step 3. Add 1-3 sentence conclusion.** Under the panel:

- Which model / project / source drove the number
- 总 token vs 去缓存后 token 差异大不大
- 一句可选展开方向（"要再拆模型/项目/当前会话，就说一声"）

**Step 4. Stop when user says stop.** "先这样" / "够了" / "不用继续" / "先停" / "先看到这里" → 1-3 句收口，不追问。

## Output contract (must hold every time)

- Panel goes into a fenced code block, first, before any prose
- 总 token and 去缓存后 token stated separately — no naked numbers
- Source status is one of `exact / diagnose / unsupported` — no "probably"
- If total is 0, explain why (no sessions today / source not_found / GBK file read failed) — never silent-success
- Costs are always local-price-table estimates, never a billing claim

## When something's off (degradation branches)

Check these only if the happy path fails or the user explicitly signals trouble:

- **`health` shows most sources `not_found`** → default paths miss real data. Do not conclude "no usage"; follow [references/path-discovery.md](references/path-discovery.md) to locate and env-override.
- **Output is garbled / terminal is GBK** (`chcp` returns `936` or chars render as `鍘熷緥`) → three-tier degradation in [references/gbk-terminal.md](references/gbk-terminal.md). Prefer Tier 1.5 (`PYTHONIOENCODING=gbk:backslashreplace`) or Tier 2 (`--format json` + re-render in ASCII).
- **OpenCode reports 0 despite active use** → adapter may need multi-endpoint config (desktop + `opencode-cli.exe` + IDE plugin share one source). See [references/multi-endpoint-scenarios.md](references/multi-endpoint-scenarios.md) and `diagnose --source opencode` for verification_issues.
- **Host has no skills loader at all** (pure chat shell) → bootstrap with `python3 scripts/token_usage.py bootstrap-prompt` or see [references/intranet-bootstrap.md](references/intranet-bootstrap.md).

Routing, source contract, and accuracy policy details: [skill-routing.md](references/skill-routing.md) · [source-contract.md](references/source-contract.md) · [accuracy-policy.md](references/accuracy-policy.md).

## Forbidden

- Do not translate the ascii-hifi panel into bullets and claim it's equivalent output
- Do not return a naked number for a short trigger — always panel first
- Do not ask the user to pick `--trend / --calendar / --session` flags; pick for them
- Do not estimate when local exact data is missing — say it's missing
- Do not keep pushing more charts after user says stop
- Do not default-promote `generic-openai-compatible` as a main source
- Do not split `opencode.exe` / `opencode-cli.exe` / IDE plugin into separate sources — they share one `opencode` source
- Do not paste UTF-8 Chinese output directly to a GBK terminal — confirm encoding first
- Do not keep running `diagnose --source trae` expecting exact tokens — trae DB is encrypted, ingress is the only path
- Do not conclude "0 tokens today" when default paths show `not_found` — discovery first

## One-line mnemonic

短触发词直接跑 `report --today`；面板先贴，结论后补 1-3 句；用户说停就停。
