from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.ecosystem_registry import build_top20_registry_payload, build_top20_registry_summary, list_top20_ecosystem_targets


class EcosystemRegistryTests(unittest.TestCase):
    def test_registry_contains_frozen_top20_ecosystems(self) -> None:
        ecosystems = list_top20_ecosystem_targets()
        ecosystem_ids = {item.ecosystem_id for item in ecosystems}

        self.assertEqual(len(ecosystems), 20)
        self.assertIn("qwen", ecosystem_ids)
        self.assertIn("kimi", ecosystem_ids)
        self.assertIn("glm", ecosystem_ids)
        self.assertIn("openai", ecosystem_ids)
        self.assertIn("anthropic", ecosystem_ids)

    def test_registry_summary_counts_china_priority_and_surfaces(self) -> None:
        summary = build_top20_registry_summary()

        self.assertEqual(summary["total_ecosystems"], 20)
        self.assertEqual(summary["china_priority_ecosystems"], 13)
        self.assertEqual(summary["global_ecosystems"], 7)
        self.assertEqual(summary["total_surfaces"], 60)
        self.assertIn("native-client", summary["surface_primary_lanes"])
        self.assertIn("ingress-capture", summary["surface_primary_lanes"])

    def test_payload_exposes_scope_and_surface_details(self) -> None:
        payload = build_top20_registry_payload()

        self.assertEqual(payload["scope"]["frozen_by"], "ecosystem/client-family")
        self.assertEqual(payload["scope"]["surfaces"], ["desktop", "cli", "ide"])
        qwen = next(item for item in payload["ecosystems"] if item["ecosystem_id"] == "qwen")
        kimi = next(item for item in payload["ecosystems"] if item["ecosystem_id"] == "kimi")
        self.assertEqual(qwen["provider_source_ids"], ["qwen-api"])
        self.assertEqual(len(qwen["surfaces"]), 3)
        self.assertEqual(qwen["surfaces"][0]["surface_type"], "desktop")
        self.assertEqual(qwen["surfaces"][1]["implemented_source_ids"], ["qwen-code-cli"])
        self.assertEqual(qwen["surfaces"][1]["maturity"], "exact-ready")
        self.assertEqual(kimi["surfaces"][1]["implemented_source_ids"], ["kimi-cli"])
        self.assertEqual(kimi["surfaces"][1]["maturity"], "exact-ready")
        deepseek = next(item for item in payload["ecosystems"] if item["ecosystem_id"] == "deepseek")
        baichuan = next(item for item in payload["ecosystems"] if item["ecosystem_id"] == "baichuan")
        self.assertEqual(deepseek["surfaces"][1]["maturity"], "exact-ready")
        self.assertEqual(deepseek["surfaces"][2]["implemented_source_ids"], ["deepseek-ide-proxy"])
        self.assertEqual(baichuan["surfaces"][1]["implemented_source_ids"], ["baichuan-cli-proxy"])
        self.assertEqual(baichuan["surfaces"][2]["maturity"], "exact-ready")


if __name__ == "__main__":
    unittest.main()
