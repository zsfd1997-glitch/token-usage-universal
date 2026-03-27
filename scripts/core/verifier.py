from __future__ import annotations

from core.models import SourceCollectResult


def verify_result(result: SourceCollectResult) -> list[str]:
    issues: list[str] = []
    for event in result.events:
        known_values = [
            value
            for value in (
                event.input_tokens,
                event.cached_input_tokens,
                event.output_tokens,
                event.reasoning_tokens,
                event.total_tokens,
            )
            if value is not None
        ]
        if known_values and min(known_values) < 0:
            issues.append(f"negative token value detected in {event.source_path}")
            break
        if event.output_tokens is not None and event.total_tokens < event.output_tokens:
            issues.append(f"total_tokens smaller than output_tokens in {event.source_path}")
            break
    return issues
