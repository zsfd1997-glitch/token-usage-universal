# Unified Schema

## UsageEvent

```json
{
  "source": "codex",
  "provider": "openai",
  "model": null,
  "session_id": "019c9244-27f4-71e2-85fd-26dcc0d777bc",
  "project_path": "/Users/guokeyu/AI/codex/学习AI",
  "timestamp": "2026-03-25T00:17:00-07:00",
  "input_tokens": 123,
  "cached_input_tokens": 45,
  "output_tokens": 67,
  "reasoning_tokens": 8,
  "total_tokens": 190,
  "accuracy_level": "exact",
  "raw_event_kind": "token_count:delta"
}
```

## Required Fields

- `source`
- `timestamp`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `accuracy_level`

## Optional Fields

- `project_path`
- `session_id`
- `model`
- `cached_input_tokens`
- `reasoning_tokens`
- `provider`

## Semantics

- `timestamp`: 事件归属时间，统一转换到请求时区
- `total_tokens`: 本条增量事件的总 token，不是全 session 累计值
- `accuracy_level`: `exact / derived / estimated / unsupported`
