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

    def test_china_priority_phase1_provider_packs_collect_exact_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_file = root / "china-priority.jsonl"
            log_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "created_at": "2026-03-25T12:00:00-07:00",
                                "provider": "sensenova",
                                "model": "SenseChat-5",
                                "session_id": "sn-1",
                                "data": {
                                    "usage": {
                                        "prompt_tokens": 70,
                                        "completion_tokens": 20,
                                        "total_tokens": 90,
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T12:05:00-07:00",
                                "provider": "baichuan",
                                "model": "Baichuan4-Turbo",
                                "session_id": "bc-1",
                                "usage": {
                                    "prompt_tokens": 120,
                                    "completion_tokens": 30,
                                    "total_tokens": 150,
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T12:10:00-07:00",
                                "request": {"url": "https://api.siliconflow.cn/v1/chat/completions"},
                                "model": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
                                "session_id": "sf-1",
                                "usage": {
                                    "prompt_tokens": 200,
                                    "completion_tokens": 50,
                                    "total_tokens": 250,
                                    "prompt_tokens_details": {"cached_tokens": 80},
                                    "completion_tokens_details": {"reasoning_tokens": 15},
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "created_at": "2026-03-25T12:15:00-07:00",
                                "url": "https://spark-api-open.xf-yun.com/v1/chat/completions",
                                "model": "spark-x1",
                                "session_id": "sp-1",
                                "payload": {
                                    "usage": {
                                        "text": {
                                            "prompt_tokens": 180,
                                            "completion_tokens": 40,
                                            "total_tokens": 220,
                                        }
                                    }
                                },
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
                sensenova_result = adapter_map["sensenova-api"].collect(_window())
                baichuan_result = adapter_map["baichuan-api"].collect(_window())
                siliconflow_result = adapter_map["siliconflow-api"].collect(_window())
                spark_result = adapter_map["spark-api"].collect(_window())

        self.assertEqual(len(sensenova_result.events), 1)
        self.assertEqual(sensenova_result.events[0].session_id, "sn-1")
        self.assertEqual(sensenova_result.events[0].provider, "sensenova")

        self.assertEqual(len(baichuan_result.events), 1)
        self.assertEqual(baichuan_result.events[0].session_id, "bc-1")
        self.assertEqual(baichuan_result.events[0].provider, "baichuan")

        self.assertEqual(len(siliconflow_result.events), 1)
        self.assertEqual(siliconflow_result.events[0].session_id, "sf-1")
        self.assertEqual(siliconflow_result.events[0].provider, "siliconflow")
        self.assertEqual(siliconflow_result.events[0].cached_input_tokens, 80)
        self.assertEqual(siliconflow_result.events[0].reasoning_tokens, 15)

        self.assertEqual(len(spark_result.events), 1)
        self.assertEqual(spark_result.events[0].session_id, "sp-1")
        self.assertEqual(spark_result.events[0].provider, "spark")
        self.assertEqual(spark_result.events[0].total_tokens, 220)


if __name__ == "__main__":
    unittest.main()
