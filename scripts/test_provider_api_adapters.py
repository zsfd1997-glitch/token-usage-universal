from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.compatible_api_family import build_provider_api_adapters
from adapters.generic_openai_compatible import GenericOpenAICompatibleAdapter
from core.config import TOKEN_USAGE_DISCOVERY_ROOTS_ENV, TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV
from core.models import TimeWindow


def _window() -> TimeWindow:
    tzinfo = ZoneInfo("US/Pacific")
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class ProviderApiAdapterTests(unittest.TestCase):
    def test_provider_specific_adapters_split_exact_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "providers.jsonl"
            log_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "created_at": "2026-03-25T10:00:00-07:00",
                                "provider": "openai",
                                "model": "gpt-5",
                                "session_id": "oa-1",
                                "usage": {"input_tokens": 100, "output_tokens": 25, "total_tokens": 125},
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T10:05:00-07:00",
                                "provider": "moonshot",
                                "model": "kimi-k2",
                                "session_id": "ms-1",
                                "usage": {"prompt_tokens": 90, "completion_tokens": 30, "total_tokens": 120},
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T10:10:00-07:00",
                                "provider": "custom-lab",
                                "model": "lab-1",
                                "session_id": "lab-1",
                                "usage": {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            adapter_map = {adapter.source_id: adapter for adapter in build_provider_api_adapters()}
            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_DISCOVERY_ROOTS_ENV: str(root / "unused"),
                },
                clear=False,
            ):
                openai_result = adapter_map["openai-api"].collect(_window())
                moonshot_result = adapter_map["moonshot-kimi-api"].collect(_window())
                generic_result = GenericOpenAICompatibleAdapter().collect(_window())

        self.assertEqual(len(openai_result.events), 1)
        self.assertEqual(openai_result.events[0].session_id, "oa-1")
        self.assertEqual(len(moonshot_result.events), 1)
        self.assertEqual(moonshot_result.events[0].session_id, "ms-1")
        self.assertEqual(len(generic_result.events), 3)
        self.assertEqual({event.session_id for event in generic_result.events}, {"oa-1", "ms-1", "lab-1"})

    def test_provider_adapter_uses_model_fallback_when_provider_field_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "openai.jsonl"
            log_file.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-25T11:00:00-07:00",
                        "model": "gpt-5.4",
                        "session_id": "oa-2",
                        "usage": {"input_tokens": 60, "output_tokens": 20, "total_tokens": 80},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            adapter_map = {adapter.source_id: adapter for adapter in build_provider_api_adapters()}
            with patch.dict(
                os.environ,
                {
                    TOKEN_USAGE_GENERIC_LOG_GLOBS_ENV: str(log_file),
                    TOKEN_USAGE_DISCOVERY_ROOTS_ENV: str(root / "unused"),
                },
                clear=False,
            ):
                result = adapter_map["openai-api"].collect(_window())

        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].provider, "openai")
        self.assertEqual(result.events[0].session_id, "oa-2")


if __name__ == "__main__":
    unittest.main()
