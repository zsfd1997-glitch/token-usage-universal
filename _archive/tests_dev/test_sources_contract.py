from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "scripts" / "token_usage.py"


def _run_sources_json() -> list[dict[str, object]]:
    output = subprocess.check_output(
        [sys.executable, str(CLI), "sources", "--format", "json"],
        text=True,
    )
    return json.loads(output)


class SourcesContractTests(unittest.TestCase):
    def test_every_source_exposes_rollup_metadata(self) -> None:
        payload = _run_sources_json()

        for item in payload:
            with self.subTest(source=item["source_id"]):
                self.assertIn("in_default_rollup", item)
                self.assertIn("detection", item)
                self.assertEqual(item["source_id"], item["detection"]["source_id"])
                self.assertEqual(item["in_default_rollup"], item["detection"]["in_default_rollup"])

    def test_generic_is_not_in_default_rollup(self) -> None:
        payload = _run_sources_json()
        generic = next(item for item in payload if item["source_id"] == "generic-openai-compatible")

        self.assertFalse(generic["in_default_rollup"])
        self.assertFalse(generic["detection"]["in_default_rollup"])

    def test_provider_families_are_independent_sources(self) -> None:
        payload = _run_sources_json()
        ids = {item["source_id"] for item in payload}

        for required in [
            "openai-api",
            "anthropic-api",
            "deepseek-api",
            "moonshot-kimi-api",
            "zhipu-glm-api",
            "qwen-api",
        ]:
            with self.subTest(source_id=required):
                self.assertIn(required, ids)

    def test_core_native_sources_always_present(self) -> None:
        payload = _run_sources_json()
        ids = {item["source_id"] for item in payload}

        for required in [
            "codex",
            "claude-code",
            "claude-desktop",
            "opencode",
            "minimax-agent",
        ]:
            with self.subTest(source_id=required):
                self.assertIn(required, ids)


if __name__ == "__main__":
    unittest.main()
