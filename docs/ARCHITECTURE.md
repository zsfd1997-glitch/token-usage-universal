# Architecture

## 产品结构

`token-usage-universal` 对外是一个 `skill`，内部由一个 Python CLI core 驱动。

```text
SKILL.md
  -> scripts/token_usage.py
      -> adapters/*
      -> core/*
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
- 做最基本的结果校验

### 3. Rendering Layer

位于 `scripts/ascii_hifi.py`。

职责：

- 把聚合结果渲染成 ASCII-HIFI 面板
- 支持 `report / sources / diagnose / health`

## 非目标

- 不做 provider billing API 联网依赖
- 不做 GUI / SaaS 面板
- 不把 CLI 单独包装成第二个对外产品

## Task Master 关系

`Task Master` 只属于可选的 PRD / task handoff。

它不参与：

- skill 运行
- health 自检
- usage 统计
- GitHub 发布
