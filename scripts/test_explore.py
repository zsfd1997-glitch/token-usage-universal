from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import token_usage


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class ExploreTests(unittest.TestCase):
    def test_explore_menu_uses_plain_recent_choices_and_close(self) -> None:
        output = _TtyStringIO()
        with (
            patch.object(token_usage.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value="7"),
            redirect_stdout(output),
        ):
            result = token_usage.command_explore(None)

        rendered = output.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("最近一周 token 消耗情况", rendered)
        self.assertIn("最近一个月 token 消耗情况", rendered)
        self.assertIn("关闭", rendered)
        self.assertIn("已关闭", rendered)


if __name__ == "__main__":
    unittest.main()
