from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.usage_records import (  # noqa: E402
    _looks_like_usage_dict,
    iter_usage_carriers,
    normalize_usage,
)


class NormalizeUsageTests(unittest.TestCase):
    def test_openai_long_keys(self) -> None:
        values = normalize_usage({
            "prompt_tokens": 132,
            "completion_tokens": 121,
            "total_tokens": 253,
            "prompt_tokens_details": {"cached_tokens": 64},
        })
        self.assertEqual(values["input_tokens"], 132)
        self.assertEqual(values["cached_input_tokens"], 64)
        self.assertEqual(values["output_tokens"], 121)
        self.assertEqual(values["total_tokens"], 253)

    def test_anthropic_long_keys_without_total(self) -> None:
        # Anthropic reports cache_read as a peer to input_tokens; input
        # already represents "paid-rate" prompt tokens, so total should
        # stay at input + output (not double-counted against cached).
        values = normalize_usage({
            "input_tokens": 300,
            "cache_read_input_tokens": 120,
            "output_tokens": 90,
        })
        self.assertEqual(values["input_tokens"], 300)
        self.assertEqual(values["cached_input_tokens"], 120)
        self.assertEqual(values["total_tokens"], 390)

    def test_opencode_short_keys_with_cache(self) -> None:
        # OpenCode v1.1.13+ schema:
        # input excludes cache.read; cache.write = first-time cache fill,
        # paid at full rate so fold into input_tokens.
        values = normalize_usage({
            "input": 1000, "output": 200, "reasoning": 50,
            "cache": {"read": 500, "write": 100},
        })
        self.assertEqual(values["input_tokens"], 1100)  # 1000 + 100 cache.write
        self.assertEqual(values["cached_input_tokens"], 500)
        self.assertEqual(values["output_tokens"], 200)
        self.assertEqual(values["reasoning_tokens"], 50)
        self.assertEqual(values["total_tokens"], 1850)  # 1100 + 500 + 200 + 50

    def test_opencode_short_keys_without_cache_field(self) -> None:
        values = normalize_usage({"input": 100, "output": 50, "reasoning": 0})
        self.assertEqual(values["input_tokens"], 100)
        self.assertEqual(values["cached_input_tokens"], 0)
        self.assertEqual(values["output_tokens"], 50)
        self.assertEqual(values["total_tokens"], 150)


class LooksLikeUsageDictTests(unittest.TestCase):
    def test_opencode_short_keys_are_recognized(self) -> None:
        self.assertTrue(_looks_like_usage_dict({"input": 100, "output": 50}))
        self.assertTrue(_looks_like_usage_dict({"input": 100, "reasoning": 5}))
        self.assertTrue(_looks_like_usage_dict({
            "cache": {"read": 10}, "output": 5,
        }))

    def test_openai_long_keys_still_recognized(self) -> None:
        self.assertTrue(_looks_like_usage_dict({
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        }))
        self.assertTrue(_looks_like_usage_dict({
            "input_tokens": 10, "output_tokens": 5,
        }))

    def test_unrelated_dicts_rejected(self) -> None:
        self.assertFalse(_looks_like_usage_dict({"name": "x", "count": 3}))
        self.assertFalse(_looks_like_usage_dict({"input": 1}))  # no output-ish field


class IterUsageCarriersTests(unittest.TestCase):
    def test_nested_opencode_short_keys(self) -> None:
        payload = {
            "session": "ses_1",
            "events": [
                {"type": "trace", "tokens": {"input": 100, "output": 50, "reasoning": 0}},
            ],
        }
        carriers = list(iter_usage_carriers(payload))
        self.assertEqual(len(carriers), 1)
        _carrier, usage = carriers[0]
        self.assertEqual(usage["input"], 100)


if __name__ == "__main__":
    unittest.main()
