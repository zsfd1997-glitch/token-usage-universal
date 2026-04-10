# task_plan

> 已替代：上一轮团队版任务主线已完成，本文件当前服务于 `top20-ecosystem-execution`。

## 输入 Input
- 目标: 按“模型生态/客户端家族”冻结 Top20，并开始执行 `Desktop + CLI + IDE` 的统一 token 统计平台建设。
- 约束: 中国国产生态优先；允许 `本地代理 / 自定义 base_url / 系统代理 / 可选 eBPF`；不做移动端和纯 Web。
- 假设: 后续阶段会持续获得真实客户端 fixture，用于把 `detect-ready` 逐步推进到 `exact-ready`。

## 处理 Process
- 路线选择: 采用 `native-client + provider-exact + ingress-capture` 三层并行架构。
- 技能链路: `workflow-superchain`
- 风险控制: 先落 registry 和 surface matrix，确保后续 adapter / health / ingress 共享同一套目标真源。

## 输出 Output
- 交付物:
  - Top20 registry 代码真源
  - Top20 execution plan 文档
  - Top20 surface matrix 文档
  - `targets` CLI
  - `release-gate` CLI
  - hostless evidence workflow
  - hostless evidence runner script
  - 对应测试
- 验收口径:
  - CLI 可直接输出冻结后的 Top20 registry
  - registry 总数为 20
  - 中国优先生态数为 13
  - 文档与 CLI 输出一致

## 成功标准
- [x] Phase 0 资产落地
- [x] CLI 可见
- [x] 回归验证通过
- [x] `Qwen Code CLI / Kimi CLI` 原生 exact 适配完成
- [x] `Gemini CLI` 原生 exact 适配完成
- [x] Top20 全生态 exact 适配完成
- [x] Phase 6 自动化 release gate 落地
- [x] Phase 1 契约测试加固完成
- [x] Phase 2 fixture 真源/diagnose 证据补齐完成
- [x] Phase 3 Linux 默认路径与 hostless ubuntu 链路落地
- [x] Phase 4 趋势化 evidence、价格核验时效、file cache 性能基线落地
- [x] Phase 5 COVERAGE / ENV 自动生成与 CI 漂移门禁落地
- [x] Part B skill 渐进披露重构完成

## 阶段链路
- DISCOVER: 已确认当前项目已有多 source 基础，但缺少 Top20 生态真源与统一执行主线。
- BRAINSTORM: 已确定按生态冻结、三层采集并行、国产优先。
- PLAN_PERSIST: 已落地主线文档、registry 和 surface matrix 资产。
- EXECUTE: 已新增 registry 模块、`targets` CLI、执行计划文档和 surface matrix。
- EXECUTE: 已新增 `qwen-code-cli / kimi-cli` adapter、env 契约、health 指引与专项测试。
- VERIFY: 已跑全量单测和 CLI 校验，最新为 `94` tests passing。
- POLISH_LOOP: 已清理 `targets` 文案与 README/ARCHITECTURE 引导。
- EXECUTE: 已新增 `openai / anthropic` 官方 ingress bootstrap profile，并把两条全球生态 IDE lane 推进到 `exact-ready`。
- VERIFY: 已跑全量单测和 `ingress profiles / ingress bootstrap / targets` 校验，最新为 `117` tests passing。
- EXECUTE: 已新增 `gemini / openrouter / perplexity / xai / mistral / stepfun` bootstrap profile，并把剩余全球生态 IDE lane 与多条 CLI ingress lane 推进到 `exact-ready`。
- EXECUTE: 已新增 `stepfun / sensenova / baichuan / siliconflow / spark / chatgpt / gemini / grok / mistral` 桌面端 source skeleton，并统一推进到 `detect-ready`。
- VERIFY: 已跑全量单测和 `health / ingress profiles / ingress bootstrap / targets` 校验，最新为 `122` tests passing。
- EXECUTE: 已新增 `qwen / kimi / glm / doubao / minimax` bootstrap profile，并把中国优先剩余 `Qwen / Kimi / GLM / Doubao / MiniMax` 的 IDE / CLI lane 推进到 `exact-ready`。
- VERIFY: 已跑全量单测和新增 profile 的 bootstrap 实跑，最新为 `126` tests passing；`ingress profiles` 已扩到 `22` 个，`surface_maturity.exact-ready` 已到 `50`。
- EXECUTE: 已新增 `gemini-cli` adapter 与 `TOKEN_USAGE_GEMINI_CLI_ROOT` 契约，并把 `StepFun / SenseNova / Baichuan / SiliconFlow / Spark / ChatGPT / Gemini / Grok / Mistral` 的 desktop fixture 补齐后统一升到 `exact-ready`。
- VERIFY: 已跑全量单测、`health / targets / ingress profiles` 实跑，以及临时 fixture 驱动的 `gemini-cli report`；随后继续补上 `opencode` 本地 exact 真源，最新为 `136` tests passing，`supported_sources = 50`，`ready_sources = 3`，Top20 `surface_maturity.exact-ready = 60`。
- EXECUTE: 已新增强化版 `release-gate`：覆盖结构性误报、默认 report runtime duplicate probe、full root-aware source platform matrix，并接入 `build_release.py --validate` 自动门禁。
- VERIFY: 已实跑 `python3 scripts/token_usage.py release-gate --format json`，当前 `7/7 gates passed`；全量回归已到 `143` tests passing。
- EXECUTE: 已新增 `.github/workflows/hostless-evidence.yml` 和 `examples/vm-testing/run-hostless-evidence.sh`，把“没有本地 Windows/macOS host”时的双平台 smoke/evidence 采集切到 GitHub-hosted runners。
- VERIFY: 已真实触发 `hostless-evidence`；首轮确认 `macos-latest` 可成功产出 evidence，而 `windows-latest` 会因 `US/Pacific` 在无 tzdata 环境下不可解析而失败。
- EXECUTE: 已补 `resolve_timezone` 的 legacy US alias fallback，新增 `test_time.py / test_time_window.py`，并把多处测试切到仓库内兼容 helper；同时收紧 workflow artifact 上传条件，避免二次噪音错误。
- VERIFY: 已跑全量单测与 `release-gate`，最新为 `155` tests passing，`7/7 gates passed`。
- EXECUTE: 已修复 Windows hosted runner 上 CLI 子进程中文 JSON 输出的 legacy codec 问题，并新增 `cp1252` 回归测试。
- EXECUTE: 已把 `test_cli_integration.py` 统一改成显式 `stdout/stderr PIPE + encoding='utf-8'`，消除 Windows hosted runner 的平台差异假阳性。
- VERIFY: 已再次跑全量单测与 `release-gate`，最新为 `158` tests passing，`7/7 gates passed`。
- EXECUTE: 已新增 `test_skill_guidance_contract / test_sources_contract / test_env_registry_contract / test_generated_docs_contract / test_release_gate_baseline`，并把默认面板骨架、退出词、周/月引导、source/source_id 契约、生成文档漂移与 baseline diff 固定成测试。
- EXECUTE: 已补齐 `scripts/fixtures/provider/*` 的全量 provider family `exact + diagnose` fixtures，以及 `scripts/fixtures/desktop/*` 的 chromium/native desktop fixtures。
- EXECUTE: 已把 `release-gate` 升级为输出 `source_states / source_state_summary / baseline diff`，证据包新增 `diff.json`，`SUMMARY.md` 固定展示 `exact / diagnose / unsupported` 计数。
- EXECUTE: 已给 `pricing_db.json` 增加 `verified_at`，给 `file_cache` 增加 `1000 session` 性能基线，并新增 `docs/COVERAGE.md / docs/ENV.md` 自动生成脚本与 CI `--check` 门禁。
- VERIFY: 已再次跑 `python3 -m unittest discover -s scripts -t . -p 'test_*.py'`，最新为 `189` tests passing。
- VERIFY: 已实跑 `python3 scripts/token_usage.py health --format json`、`sources --format json`、`release-gate --format json` 与 `release-gate --baseline <bundle> --output-dir <bundle>`；当前 `supported_sources = 50`、`ready_sources = 4`、`7/7 gates passed`、baseline diff 为 `50 unchanged / 0 regressed`。
- EXECUTE: 已把 repo `SKILL.md` 重构为轻量门面，并拆出 `references/skill-routing.md` / `references/skill-output-contract.md`；README 同步指向新的渐进披露结构。
- VERIFY: 已跑 `python3 -m unittest scripts.test_skill_contract scripts.test_skill_guidance_contract`、`python3 -m unittest scripts.test_env_registry_contract scripts.test_generated_docs_contract`、skill `quick_validate` 与全量 `191` tests passing。
- SHIP: 当前为仓库内阶段性交付，不做远端发布。
- HANDOFF: Phase 1-5 与 Part B skill refactor 当前已在仓库内完成；后续主线只剩真实多机 E2E 和更多桌面 token-bearing 样本采集。
