# Architecture

## 产品结构

`token-usage-universal` 对外是一个 `skill`，内部由一个 Python CLI core 驱动。

```text
SKILL.md
  -> scripts/token_usage.py
      -> adapters/*
      -> core/*
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
- `generic-openai-compatible`

### 2. Core Layer

位于 `scripts/core/`。

职责：

- 定义数据模型
- 处理时间窗口
- 构建 health 报告
- 聚合 usage 数据
- 估算 cost（严格标记为 estimated）
- 做最基本的结果校验

当前已输出：

- `by_source / by_model / by_project / by_session / by_day`
- `current_session`
- `session_detail`
- `charts.trend_7d / charts.trend_30d / charts.calendar_month`

### 3. Rendering Layer

位于 `scripts/ascii_hifi.py`。

职责：

- 把聚合结果渲染成 ASCII-HIFI 终端控制面
- 支持条形图、sparkline、月历热力图和当前会话卡片
- 支持 `report / sources / diagnose / health / explore`

### 4. Explore Layer

位于 `scripts/token_usage.py` 中的轻量交互入口。

职责：

- 在 TTY 中提供“弹出可选”的视图选择
- 只做交互收集与路由，不单独实现聚合逻辑
- 非 TTY 下优雅降级，提示改用纯 flags/subcommands

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
