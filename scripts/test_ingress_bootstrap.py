from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.ingress_bootstrap import build_ingress_bootstrap_payload, build_ingress_profiles_payload


class IngressBootstrapTests(unittest.TestCase):
    def test_profiles_payload_lists_generic_and_china_priority_profiles(self) -> None:
        payload = build_ingress_profiles_payload()

        profile_ids = {item["profile_id"] for item in payload["profiles"]}
        self.assertIn("openai-compatible", profile_ids)
        self.assertIn("anthropic-compatible", profile_ids)
        self.assertIn("deepseek", profile_ids)
        self.assertIn("qianfan", profile_ids)
        self.assertIn("hunyuan", profile_ids)
        self.assertIn("sensenova", profile_ids)
        self.assertIn("baichuan", profile_ids)
        self.assertIn("siliconflow", profile_ids)
        self.assertIn("spark", profile_ids)

    def test_deepseek_bootstrap_builds_continue_and_cli_samples(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="deepseek",
            editor="vscode",
            project_path="/tmp/project",
        )

        self.assertEqual(payload["profile"]["protocol"], "openai")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/v1")
        self.assertIn("provider: openai", payload["continue"]["snippet"])
        self.assertIn("model: deepseek-chat", payload["continue"]["snippet"])
        self.assertEqual(
            payload["cli"]["shell_exports"]["OPENAI_BASE_URL"],
            "http://127.0.0.1:8787/v1",
        )
        self.assertEqual(
            payload["cli"]["shell_exports"]["OPENAI_API_KEY"],
            "$DEEPSEEK_API_KEY",
        )

    def test_generic_anthropic_profile_requires_upstream_override(self) -> None:
        with self.assertRaises(ValueError):
            build_ingress_bootstrap_payload(
                profile_id="anthropic-compatible",
                editor="jetbrains",
            )

    def test_baichuan_profile_accepts_manual_upstream(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="baichuan",
            editor="jetbrains",
            upstream_base_url="https://api.baichuan-ai.example/v1",
        )

        self.assertEqual(payload["profile"]["profile_id"], "baichuan")
        self.assertEqual(payload["editor"]["id"], "jetbrains")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.baichuan-ai.example/v1")
        self.assertIn("Baichuan4-Turbo", payload["continue"]["snippet"])


if __name__ == "__main__":
    unittest.main()
