# Architecture

## 产品结构

`token-usage-universal` 对外主成品是 `独立 Python CLI`，`skill` 只是可选包装层；内部由一个 Python CLI core 驱动。

```text
SKILL.md
  -> scripts/token_usage.py
      -> adapters/*
      -> core/*
      -> core/ecosystem_registry.py
      -> core/pricing.py
      -> ascii_hifi.py
```

## 关键层次

### 1. Adapter Layer

位于 `scripts/adapters/`。

职责：

- 探测来源是否存在
- 从本地真源收集 usage 事件
- 返回标准 `SourceDetection` 和 `SourceCollectResult`

当前来源：

- `codex`
- `claude-code`
- `claude-desktop`
- `opencode`
- `minimax-agent`
- `qwen-code-cli`
- `kimi-cli`
- `kimi-desktop / glm-desktop / qwen-desktop / deepseek-desktop / doubao-desktop / qianfan-desktop / yuanbao-desktop / perplexity-desktop`
- `openai-api / anthropic-api / google-gemini-api / moonshot-kimi-api / zhipu-glm-api / qwen-api / deepseek-api / minimax-api / xai-grok-api / cohere-api / mistral-api / perplexity-api / openrouter-api / togetherai-api / fireworks-api / azure-openai-api / baidu-qianfan-api / tencent-hunyuan-api / stepfun-api / doubao-api / sensenova-api / baichuan-api / siliconflow-api / spark-api`
- `generic-openai-compatible`（手动补漏 / diagnose fallback）

### 2. Core Layer

位于 `scripts/core/`。

职责：

- 定义数据模型
- 处理时间窗口
- 构建 health 报告
- 聚合 usage 数据
- 估算 cost（严格标记为 estimated）
- 做最基本的结果校验
- 维护 Top20 生态 registry 与 surface matrix 真源

当前已输出：

- `by_source / by_model / by_project / by_session / by_day`
- `current_session`
- `session_detail`
- `charts.trend_7d / charts.trend_30d / charts.calendar_month`
- `targets`（冻结的 Top20 ecosystem/client-family registry）
- `release-gate`（自动化校验 Top20 覆盖率、exact 覆盖率、结构性误报、默认 report 重复计数 probe 与双平台 root matrix）

### 3. Rendering Layer

位于 `scripts/ascii_hifi.py`。

职责：

- 把聚合结果渲染成 ASCII-HIFI 终端控制面
- 支持条形图、sparkline、月历热力图和当前会话卡片
- 支持 `report / sources / diagnose / health / targets / release-gate / explore`

### 4. Explore Layer

位于 `scripts/token_usage.py` 中的轻量交互入口。

职责：

- 在 TTY 中提供“弹出可选”的视图选择
- 只做交互收集与路由，不单独实现聚合逻辑
- 非 TTY 下优雅降级，提示改用纯 flags/subcommands

### 5. Ingress Companion Layer

位于 `scripts/core/ingress_companion.py` 和 `token_usage.py ingress *`。

职责：

- 为 `IDE / 内网 launcher / 自定义 base_url` 客户端提供本地 companion
- 支持 `openai / anthropic / generic` 三种协议模式
- 把 exact usage 响应落成 JSONL，供 provider family 自动发现
- 尽量不绑定某个固定 `skills` 库或单一宿主环境
- `scripts/core/ingress_bootstrap.py` 进一步把 companion 包成生态级 bootstrap profiles，直接生成 `VS Code / JetBrains` 的 Continue 配置片段和 CLI shell env 示例

## 非目标

- 不做 provider billing API 联网依赖
- 不做 GUI / SaaS 面板
- 不把 CLI 单独包装成第二个对外产品
- 不把 `estimated cost` 伪装成账单真源

## Task Master 关系

`Task Master` 只属于可选的 PRD / task handoff。

它不参与：

- skill 运行
- health 自检
- usage 统计
- GitHub 发布
