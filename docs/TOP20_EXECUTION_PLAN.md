# Top20 Execution Plan

## Goal

把 `token-usage-universal` 从“少数本地客户端统计工具”升级为“Top20 模型生态/客户端家族”的统一 token 统计平台。

冻结口径：

- 冻结单位：`模型生态 / 客户端家族`
- 范围：`Desktop + CLI + IDE`
- 三层采集：`native-client + provider-exact + ingress-capture`
- 中国优先：优先完成国产生态的 Desktop / CLI / IDE 多端覆盖

## Why This Shape

不能按单个 SKU 做：

- SKU 变化太快，维护成本高
- 同一生态往往同时有 `App / Desktop / CLI / IDE / API`
- 真正难点不是模型名，而是“token 真源从哪里拿”

所以必须按生态冻结，再按 surface 拆交付。

## Frozen Top20

### China Priority 13

- `Qwen / DashScope / Qwen Code`
- `Kimi / Moonshot / Kimi CLI`
- `GLM / BigModel / Z.ai`
- `MiniMax / MiniMax Agent`
- `DeepSeek`
- `Doubao / Volcengine Ark`
- `Baidu Qianfan / Wenxin`
- `Tencent Hunyuan / Yuanbao`
- `StepFun`
- `SenseNova`
- `Baichuan`
- `SiliconFlow`
- `讯飞星火 / Spark`

### Global 7

- `OpenAI / Codex / ChatGPT Desktop`
- `Anthropic / Claude Code / Claude Desktop`
- `Google Gemini / Gemini CLI`
- `OpenRouter`
- `Perplexity`
- `xAI / Grok`
- `Mistral`

## Capture Lanes

### 1. Native Client

适用于：

- 官方 CLI export / stats / logs
- Electron / Chromium Desktop `Cache_Data / IndexedDB / Local Storage`
- 本地 session artifacts / checkpoints

适合：

- `Desktop`
- 官方 `CLI`

### 2. Provider Exact

适用于：

- 官方 API usage schema
- OpenAI-compatible
- Anthropic-compatible
- provider-specific cache / reasoning 字段

适合：

- 统一 `usage normalizer`
- canonical model 归一化
- 给 native 和 ingress 做 schema 底座

### 3. Ingress Capture

适用于：

- 自定义 `base_url`
- 本地代理
- 系统代理
- 可选 eBPF

适合：

- `IDE`
- 私有 launcher
- 无法稳定落本地 exact cache 的客户端

## Phase Plan

### Phase 0

产物：

- `Top20 registry`
- `surface matrix`
- `truth model`
- `targets` CLI

验收：

- 20 个生态全部入表
- 每个生态都明确 `Desktop / CLI / IDE` 的主采集 lane

### Phase 1

目标：

- 完成所有 Top20 的 provider exact schema pack

当前进度：

- China Priority batch A 已落地：`sensenova-api`、`baichuan-api`、`siliconflow-api`、`spark-api`
- provider family 现在不仅看 `provider / model`，也会看 `request url / base_url / endpoint`，用于兼容 IDE 代理日志和 provider passthrough 日志
- `Qwen Code CLI` 已进入 `exact-ready`：直接读取官方 project-scoped session JSONL
- `Kimi CLI` 已进入 `exact-ready`：直接读取官方 `~/.kimi/sessions/*/*/wire.jsonl` 与 `StatusUpdate.token_usage`
- `GLM Desktop / Doubao Desktop / Perplexity Desktop` 已完成桌面端 exact-native 强化：统一支持 `Cache_Data + IndexedDB + Local Storage` 三类本地真源
- `DeepSeek Desktop / Qianfan Desktop / Yuanbao Desktop` 已完成桌面端 exact-native 强化：统一支持 `Cache_Data + IndexedDB + Local Storage` 三类本地真源
- `pricing_db.json` 已补齐 `ERNIE / Hunyuan / SenseNova / Baichuan / Spark / Doubao alias` 这一批国产生态的费用估算基线

验收：

- 官方样例 fixture 全通过
- cache / reasoning / total token 字段全部标准化

### Phase 2

目标：

- 完成第一梯队 native client pack

第一梯队：

- `Claude Desktop`
- `MiniMax Agent`
- `Qwen Code CLI`
- `Kimi CLI`
- `Kimi Desktop`
- `GLM Desktop`
- `Doubao Desktop`
- `Perplexity Desktop`
- `Codex`
- `OpenCode`

验收：

- source 存在时不误报 `ready`
- 没真源时明确输出 diagnose 原因

### Phase 3

目标：

- 上线 ingress companion

当前进度：

- `token_usage.py ingress config` 已可为单个 provider 打印本地代理地址、上游地址、推荐 env/config 与 log 根目录
- `token_usage.py ingress serve` 已可启动本地 companion，并把 exact usage 响应落成 JSONL
- 当前 companion 已支持 `openai / anthropic / generic` 三种协议模式，优先服务 `IDE / 内网 launcher / 自定义 base_url` 场景

能力：

- `OpenAI-compatible`
- `Anthropic-compatible`
- provider passthrough
- 本地代理健康检查

验收：

- 支持改 `base_url` 的 CLI / IDE 都能被 exact 捕获

### Phase 4

目标：

- 建立 IDE lane

原则：

- 不按每个插件单独写 parser
- 按生态 family + proxy companion 收敛

验收：

- VS Code / JetBrains 至少各有一条打通样板链路

### Phase 5

目标：

- 展示层和归因层升级

新增视图：

- `by ecosystem`
- `by surface`
- `by capture lane`
- `missing source reasons`

### Phase 6

目标：

- Win/mac matrix + release gate

验收：

- 覆盖率、误报率、重复计数率全部达标后才对外宣称完成

## Gates

- `Top20 覆盖率 >= 90%`
- `中国优先 13 覆盖率 = 100%`
- `exact 覆盖率 >= 80%`
- `误报 ready = 0`
- `重复计数率 <= 0.5%`
- `diagnose 可解释率 >= 95%`
- `Windows + macOS` 双平台通过

## Rollback

- 新增生态 registry、surface matrix、proxy companion 都是增量资产
- 任一阶段不可行时，保留现有 `native + provider` 路线，不回退已稳定 source
- ingress companion 若不满足合规要求，可整体关闭，不影响现有 CLI 统计链路
