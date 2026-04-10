from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
README_TEXT = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
CONFIG_TEXT = (REPO_ROOT / "scripts" / "core" / "config.py").read_text(encoding="utf-8")


def _readme_env_keys() -> set[str]:
    return set(re.findall(r"`(TOKEN_USAGE_[A-Z_]+)`", README_TEXT))


def _config_env_keys() -> set[str]:
    module = ast.parse(CONFIG_TEXT)
    keys: set[str] = set()
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.endswith("_ENV"):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            keys.add(node.value.value)
    return keys


class EnvRegistryContractTests(unittest.TestCase):
    def test_readme_lists_every_env_key_used_in_code(self) -> None:
        missing = _config_env_keys() - _readme_env_keys()
        self.assertFalse(
            missing,
            f"README 漏掉了 core/config.py 里在用的 env：{sorted(missing)}",
        )

    def test_readme_does_not_list_dead_env_keys(self) -> None:
        dead = _readme_env_keys() - _config_env_keys()
        self.assertFalse(
            dead,
            f"README 里挂了已经失效的 env：{sorted(dead)}",
        )


if __name__ == "__main__":
    unittest.main()
