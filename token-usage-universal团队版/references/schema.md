# Team Schema

## TeamUsageEvent

```json
{
  "event_id": "8a7b27f9c3c7",
  "team_id": "demo-team",
  "user_id": "alice",
  "machine_id": "alice-mbp",
  "machine_label": "Alice MacBook Pro",
  "source": "codex",
  "provider": "openai",
  "model": "gpt-5.4",
  "session_id": "019c9244-27f4-71e2-85fd-26dcc0d777bc",
  "project_path": "/Users/alice/work/demo",
  "timestamp": "2026-03-30T09:17:00-07:00",
  "input_tokens": 1200,
  "cached_input_tokens": 300,
  "output_tokens": 420,
  "reasoning_tokens": 80,
  "total_tokens": 1920,
  "accuracy_level": "exact",
  "raw_event_kind": "token_count:delta",
  "source_path": "/Users/alice/.codex/sessions/2026/03/30/run.jsonl",
  "exported_at": "2026-03-30T22:40:00-07:00"
}
```

## Required Fields

- `event_id`
- `team_id`
- `user_id`
- `machine_id`
- `source`
- `provider`
- `timestamp`
- `session_id`
- `total_tokens`
- `accuracy_level`
- `raw_event_kind`
- `source_path`

## Optional Fields

- `machine_label`
- `project_path`
- `model`
- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `reasoning_tokens`
- `exported_at`

## Semantics

- `event_id`: 稳定去重键，中心汇总时优先按它去重
- `team_id`: 团队隔离维度
- `user_id`: 成员唯一标识，建议用企业账号或工号
- `machine_id`: 设备唯一标识，建议稳定不变
- `total_tokens`: 本条事件的总 token，保持增量语义
- `accuracy_level`: `exact / derived / estimated / unsupported`
