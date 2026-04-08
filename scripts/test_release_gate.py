from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.release_gate import _build_default_selection_duplicate_probe, build_release_gate_payload


def _health_report() -> dict[str, object]:
    return {
        "supported_sources": 3,
        "sources": [
            {
                "source_id": "codex",
                "supported": True,
                "summary": "ready",
            },
            {
                "source_id": "claude-desktop",
                "supported": True,
                "summary": "desktop traces detected",
            },
            {
                "source_id": "openai-api",
                "supported": True,
                "summary": "provider logs auto-discovered",
            },
        ],
    }


class ReleaseGateTests(unittest.TestCase):
    def test_release_gate_passes_for_current_registry_and_adapter_backing(self) -> None:
        adapter_source_ids = {
            "codex",
            "claude-code",
            "claude-desktop",
            "opencode",
            "minimax-agent",
            "qwen-code-cli",
            "kimi-cli",
            "gemini-cli",
            "kimi-desktop",
            "glm-desktop",
            "qwen-desktop",
            "deepseek-desktop",
            "doubao-desktop",
            "qianfan-desktop",
            "yuanbao-desktop",
            "perplexity-desktop",
            "stepfun-desktop",
            "sensenova-desktop",
            "baichuan-desktop",
            "siliconflow-desktop",
            "spark-desktop",
            "chatgpt-desktop",
            "gemini-desktop",
            "grok-desktop",
            "mistral-desktop",
            "openai-api",
            "anthropic-api",
            "google-gemini-api",
            "moonshot-kimi-api",
            "zhipu-glm-api",
            "qwen-api",
            "deepseek-api",
            "minimax-api",
            "xai-grok-api",
            "cohere-api",
            "mistral-api",
            "perplexity-api",
            "openrouter-api",
            "togetherai-api",
            "fireworks-api",
            "azure-openai-api",
            "baidu-qianfan-api",
            "tencent-hunyuan-api",
            "stepfun-api",
            "doubao-api",
            "sensenova-api",
            "baichuan-api",
            "siliconflow-api",
            "spark-api",
            "generic-openai-compatible",
        }

        payload = build_release_gate_payload(
            adapter_source_ids=adapter_source_ids,
            health_report=_health_report(),
        )

        self.assertEqual(payload["summary"]["status"], "pass")
        self.assertEqual(payload["registry_summary"]["total_ecosystems"], 20)
        self.assertEqual(payload["registry_summary"]["surface_maturity"]["exact-ready"], 60)
        self.assertEqual(payload["missing_backing_source_ids"], [])
        self.assertEqual(payload["metrics"]["default_duplicate_event_ratio"], 0.0)
        self.assertEqual(payload["platform_matrix"]["macos"]["covered_sources"], payload["platform_matrix"]["macos"]["total_sources"])
        self.assertEqual(payload["platform_matrix"]["windows"]["covered_sources"], payload["platform_matrix"]["windows"]["total_sources"])
        self.assertTrue(payload["platform_matrix"]["macos"]["supported"])
        self.assertTrue(payload["platform_matrix"]["windows"]["supported"])

    def test_release_gate_fails_when_adapter_backing_is_missing(self) -> None:
        payload = build_release_gate_payload(
            adapter_source_ids={"codex", "openai-api"},
            health_report=_health_report(),
        )

        self.assertEqual(payload["summary"]["status"], "fail")
        self.assertIn("claude-desktop", payload["missing_backing_source_ids"])
        false_ready_gate = next(item for item in payload["gates"] if item["gate_id"] == "false-ready-claims")
        self.assertEqual(false_ready_gate["status"], "fail")

    def test_duplicate_probe_proves_default_selection_avoids_generic_overlap(self) -> None:
        probe = _build_default_selection_duplicate_probe()

        self.assertEqual(probe["default_duplicate_event_ratio"], 0.0)
        self.assertGreater(probe["explicit_duplicate_event_ratio"], 0.0)
        self.assertIn("generic-openai-compatible", probe["manual_only_source_ids"])
        self.assertEqual(probe["default_sessions"], ["ms-1", "oa-1"])
        self.assertEqual(probe["explicit_sessions"], ["lab-1", "ms-1", "oa-1"])


if __name__ == "__main__":
    unittest.main()
