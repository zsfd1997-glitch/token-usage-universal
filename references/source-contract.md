# Source Contract

每个来源 adapter 至少声明：

- `source_id`
- `display_name`
- `provider`
- `accuracy_level`

并实现这四步：

1. `detect()`
- 判断本机是否存在该来源的本地痕迹
- 输出是否可用、为何不可用、候选路径

2. `scan()`
- 返回候选日志文件

3. `collect()`
- 解析原始记录并产出统一 `UsageEvent`
- 必须明确时间语义和增量语义

4. `verify()`
- 检查负数、重复累计、缺失关键字段等异常

## 当前约束

- 默认只读本地文件
- 不能联网补账单
- 没有真源 usage 字段时，必须停在 `unsupported`

## 增量语义

- `codex`: cumulative total -> convert to per-event delta
- `generic-openai-compatible`: explicit per-record usage delta
- `claude-code`: `timing.json` session total -> exact total-token session event
  - 时间语义: 使用 `executor_end` / `grader_end`
  - 数量语义: 使用 `total_tokens`
  - 限制: 常见样本只有 `total_tokens`，没有 `input/output/cache` 拆分；仅 transcript 时继续 `unsupported`
