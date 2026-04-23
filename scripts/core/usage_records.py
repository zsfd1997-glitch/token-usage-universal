from __future__ import annotations


TIMESTAMP_KEYS = ("timestamp", "created_at", "time", "created", "finished_at")
SESSION_KEYS = (
    "session_id",
    "sessionId",
    "conversation_id",
    "conversationId",
    "request_id",
    "requestId",
    "trace_id",
    "traceId",
    "id",
)
PROJECT_KEYS = ("project_path", "cwd", "project", "workspace", "repo_path", "working_directory", "root")
PROVIDER_KEYS = ("provider", "provider_name", "model_provider", "vendor", "api_provider")
MODEL_KEYS = ("model", "model_name", "model_id", "modelId", "model_name_for_human")


def find_first_value(node, keys: tuple[str, ...]):
    if isinstance(node, dict):
        for key in keys:
            if key in node and node[key] not in (None, ""):
                return node[key]
        for value in node.values():
            found = find_first_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_first_value(value, keys)
            if found not in (None, ""):
                return found
    return None


def _int_value(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _nested_int(payload: dict[str, object], *path: str) -> int:
    current: object = payload
    for key in path:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    return _int_value(current)


def _looks_like_usage_dict(node: dict[str, object]) -> bool:
    has_input = any(
        key in node
        for key in (
            "input_tokens",
            "prompt_tokens",
            "cached_input_tokens",
            "cache_read_input_tokens",
            # OpenCode v1.1.13+ schema: {"input", "output", "reasoning",
            # "cache": {"read", "write"}} — short keys on a bare token dict.
            "input",
        )
    )
    has_output = any(
        key in node
        for key in (
            "output_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "reasoning_output_tokens",
            # OpenCode v1.1.13+ schema (see above).
            "output",
            "reasoning",
        )
    )
    has_total = "total_tokens" in node
    has_nested_cache = (
        _nested_int(node, "input_token_details", "cached_tokens") > 0
        or _nested_int(node, "prompt_tokens_details", "cached_tokens") > 0
        # OpenCode nested cache: {"cache": {"read": N, "write": N}}
        or _nested_int(node, "cache", "read") > 0
        or _nested_int(node, "cache", "write") > 0
    )
    return has_total or ((has_input or has_nested_cache) and has_output)


def find_usage_dict(node):
    if isinstance(node, dict):
        if _looks_like_usage_dict(node):
            return node
        for value in node.values():
            found = find_usage_dict(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_usage_dict(value)
            if found:
                return found
    return None


def iter_usage_carriers(node):
    if isinstance(node, dict):
        direct_usage = node.get("usage")
        if isinstance(direct_usage, dict) and _looks_like_usage_dict(direct_usage):
            yield node, direct_usage
        elif _looks_like_usage_dict(node):
            yield node, node
        for key, value in node.items():
            if key == "usage":
                continue
            yield from iter_usage_carriers(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_usage_carriers(value)


def normalize_usage(payload: dict[str, object]) -> dict[str, int]:
    # Two schemas share this function:
    #  - OpenAI / Anthropic long-key: input_tokens / prompt_tokens already
    #    includes any cached_read portion; total_tokens = input + output.
    #  - OpenCode v1.1.13+ short-key: {"input", "output", "reasoning",
    #    "cache": {"read", "write"}}; "input" excludes cached read, and
    #    total must include cache.read + cache.write.
    has_long_input = "input_tokens" in payload or "prompt_tokens" in payload
    has_short_input = "input" in payload and not has_long_input

    if has_long_input:
        input_tokens = _int_value(payload.get("input_tokens", payload.get("prompt_tokens", 0)))
    elif has_short_input:
        # OpenCode: "input" excludes cache.read; fold cache.write into input
        # so the first-time cache-population cost shows up as billable input.
        input_tokens = _int_value(payload.get("input", 0)) + _nested_int(payload, "cache", "write")
    else:
        input_tokens = 0

    cached_input_tokens = max(
        _int_value(payload.get("cached_input_tokens", 0)),
        _int_value(payload.get("cache_read_input_tokens", 0)),
        _nested_int(payload, "input_token_details", "cached_tokens"),
        _nested_int(payload, "prompt_tokens_details", "cached_tokens"),
        _nested_int(payload, "cache", "read"),
    )
    output_tokens = _int_value(
        payload.get("output_tokens", payload.get("completion_tokens", payload.get("output", 0)))
    )
    reasoning_tokens = max(
        _int_value(payload.get("reasoning_tokens", 0)),
        _int_value(payload.get("reasoning_output_tokens", 0)),
        _int_value(payload.get("reasoning", 0)),
        _nested_int(payload, "output_token_details", "reasoning_tokens"),
        _nested_int(payload, "completion_tokens_details", "reasoning_tokens"),
    )
    total_tokens = _int_value(payload.get("total_tokens", 0))
    if not total_tokens:
        if has_short_input:
            # OpenCode: total = (input including cache.write) + cache.read + output + reasoning
            total_tokens = input_tokens + cached_input_tokens + output_tokens + reasoning_tokens
        else:
            # OpenAI / Anthropic: input already includes cached; total = input + output
            total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }
