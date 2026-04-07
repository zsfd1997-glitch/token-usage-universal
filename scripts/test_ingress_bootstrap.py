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
    def test_profiles_payload_lists_global_and_china_priority_profiles(self) -> None:
        payload = build_ingress_profiles_payload()

        profile_ids = {item["profile_id"] for item in payload["profiles"]}
        self.assertIn("openai", profile_ids)
        self.assertIn("anthropic", profile_ids)
        self.assertIn("gemini", profile_ids)
        self.assertIn("openrouter", profile_ids)
        self.assertIn("perplexity", profile_ids)
        self.assertIn("xai", profile_ids)
        self.assertIn("mistral", profile_ids)
        self.assertIn("stepfun", profile_ids)
        self.assertIn("qwen", profile_ids)
        self.assertIn("kimi", profile_ids)
        self.assertIn("glm", profile_ids)
        self.assertIn("doubao", profile_ids)
        self.assertIn("minimax", profile_ids)
        self.assertIn("openai-compatible", profile_ids)
        self.assertIn("anthropic-compatible", profile_ids)
        self.assertIn("deepseek", profile_ids)
        self.assertIn("qianfan", profile_ids)
        self.assertIn("hunyuan", profile_ids)
        self.assertIn("sensenova", profile_ids)
        self.assertIn("baichuan", profile_ids)
        self.assertIn("siliconflow", profile_ids)
        self.assertIn("spark", profile_ids)
        self.assertEqual(payload["summary"]["profiles"], 22)
        self.assertEqual(payload["summary"]["protocols"]["openai"], 20)
        self.assertEqual(payload["summary"]["protocols"]["anthropic"], 2)

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

    def test_official_openai_profile_uses_embedded_upstream(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="openai",
            editor="vscode",
        )

        self.assertEqual(payload["profile"]["profile_id"], "openai")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.openai.com/v1")
        self.assertIn("model: gpt-4.1", payload["continue"]["snippet"])
        self.assertEqual(payload["cli"]["shell_exports"]["OPENAI_BASE_URL"], "http://127.0.0.1:8787/v1")

    def test_official_anthropic_profile_uses_embedded_upstream(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="anthropic",
            editor="jetbrains",
        )

        self.assertEqual(payload["profile"]["profile_id"], "anthropic")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.anthropic.com")
        self.assertIn("model: claude-sonnet-4-20250514", payload["continue"]["snippet"])
        self.assertEqual(payload["cli"]["shell_exports"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8787")

    def test_perplexity_profile_keeps_root_openai_base_path(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="perplexity",
            editor="vscode",
        )

        self.assertEqual(payload["profile"]["profile_id"], "perplexity")
        self.assertEqual(payload["profile"]["local_base_path"], "")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787")
        self.assertEqual(payload["companion"]["upstream_base_url"], "https://api.perplexity.ai")
        self.assertIn("model: sonar-pro", payload["continue"]["snippet"])

    def test_gemini_profile_uses_openai_compat_path(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="gemini",
            editor="vscode",
        )

        self.assertEqual(payload["profile"]["profile_id"], "gemini")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/v1beta/openai")
        self.assertEqual(
            payload["companion"]["upstream_base_url"],
            "https://generativelanguage.googleapis.com/v1beta/openai",
        )
        self.assertIn("model: gemini-2.5-flash", payload["continue"]["snippet"])

    def test_qwen_profile_uses_dashscope_compat_path(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="qwen",
            editor="jetbrains",
        )

        self.assertEqual(payload["profile"]["profile_id"], "qwen")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/compatible-mode/v1")
        self.assertEqual(
            payload["companion"]["upstream_base_url"],
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertIn("model: qwen3-coder-plus", payload["continue"]["snippet"])

    def test_glm_profile_uses_coding_endpoint_path(self) -> None:
        payload = build_ingress_bootstrap_payload(
            profile_id="glm",
            editor="vscode",
        )

        self.assertEqual(payload["profile"]["profile_id"], "glm")
        self.assertEqual(payload["companion"]["local_base_url"], "http://127.0.0.1:8787/api/coding/paas/v4")
        self.assertEqual(
            payload["companion"]["upstream_base_url"],
            "https://open.bigmodel.cn/api/coding/paas/v4",
        )
        self.assertIn("model: glm-4.7", payload["continue"]["snippet"])


if __name__ == "__main__":
    unittest.main()
