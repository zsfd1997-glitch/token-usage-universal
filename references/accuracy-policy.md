# Accuracy Policy

## Levels

### `exact`
- 原始日志里有明确 usage 数值
- 时间戳明确
- 增量语义明确
- 允许“只精确到 total_tokens”的 session 级真源，但必须显式说明缺失的拆分字段

### `derived`
- 原始日志不直接给完整 usage，但能通过稳定规则推导
- v1 默认不输出

### `estimated`
- 需要 tokenizer 或价格表估算
- v1 禁止默认输出

### `unsupported`
- 本地无真源
- 真源字段含糊
- 时间或增量语义不可靠

## Hard Guard

出现以下任一情况，不得输出 `exact`：

- 只有文本 transcript，没有 usage 数值
- 同一来源无法解释累计与增量关系
- 关键字段缺失且无法稳定补齐
- 统计只能依赖模型 tokenizer 猜测
