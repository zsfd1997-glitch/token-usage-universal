# findings

> 已替代：上一轮团队版 findings 已结束；当前文件记录 `top20-ecosystem-execution` 的关键证据。

## 证据 Evidence
- Top20 registry 真源已落地在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py)。
- CLI 已新增 `targets` 命令，入口在 [token_usage.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/token_usage.py)。
- ASCII 终端层已能直接展示 Top20 registry，实现在 [ascii_hifi.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/ascii_hifi.py)。
- 人类可读执行计划与矩阵已落地在：
  - [TOP20_EXECUTION_PLAN.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_EXECUTION_PLAN.md)
  - [TOP20_SURFACE_MATRIX.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/TOP20_SURFACE_MATRIX.md)
- 测试已覆盖 registry 和 CLI：
  - [test_ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_ecosystem_registry.py)
  - [test_cli_integration.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_cli_integration.py)
- Phase 1 第一批 provider exact pack 已落地在 [compatible_api_family.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/compatible_api_family.py)：
  - `sensenova-api`
  - `baichuan-api`
  - `siliconflow-api`
  - `spark-api`
- provider adapter 测试已覆盖嵌套 `usage`、endpoint/base_url 识别、cached/reasoning token 归一化，见 [test_provider_api_adapters.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_provider_api_adapters.py)
- `Qwen Code CLI` 原生适配已落地在 [qwen_code_cli.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/qwen_code_cli.py)，测试见 [test_qwen_code_cli.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_qwen_code_cli.py)。
- `Kimi CLI` 原生适配已落地在 [kimi_cli.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/kimi_cli.py)，测试见 [test_kimi_cli.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_kimi_cli.py)。
- `Claude Code` 现已扩展到新布局 `~/.claude/projects/**/*.jsonl`：会直接从 assistant `message.usage` 提取 `input / cache / output / total token`，实现位于 [claude_code.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/claude_code.py)，测试见 [test_claude_code.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_claude_code.py)。
- `Qwen / Kimi` 两条 CLI surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- Chromium/Electron 桌面端 exact 底座已升级为同时读取 `Cache_Data / IndexedDB / Local Storage`，核心实现在 [chromium_desktop.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/chromium_desktop.py) 和 [chromium_cache.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/chromium_cache.py)。
- `GLM / Doubao / Perplexity` 三条桌面端原生适配已落地在 [chromium_desktop_family.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/chromium_desktop_family.py)，专项测试见 [test_chromium_desktop_adapters.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_chromium_desktop_adapters.py) 和 [test_chromium_cache.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_chromium_cache.py)。
- `GLM / Doubao / Perplexity` 三条桌面端 surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- `DeepSeek / Qianfan / Yuanbao` 三条桌面端原生适配已落地在 [chromium_desktop_family.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/chromium_desktop_family.py)，专项测试同样覆盖在 [test_chromium_desktop_adapters.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_chromium_desktop_adapters.py)。
- `DeepSeek / Qianfan / Yuanbao` 三条桌面端 surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- `Claude Desktop` 现已增加模型痕迹观测层：即使当前没有 exact token payload，也会从 `IndexedDB / Local Storage / Session Storage` 补抓 `claude-sonnet / haiku / opus` 等模型痕迹，实现在 [claude_desktop.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/claude_desktop.py)。
- report 聚合层与 ASCII 面板现已新增“已观测来源 / 已观测模型（未计入 token）”分栏，证据链在 [aggregator.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/aggregator.py) 和 [ascii_hifi.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/ascii_hifi.py)，测试见 [test_reporting.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_reporting.py)。
- `ingress companion` 最小可用实现已落地在 [ingress_companion.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ingress_companion.py)，CLI 入口在 [token_usage.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/token_usage.py)，专项测试见 [test_ingress_companion.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_ingress_companion.py)。
- `ingress bootstrap` 与 profile catalog 已落地在 [ingress_bootstrap.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ingress_bootstrap.py)，CLI 入口同样在 [token_usage.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/token_usage.py)，专项测试见 [test_ingress_bootstrap.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_ingress_bootstrap.py)。
- `release-gate` 自动门禁已落地在 [release_gate.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/release_gate.py)，CLI 入口同样在 [token_usage.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/token_usage.py)，专项测试见 [test_release_gate.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_release_gate.py)。
- `release-gate` 现在会实跑默认 report 的重复计数 probe：同一份临时 exact log 同时命中 provider family 与 `generic-openai-compatible` 时，默认 report 仍保持 `0.0%` duplicate，而显式把 generic 拉进来时 probe 会看到重复。
- `release-gate` 现在也会验证全部 `25/25` root-aware source 的 `Windows + macOS` 默认根路径矩阵，而不再只看少数代表来源。
- `release-gate --output-dir ...` 现在会导出真实机器证据包，包含 `release_gate.json / health.json / sources.json / targets.json / report_today.json / report_recent_30d.json / diagnose/*.json / SUMMARY.md`。
- 发布导出脚本已接入 `--validate` 自动门禁，实现在 [build_release.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/build_release.py)。
- “无 host 环境”的替代链路已落地在 [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml)，会在 `windows-latest + macos-latest` 上跑单测和 `release-gate --output-dir ...`，然后上传 artifact。
- 本地触发/回收脚本已落地在 [run-hostless-evidence.sh](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/run-hostless-evidence.sh)，会用 `gh` 触发 workflow、等待 run 完成，并把 artifact 下载到本地目录。
- GitHub Actions `hostless-evidence` 首轮 run `24126522036` 已提供新的平台证据：
  - `macos-latest` job `70392362123` 成功完成单测、`release-gate` 和 artifact 上传
  - `windows-latest` job `70392362108` 在 `Run unit tests` 失败，根因不是业务解析器，而是 `US/Pacific` 在无 `tzdata` 环境下触发 `ZoneInfoNotFoundError`
- 时区兼容修复已落地在 [time_window.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/time_window.py)：
  - 为 `US/Pacific / US/Mountain / US/Central / US/Eastern / US/Alaska / US/Hawaii` 增加 canonical fallback
  - `build_time_window / build_month_window` 现在会保留调用方传入的时区名，避免 alias 被静默改写
- Windows 兼容测试真源已下沉到：
  - [test_time.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_time.py)
  - [test_time_window.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_time_window.py)
- `hostless-evidence` workflow 已在 [hostless-evidence.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/workflows/hostless-evidence.yml) 加上 `env.EVIDENCE_DIR != ''` 守卫，避免前置步骤失败时 artifact 上传再报一次 `path` 噪音错误
- 第二轮 Windows hosted run 的剩余失败根因已确认：CLI 子进程在 legacy stdout codec 下打印中文 JSON 时会触发 `UnicodeEncodeError`，而集成测试本身还会因为 `capture_output/text` 的平台差异表现成 `result.stdout is None`
- 最终修复已分两层落地：
  - [token_usage.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/token_usage.py) 现已在启动时强制把 `stdout / stderr` 重配置为 UTF-8，确保 `health / targets / report / release-gate` 这类含中文输出的 CLI 在 Windows hosted runner 上可稳定输出
  - [test_cli_integration.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_cli_integration.py) 现已统一改成显式 `stdout/stderr PIPE + encoding='utf-8'`，并在失败时直接打印 stdout/stderr，避免再出现“非零退出信息丢失”或 `stdout is None` 的黑盒误报
- `cp1252` 模拟回归现已被固定在 [test_cli_integration.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_cli_integration.py)，用于覆盖 legacy stdout encoding 场景
- GitHub-hosted `hostless-evidence` 最终成功证据已出现于 run `24128775284`：
  - `windows-latest` job `70399851410` 通过
  - `macos-latest` job `70399851412` 通过
  - artifact 已下载到 [github-hosted](/Users/guokeyu/AI/codex/token-usage-universal/examples/vm-testing/output/github-hosted)
- 模拟实机统一操作手册已落地在 [VM_RUNBOOK.md](/Users/guokeyu/AI/codex/token-usage-universal/docs/VM_RUNBOOK.md)。
- token 查询 skill 的短触发词现已显式覆盖 `token / 用量 / 消耗量 / 使用量 / 消耗`，并把默认聊天输出协议收紧为：只要 CLI 返回 `ascii-hifi` 面板，就先原样贴面板，再补简短结论。
- 这套交互契约现已下沉到仓库自身，而不是依赖某台开发机的 `~/.codex` 覆盖：README 新增了 `GitHub 交付契约` 说明，测试新增在 [test_skill_contract.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_skill_contract.py)。
- GitHub 产品分发相关的社区健康文件现已补齐在仓库内：
  - [CODE_OF_CONDUCT.md](/Users/guokeyu/AI/codex/token-usage-universal/CODE_OF_CONDUCT.md)
  - [SECURITY.md](/Users/guokeyu/AI/codex/token-usage-universal/SECURITY.md)
  - [SUPPORT.md](/Users/guokeyu/AI/codex/token-usage-universal/SUPPORT.md)
  - [bug_report.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/ISSUE_TEMPLATE/bug_report.yml)
  - [feature_request.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/ISSUE_TEMPLATE/feature_request.yml)
  - [config.yml](/Users/guokeyu/AI/codex/token-usage-universal/.github/ISSUE_TEMPLATE/config.yml)
  - [pull_request_template.md](/Users/guokeyu/AI/codex/token-usage-universal/.github/pull_request_template.md)
  - [test_github_repo_contract.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_github_repo_contract.py)
- `DeepSeek / Qianfan / Hunyuan / SenseNova / Baichuan / SiliconFlow / Spark` 的 `CLI / IDE` runtime surface 已通过共享 ingress bootstrap 升到 `exact-ready`。
- `OpenAI / Anthropic` 官方 ingress bootstrap profile 已补齐，`OpenAI IDE / Claude IDE` 两条全球生态 surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- `Gemini / OpenRouter / Perplexity / xAI / Mistral / StepFun` 的 ingress bootstrap profile 已补齐；其中 `Gemini / OpenRouter / Perplexity / xAI / Mistral` 的 `IDE` surface 和 `OpenRouter / Perplexity / xAI / Mistral / StepFun` 的 `CLI` surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- `Qwen / Kimi / GLM / Doubao / MiniMax` 的 ingress bootstrap profile 已补齐；其中 `Qwen / Kimi` 的 `IDE` surface、`GLM / Doubao / MiniMax` 的 `CLI / IDE` surface 已在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `exact-ready`。
- `StepFun / SenseNova / Baichuan / SiliconFlow / Spark / ChatGPT / Gemini / Grok / Mistral` 的桌面端 source skeleton 已落地在 [chromium_desktop_family.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/adapters/chromium_desktop_family.py)，并在 [ecosystem_registry.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/ecosystem_registry.py) 升级为 `detect-ready`。
- 价格库已在 [pricing_db.json](/Users/guokeyu/AI/codex/token-usage-universal/scripts/core/pricing_db.json) 补齐 `ERNIE / Hunyuan / SenseNova / Baichuan / Spark / Doubao aliases`；回归测试见 [test_pricing.py](/Users/guokeyu/AI/codex/token-usage-universal/scripts/test_pricing.py)。
- 最新验证：
  - `python3 -m unittest scripts.test_claude_code scripts.test_reporting scripts.test_chromium_desktop_adapters` 当前通过
  - `python3 -m unittest discover -s scripts -t . -p 'test_*.py'` 通过，`158` tests
  - `Claude Code` project JSONL fixture 已成功输出 `total_tokens = 30848`、`input_tokens = 30109`、`cached_input_tokens = 123`、`output_tokens = 616`
  - report 当前已能把 `claude-sonnet-4-6` 归到“已观测模型（未计入 token）”，不会误算进 exact 总量
  - report 当前已能把 `minimax-agent` 归到“已观测来源（未计入 token）”，不会因为只有痕迹就静默消失
  - `python3 scripts/token_usage.py health --format json` 返回 `supported_sources = 50`
  - `python3 scripts/token_usage.py targets --format json` 显示 `surface_maturity.exact-ready = 60`
  - `python3 scripts/token_usage.py ingress config --provider deepseek --upstream-base-url https://api.deepseek.com --protocol openai --format json` 成功输出本地 `v1` companion 地址
  - `python3 scripts/token_usage.py ingress profiles --format json` 成功输出 `22` 个 bootstrap profile
  - `python3 scripts/token_usage.py ingress bootstrap --profile gemini --editor vscode --format json` 成功输出 Gemini OpenAI-compatibility 的 `/v1beta/openai` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile openrouter --editor jetbrains --format json` 成功输出 OpenRouter `/api/v1` 对应的本地 `/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile perplexity --editor vscode --format json` 成功输出 Perplexity root-base companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile stepfun --editor jetbrains --format json` 成功输出 StepFun `/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile qwen --editor vscode --format json` 成功输出 DashScope `/compatible-mode/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile kimi --editor jetbrains --format json` 成功输出 Moonshot `/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile glm --editor vscode --format json` 成功输出 BigModel coding `/api/coding/paas/v4` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile doubao --editor jetbrains --format json` 成功输出 Ark `/api/v3` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile minimax --editor vscode --format json` 成功输出 MiniMax `/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile openai --editor vscode --format json` 成功输出官方 OpenAI profile 的 `/v1` companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile anthropic --editor jetbrains --format json` 成功输出官方 Anthropic profile 的 root-base companion 样板
  - `python3 scripts/token_usage.py ingress bootstrap --profile anthropic-compatible --editor jetbrains --upstream-base-url https://api.anthropic.example --format json` 成功输出 Anthropic-compatible JetBrains 样板
  - 当前机器 `health` 仍显示 `deepseek-desktop / qianfan-desktop / yuanbao-desktop = not-found`，原因是本机没有对应 app-data 根目录，不是代码未实现
  - `python3 scripts/token_usage.py release-gate --format json` 当前返回 `7/7 gates passed`，其中 `Top20 coverage / China priority / exact surface / false-ready claims / default report duplicate rate / diagnose explainability / windows-macos-root-matrix` 全部通过
  - `python3 scripts/token_usage.py release-gate --format json --output-dir /tmp/token-usage-universal-evidence` 当前已实跑成功，证据包目录可直接用于后续真机交接
  - `python3 scripts/build_release.py --output-dir /tmp/token-usage-universal-release-gate --validate --force` 当前已实跑成功，说明发布导出链路会先过单测与 `release-gate`
  - `git remote -v` 当前显示 `origin = https://github.com/zsfd1997-glitch/token-usage-universal.git`
  - `gh auth status` 当前显示账号 `zsfd1997-glitch` 已登录，且 token scope 包含 `repo` 和 `workflow`
  - `python3 -m unittest scripts.test_skill_contract` 当前通过，说明仓库内 `SKILL.md` 和 `README.md` 已共同约束 `token` 默认触发与 `ascii-hifi` 默认输出
  - `gh api repos/zsfd1997-glitch/token-usage-universal/community/profile` 当前仍返回 `health_percentage = 57`，且 `code_of_conduct / issue_template / pull_request_template = null`；这是远端默认分支尚未包含本地新文件，不是本地仓库缺失
  - `python3 -m unittest scripts.test_github_repo_contract scripts.test_skill_contract` 当前通过

## 异常/降级 Events
- `workflow-superchain` 推荐的 `init_superchain_artifacts.py` 在本仓库内不存在，因此本轮沿用现有 `master-plan.md / task_plan.md / progress.md / findings.md` 主线文档继续执行。
- `workflow-superchain` 推荐的 `validate_superchain_artifacts.py` 与 `superchain_observability.py` 在本仓库内不存在，因此本轮改为用真实测试、CLI 输出与主线文档回填做验收闭环。
- `knowledge-superchain` 推荐的 harness 脚本在本仓库内也不存在，因此本次“存档”沿用仓库现有主线资产而不是伪造脚本执行。
- GitHub-hosted `hostless-evidence` 的 Node.js 20 deprecation 仅是 Actions 依赖版本告警，不影响当前 run `24128775284` 的成功结论；后续可单独升级 `actions/checkout / setup-python / upload-artifact` 以消除告警。

## 根因 Root Cause
- 当前项目虽然已有多 source 统计能力，但没有统一的 Top20 生态真源，导致 roadmap、adapter、health 和未来 ingress 可能各自漂移。

## 决策 Decision
- 选择先落 `Top20 registry + surface matrix + targets CLI`，再进入 provider exact pack 和 native client pack。
- 不选择直接继续补零散 adapter，因为那会加速目标口径失控。

## 风险 Risk
- 当前 registry 的 `60/60` surface 已经全到 `exact-ready`，且 hosted runner 双平台证据已通过，但这仍不等于所有生态都已完成真实双机 E2E 与真实样本回归。
- 如果没有后续真实 fixture 与双平台实测，`release-gate` 仍不能完全替代真机验收。
- GitHub-hosted runner 能解决“没有 host 环境”的平台级 smoke/evidence 采集，但不会凭空带来真实桌面客户端 app-data。
- ingress companion 已经最小可用，且中国优先剩余 IDE/CLI lane 也已全部接上共享 bootstrap；当前主要风险转移到 `Gemini CLI` 与多条 `detect-ready` desktop surface 的真实 fixture 完整性。
- `qwen-code-cli / kimi-cli` 虽然代码已完成，但当前机器没有对应 runtime root，所以本机 health 会显示 `not-found`；这不应被误读成适配失败。
- `glm-desktop / doubao-desktop / perplexity-desktop` 虽然代码已完成，但当前机器没有对应桌面端 app-data，所以本机只能验证 `not-found` 分支与测试夹具分支；真机 exact 命中仍依赖后续 fixture。
- `release-gate` 当前虽然已覆盖全部 root-aware source 的双平台默认路径矩阵，并补了默认 report 的 runtime duplicate probe，但这仍不等于真实双机 E2E 与大样本实测已完成。
