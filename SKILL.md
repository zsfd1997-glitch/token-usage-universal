---
name: "token-usage-universal"
description: "Translate natural-language requests about local AI token usage into the repo's standalone Python CLI (`scripts/token_usage.py`). Trigger when the user wants today's or recent local token usage, model/project/source/session comparisons, or diagnosis for why a local AI client is missing from counts; short triggers include `token`, `用量`, `消耗量`, `使用量`, `消耗`. Do not trigger for vendor billing pages, internet research, or remote/web-only analytics without local logs. Read local logs only and default to exact-first results."
---

# Token Usage Universal

Treat this skill as the natural-language wrapper for the standalone Python CLI at `scripts/token_usage.py`.

## Keep The Product Boundary Clear

- Treat the product as `独立 Python CLI + SKILL 包装层`, not as an abstract framework.
- Translate user intent into CLI calls; do not ask the user to compose flags manually.
- Prefer the smallest command that answers the question.
- Keep replies Chinese-first, result-first, and simple.

## Route The Request

- Use `report` for totals, trends, model/project/source breakdowns, and current-session views.
- Use `diagnose` when the user asks why a source or client was not counted.
- Use `sources` or `health` only when they help explain support state or missing paths.
- Treat short trigger words as "show today's overview first", not as a clarification loop.
- Load [skill-routing.md](references/skill-routing.md) when the phrasing is vague, when you need the default guidance flow, or when you need example utterances and command bias.

## Format The Answer

- Put the `ascii-hifi` panel first whenever the CLI already returned one.
- Downgrade to pure text only when the user explicitly asks for it or when the panel cannot be rendered cleanly.
- Stop expanding when the user says enough.
- Load [skill-output-contract.md](references/skill-output-contract.md) for the fixed panel skeleton, plain-text downgrade rules, exit phrases, and validation gate.

## Load Extra Truth Only When Needed

- Load [source-contract.md](references/source-contract.md) when you need `source_id`, provider-family split, or source-state truth.
- Load [accuracy-policy.md](references/accuracy-policy.md) when you need `exact / diagnose / unsupported` boundaries or cost-estimation rules.
- Load [model-benchmark-anchors.md](references/model-benchmark-anchors.md) only when you need the fixed benchmark model names used in output.
- Load [COVERAGE.md](docs/COVERAGE.md) or [ENV.md](docs/ENV.md) when you need the generated support list or env registry.
- Keep this file lean; do not duplicate long source/env inventories here.

## Preserve The Contract

- Report `exact` when exact local truth exists.
- Report `diagnose` or `unsupported` plainly when exact truth does not exist.
- Explain why a result is empty or zero; do not present an empty success.
- Keep `generic-openai-compatible` as fallback or diagnose material rather than the default rollup truth.
