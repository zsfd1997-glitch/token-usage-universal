from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.pricing import PricingDatabase


class PricingTests(unittest.TestCase):
    def test_same_db_path_reuses_singleton_instance(self) -> None:
        first = PricingDatabase()
        second = PricingDatabase()
        self.assertIs(first, second)

    def test_alias_resolution_hits_known_model(self) -> None:
        pricing = PricingDatabase()
        resolved = pricing.resolve("openai/gpt-5.4", "openai")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["provider"], "openai")

    def test_reasoning_falls_back_to_output_rate(self) -> None:
        pricing = PricingDatabase()
        cost = pricing.estimate_cost(
            model="gpt-5.4",
            provider="openai",
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=1_000_000,
            reasoning_tokens=1_000_000,
        )
        self.assertAlmostEqual(cost, 30.0, places=2)

    def test_cost_excludes_cached_input_by_default(self) -> None:
        pricing = PricingDatabase()
        cost = pricing.estimate_cost(
            model="gpt-5.4",
            provider="openai",
            input_tokens=900_000,
            cached_input_tokens=100_000,
            output_tokens=180_000,
            reasoning_tokens=20_000,
            total_tokens=1_100_000,
        )
        self.assertAlmostEqual(cost, 5.0, places=2)

    def test_cost_can_include_cached_input_when_requested(self) -> None:
        pricing = PricingDatabase()
        cost = pricing.estimate_cost(
            model="gpt-5.4",
            provider="openai",
            input_tokens=900_000,
            cached_input_tokens=100_000,
            output_tokens=180_000,
            reasoning_tokens=20_000,
            total_tokens=1_100_000,
            count_cached_input=True,
        )
        self.assertAlmostEqual(cost, 5.025, places=3)

    def test_unknown_model_returns_none(self) -> None:
        pricing = PricingDatabase()
        self.assertIsNone(pricing.resolve("totally-unknown-model", "unknown"))


if __name__ == "__main__":
    unittest.main()
