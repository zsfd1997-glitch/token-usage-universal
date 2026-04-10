from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class GeneratedDocsContractTests(unittest.TestCase):
    def test_coverage_doc_is_up_to_date(self) -> None:
        subprocess.check_call(
            [sys.executable, "scripts/build_coverage_doc.py", "--check"],
            cwd=REPO_ROOT,
        )

    def test_env_doc_is_up_to_date(self) -> None:
        subprocess.check_call(
            [sys.executable, "scripts/build_env_doc.py", "--check"],
            cwd=REPO_ROOT,
        )


if __name__ == "__main__":
    unittest.main()
