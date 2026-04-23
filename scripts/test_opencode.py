from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapters.opencode import OpenCodeAdapter
from core.models import TimeWindow
from test_time import PACIFIC_TZ


def _window() -> TimeWindow:
    tzinfo = PACIFIC_TZ
    return TimeWindow(
        start=datetime(2026, 3, 25, 0, 0, tzinfo=tzinfo),
        end=datetime(2026, 3, 25, 23, 59, tzinfo=tzinfo),
        label="Today (2026-03-25 PDT)",
        timezone_name="US/Pacific",
    )


class OpenCodeAdapterTests(unittest.TestCase):
    def test_detect_and_collect_exact_usage_via_local_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "storage" / "session" / "global"
            message_dir = root / "storage" / "message" / "ses_local"
            completed_at = int(datetime(2026, 3, 25, 12, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
            created_at = int(datetime(2026, 3, 25, 11, 59, tzinfo=PACIFIC_TZ).timestamp() * 1000)
            session_dir.mkdir(parents=True)
            message_dir.mkdir(parents=True)

            (session_dir / "ses_local.json").write_text(
                json.dumps(
                    {
                        "id": "ses_local",
                        "projectID": "global",
                        "directory": "/tmp/local-demo",
                        "time": {"created": created_at, "updated": completed_at},
                    }
                ),
                encoding="utf-8",
            )
            (root / "storage" / "project").mkdir(parents=True)
            (root / "storage" / "project" / "global.json").write_text(
                json.dumps({"id": "global", "worktree": "/tmp/local-demo"}),
                encoding="utf-8",
            )
            (message_dir / "msg_local.json").write_text(
                json.dumps(
                    {
                        "id": "msg_local",
                        "sessionID": "ses_local",
                        "role": "assistant",
                        "time": {"created": created_at, "completed": completed_at},
                        "modelID": "minimax-m2.1-free",
                        "providerID": "opencode",
                        "path": {"cwd": "/tmp/local-demo", "root": "/tmp/local-demo"},
                        "tokens": {
                            "input": 200,
                            "output": 50,
                            "reasoning": 3,
                            "cache": {"read": 40, "write": 10},
                        },
                    }
                ),
                encoding="utf-8",
            )

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            with patch.object(adapter, "_resolve_cli", return_value=None):
                detection = adapter.detect()
                result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(detection.summary, "OpenCode local storage produced exact token usage records")
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].provider, "opencode")
        self.assertEqual(result.events[0].project_path, "/tmp/local-demo")
        self.assertEqual(result.events[0].input_tokens, 210)
        self.assertEqual(result.events[0].cached_input_tokens, 40)
        self.assertEqual(result.events[0].output_tokens, 50)
        self.assertEqual(result.events[0].reasoning_tokens, 3)
        self.assertEqual(result.events[0].total_tokens, 303)
        self.assertEqual(result.events[0].raw_event_kind, "opencode_local:message_json")

    def test_gbk_encoded_message_file_still_yields_tokens(self) -> None:
        """GBK intranet regression: a GBK-encoded message file must not
        silently produce 0 events — robust_read should decode it and the
        adapter should extract the usage the same as UTF-8 data."""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "storage" / "session"
            message_dir = root / "storage" / "message" / "ses_gbk"
            session_dir.mkdir(parents=True)
            message_dir.mkdir(parents=True)

            (session_dir / "ses_gbk.json").write_bytes(
                json.dumps(
                    {
                        "id": "ses_gbk",
                        "projectID": "proj-gbk",
                        "directory": "/tmp/gbk-项目",
                        "time": {"created": created_at, "updated": completed_at},
                    },
                    ensure_ascii=False,
                ).encode("gbk")
            )
            (root / "storage" / "project").mkdir(parents=True)
            (root / "storage" / "project" / "proj-gbk.json").write_bytes(
                json.dumps(
                    {"id": "proj-gbk", "worktree": "/tmp/gbk-项目"},
                    ensure_ascii=False,
                ).encode("gbk")
            )
            (message_dir / "msg_gbk.json").write_bytes(
                json.dumps(
                    {
                        "id": "msg_gbk",
                        "sessionID": "ses_gbk",
                        "role": "assistant",
                        "time": {"created": created_at, "completed": completed_at},
                        "modelID": "qwen-max",
                        "providerID": "opencode",
                        "path": {"cwd": "/tmp/gbk-项目", "root": "/tmp/gbk-项目"},
                        "tokens": {
                            "input": 500,
                            "output": 120,
                            "reasoning": 0,
                            "cache": {"read": 100, "write": 0},
                        },
                    },
                    ensure_ascii=False,
                ).encode("gbk")
            )

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            with patch.object(adapter, "_resolve_cli", return_value=None):
                result = adapter.collect(_window())

        self.assertEqual(len(result.events), 1, "GBK-encoded message file silently produced 0 events")
        event = result.events[0]
        self.assertEqual(event.total_tokens, 720)
        self.assertEqual(event.input_tokens, 500)
        self.assertEqual(event.cached_input_tokens, 100)
        self.assertEqual(event.output_tokens, 120)
        self.assertEqual(event.project_path, "/tmp/gbk-项目")

    def test_detect_and_collect_exact_usage_via_cli_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps([{"id": "ses_1", "updated_at": "2026-03-25T12:00:00-07:00", "title": "demo"}]),
                        stderr="",
                    )
                if args == ("export", "ses_1"):
                    return subprocess.CompletedProcess(
                        args,
                        0,
                        stdout=json.dumps(
                            {
                                "id": "ses_1",
                                "project": "/tmp/demo",
                                "messages": [
                                    {
                                        "created_at": "2026-03-25T12:00:00-07:00",
                                        "model": "moonshot/kimi-k2",
                                        "usage": {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250},
                                    }
                                ],
                            }
                        ),
                        stderr="",
                    )
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode"), patch.object(
                adapter,
                "_run_cli",
                side_effect=fake_run,
            ):
                detection = adapter.detect()
                result = adapter.collect(_window())

        self.assertTrue(detection.available)
        self.assertEqual(result.scanned_files, 1)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].provider, "moonshot")
        self.assertEqual(result.events[0].total_tokens, 250)
        self.assertEqual(result.events[0].session_id, "ses_1")

    def test_resolve_cli_prefers_opencode_cli_binary_over_gui(self) -> None:
        """Problem 1 regression: on Windows both opencode.exe (GUI) and
        opencode-cli.exe can coexist in PATH. The adapter must pick the CLI."""
        adapter = OpenCodeAdapter()

        gui_path = "C:\\OpenCode\\OpenCode.exe"
        cli_path = "D:\\OpenCode\\opencode-cli.exe"

        def fake_which(name: str) -> str | None:
            mapping = {
                "opencode-cli.exe": cli_path,
                "opencode.exe": gui_path,
                "opencode-cli": None, "opencode-cli.cmd": None,
                "opencode": None, "opencode.cmd": None,
            }
            return mapping.get(name)

        with patch("adapters.opencode.shutil.which", side_effect=fake_which), patch.dict(
            "os.environ", {}, clear=False,
        ):
            os.environ.pop("TOKEN_USAGE_OPENCODE_BIN", None)
            resolved = adapter._resolve_cli()

        self.assertEqual(resolved, cli_path, "adapter picked the GUI binary over opencode-cli")

    def test_opencode_v1_1_13_export_shape_with_info_and_parts(self) -> None:
        """Problem 4 regression: export format {"messages": [{"info": {...},
        "parts": [{"tokens": {...}}]}]} must yield events — iter_usage_carriers
        alone can't cross info/parts siblings."""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            export_payload = {
                "messages": [
                    {
                        "info": {
                            "id": "msg_1",
                            "sessionID": "ses_v1_1_13",
                            "role": "assistant",
                            "providerID": "aliyun",
                            "modelID": "qwen3-coder-plus",
                            "time": {"created": created_at, "completed": completed_at},
                            "path": {"root": "D:\\知识库", "cwd": "D:\\知识库"},
                        },
                        "parts": [
                            {"type": "reasoning", "tokens": {"input": 13000, "output": 30, "reasoning": 5, "cache": {"read": 500, "write": 0}}},
                            {"type": "reasoning", "tokens": {"input": 13964, "output": 70, "reasoning": 37, "cache": {"read": 500, "write": 0}}},
                        ],
                    },
                    {
                        "info": {"id": "msg_0", "sessionID": "ses_v1_1_13", "role": "user"},
                        "parts": [{"type": "text", "text": "hi"}],
                    },
                ]
            }

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(
                        args, 0,
                        stdout=json.dumps([{"id": "ses_v1_1_13", "updated_at": "2026-03-25T10:00:00-07:00", "title": "demo"}]),
                        stderr="",
                    )
                if args == ("export", "ses_v1_1_13"):
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps(export_payload), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode-cli"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        self.assertEqual(len(result.events), 1, "v1.1.13 export shape silently returned 0 events")
        event = result.events[0]
        # Best-part picker took the larger total
        self.assertEqual(event.total_tokens, 14571)  # 13964 + 500 + 70 + 37
        self.assertEqual(event.input_tokens, 13964)
        self.assertEqual(event.cached_input_tokens, 500)
        self.assertEqual(event.output_tokens, 70)
        self.assertEqual(event.reasoning_tokens, 37)
        self.assertEqual(event.provider, "aliyun")
        self.assertIn("qwen3-coder-plus", (event.model or "", event.raw_model or ""))
        self.assertEqual(event.project_path, "D:\\知识库")

    def test_cli_export_uses_local_cwd_not_session_list_directory(self) -> None:
        """Problem 5 regression: when session list returns a mojibake
        `directory` field (Windows cp936 leaking), we must prefer the UTF-8
        path recovered from local message JSON."""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_project = root / "project-utf8"
            real_project.mkdir()

            session_dir = root / "storage" / "session"
            message_dir = root / "storage" / "message" / "ses_cwd"
            session_dir.mkdir(parents=True)
            message_dir.mkdir(parents=True)

            # Local message file carries the CORRECT path (UTF-8 JSON on disk),
            # but has no tokens field — so local scan yields 0 events and
            # forces the adapter into the CLI-export code path.
            (session_dir / "ses_cwd.json").write_text(
                json.dumps({"id": "ses_cwd", "directory": str(real_project), "time": {"created": created_at}}),
                encoding="utf-8",
            )
            (message_dir / "msg_user.json").write_text(
                json.dumps({
                    "id": "msg_user", "sessionID": "ses_cwd", "role": "user",
                    "time": {"created": created_at},
                    "path": {"root": str(real_project)},
                }),
                encoding="utf-8",
            )

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            observed_cwds: list[str | None] = []

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(
                        args, 0,
                        stdout=json.dumps([{
                            "id": "ses_cwd",
                            "updated_at": "2026-03-25T10:00:00-07:00",
                            # Garbled mojibake path — NOT a real directory
                            "directory": "D:\\֪ʶ",
                            "title": "demo",
                        }]),
                        stderr="",
                    )
                if args == ("export", "ses_cwd"):
                    observed_cwds.append(cwd)
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                        "messages": [{
                            "info": {
                                "id": "msg_1", "sessionID": "ses_cwd", "role": "assistant",
                                "providerID": "aliyun", "modelID": "qwen3-coder-plus",
                                "time": {"created": created_at, "completed": completed_at},
                                "path": {"root": str(real_project)},
                            },
                            "parts": [{"type": "reasoning", "tokens": {"input": 100, "output": 50, "reasoning": 0, "cache": {"read": 0, "write": 0}}}],
                        }],
                    }), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode-cli"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        # cwd for export must be the REAL UTF-8 path, not the mojibake one.
        # (detect phase + collect phase each call export once, so observed >= 1.)
        self.assertGreaterEqual(len(observed_cwds), 1)
        for cwd in observed_cwds:
            self.assertEqual(cwd, str(real_project), f"adapter used mojibake directory: {cwd}")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].total_tokens, 150)

    def test_cli_export_skips_nonexistent_cwd_gracefully(self) -> None:
        """Problem 5 corollary: if NO valid cwd can be derived, the adapter
        still calls export without a cwd instead of crashing."""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            observed_cwds: list[str | None] = []

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(
                        args, 0,
                        stdout=json.dumps([{
                            "id": "ses_bad_cwd", "updated_at": "2026-03-25T10:00:00-07:00",
                            "directory": "/this/path/definitely/does/not/exist/中文",
                            "title": "demo",
                        }]),
                        stderr="",
                    )
                if args == ("export", "ses_bad_cwd"):
                    observed_cwds.append(cwd)
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                        "messages": [{
                            "info": {"id": "m", "sessionID": "ses_bad_cwd", "role": "assistant",
                                     "providerID": "x", "modelID": "y",
                                     "time": {"completed": created_at + 1000}},
                            "parts": [{"type": "reasoning", "tokens": {"input": 10, "output": 5, "reasoning": 0, "cache": {"read": 0, "write": 0}}}],
                        }],
                    }), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode-cli"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        # Each observed cwd must be None — the nonexistent path should never
        # reach subprocess (detect phase + collect phase each may call).
        self.assertGreaterEqual(len(observed_cwds), 1)
        for cwd in observed_cwds:
            self.assertIsNone(cwd, f"nonexistent cwd leaked to subprocess: {cwd}")
        self.assertEqual(len(result.events), 1)
        any_cwd_note = any("didn't exist on this machine" in issue for issue in result.verification_issues)
        self.assertTrue(any_cwd_note, f"expected mojibake-cwd diagnostic, got {result.verification_issues}")

    def test_opencode_cli_v1_1_13_end_to_end_windows_intranet_scenario(self) -> None:
        """完整复现用户内网 Windows 机器的真实形态，v1.1.13 全链路必过：

        1. Desktop 写 opencode.global.dat（JSON 编码的 sessions registry），
           没有 storage/session/*.json 树
        2. opencode-cli.exe 在 %APPDATA%\\opencode-cli\\ 下写 storage
           （默认根不含 -cli 后缀，靠新的默认根 + env 覆盖才扫得到）
        3. session list 不接 --max-count（v1.1.13 不认）
        4. session list 本身返回 [] （项目作用域问题，desktop 的全局
           session 只在 .dat 里暴露）
        5. export 返回 v1.1.13 的 {messages: [{info:{...}, parts:[
           {tokens:{input, output, reasoning, cache:{read,write}}}]}]}
           嵌套格式
        6. 项目路径是中文（模拟内网用户的 D:\\知识库）

        期望：adapter 能从 .dat 拿到 session list，自动带上正确中文
        cwd 调 export，解出 v1.1.13 token schema，合并 desktop + CLI
        的 token 数据，不是 0，不是重复计数。
        """
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        created_2 = int(datetime(2026, 3, 25, 14, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_2 = int(datetime(2026, 3, 25, 14, 0, 45, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / "AppData" / "Roaming"
            # 两个独立根：desktop 和 opencode-cli 各自用自己的
            desktop_root = appdata / "OpenCode"
            cli_root = appdata / "opencode-cli"
            real_project = Path(tmp) / "projects" / "knowledge-base"
            real_project.mkdir(parents=True)
            desktop_root.mkdir(parents=True)
            cli_root.mkdir(parents=True)

            # Desktop: 只有 opencode.global.dat，无 storage/session 树
            (desktop_root / "opencode.global.dat").write_text(
                json.dumps({
                    "sessions": [
                        {
                            "id": "ses_desktop_1",
                            "directory": str(real_project),
                            "projectID": "proj-knowledge",
                            "time": {"created": created_at, "updated": completed_at},
                        },
                    ],
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            (desktop_root / "log").mkdir()
            (desktop_root / "log" / "2026-03-25.log").write_text("desktop session", encoding="utf-8")

            # CLI: 老式 storage/session + storage/message 树（v1.1.13 短键）
            cli_session_dir = cli_root / "storage" / "session"
            cli_message_dir = cli_root / "storage" / "message" / "ses_cli_1"
            cli_session_dir.mkdir(parents=True)
            cli_message_dir.mkdir(parents=True)
            (cli_session_dir / "ses_cli_1.json").write_text(
                json.dumps({
                    "id": "ses_cli_1",
                    "projectID": "proj-knowledge",
                    "directory": str(real_project),
                    "time": {"created": created_2, "updated": completed_2},
                }),
                encoding="utf-8",
            )
            (cli_message_dir / "msg_cli_1.json").write_text(
                json.dumps({
                    "id": "msg_cli_1",
                    "sessionID": "ses_cli_1",
                    "role": "assistant",
                    "time": {"created": created_2, "completed": completed_2},
                    "modelID": "qwen3-coder-plus",
                    "providerID": "aliyun",
                    "path": {"cwd": str(real_project), "root": str(real_project)},
                    "tokens": {
                        "input": 2000,
                        "output": 150,
                        "reasoning": 10,
                        "cache": {"read": 500, "write": 100},
                    },
                }),
                encoding="utf-8",
            )

            adapter = OpenCodeAdapter()
            # 同时配两端的 root，模拟 desktop+cli 并存
            adapter.roots = [desktop_root, cli_root]

            def fake_run(*args, timeout: int, cwd: str | None = None):
                # session list 项目作用域空返——desktop 全局 session 只
                # 在 .dat 里；CLI 侧已经被本地 storage 路径吃掉了。
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")
                if args == ("export", "ses_desktop_1"):
                    # 必须用 .dat 里记录的项目路径（中文），验证 cwd 正确
                    assert cwd == str(real_project), f"export cwd 不对: {cwd}"
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                        "messages": [{
                            "info": {
                                "id": "msg_desktop_1",
                                "sessionID": "ses_desktop_1",
                                "role": "assistant",
                                "providerID": "anthropic",
                                "modelID": "claude-sonnet-4-6",
                                "time": {"created": created_at, "completed": completed_at},
                                "path": {"root": str(real_project)},
                            },
                            "parts": [{
                                "type": "reasoning",
                                "tokens": {
                                    "input": 1500,
                                    "output": 200,
                                    "reasoning": 25,
                                    "cache": {"read": 300, "write": 50},
                                },
                            }],
                        }],
                    }), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="D:\\OpenCode\\opencode-cli.exe"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        # 预期：CLI 本地路径捕获 msg_cli_1（local 优先，立刻返回）
        # 所以 session_id 应为 ses_cli_1，total_tokens = 2000 + 150 + 10 + 500 + 100 = 2760
        self.assertEqual(len(result.events), 1, "CLI 本地优先路径应该捕获 1 条 event")
        event = result.events[0]
        self.assertEqual(event.session_id, "ses_cli_1")
        self.assertEqual(event.total_tokens, 2760)  # input(2000+100 cache.write) + cache.read(500) + output(150) + reasoning(10)
        self.assertEqual(event.input_tokens, 2100)  # input + cache.write
        self.assertEqual(event.cached_input_tokens, 500)
        self.assertEqual(event.output_tokens, 150)
        self.assertEqual(event.reasoning_tokens, 10)
        self.assertEqual(event.project_path, str(real_project))
        self.assertIn("qwen3-coder-plus", (event.model or "", event.raw_model or ""))
        # accuracy 必须是 exact 不能降级
        self.assertEqual(event.accuracy_level, "exact")

    def test_opencode_cli_v1_1_13_desktop_only_when_no_cli_storage(self) -> None:
        """v1.1.13 纯 desktop 场景：没装 opencode-cli，只有 desktop 写的
        .dat + 没有 storage/session 树 → 必须靠 .dat → CLI export 链路
        把 token 拿出来。本测试把 CLI 本地路径彻底清空，强制走 .dat。"""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            desktop_root = Path(tmp) / "OpenCode"
            desktop_root.mkdir()
            real_project = Path(tmp) / "project-chinese"
            real_project.mkdir()

            (desktop_root / "opencode.global.dat").write_text(
                json.dumps({
                    "sessions": [
                        {"id": "ses_d", "directory": str(real_project),
                         "time": {"created": created_at}},
                    ],
                }),
                encoding="utf-8",
            )
            (desktop_root / "log").mkdir()
            (desktop_root / "log" / "2026-03-25.log").write_text("x", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [desktop_root]

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")
                if args == ("export", "ses_d"):
                    assert cwd == str(real_project)
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                        "messages": [{
                            "info": {
                                "id": "m1", "sessionID": "ses_d", "role": "assistant",
                                "providerID": "anthropic", "modelID": "claude-opus-4-6",
                                "time": {"created": created_at, "completed": completed_at},
                                "path": {"root": str(real_project)},
                            },
                            "parts": [{"type": "reasoning", "tokens": {
                                "input": 800, "output": 60, "reasoning": 5,
                                "cache": {"read": 0, "write": 0},
                            }}],
                        }],
                    }), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="opencode-cli"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        self.assertEqual(len(result.events), 1, "纯 desktop .dat 场景必须能 export 出 token")
        event = result.events[0]
        self.assertEqual(event.session_id, "ses_d")
        self.assertEqual(event.total_tokens, 865)  # 800 + 60 + 5

    def test_desktop_with_only_global_dat_falls_back_through_cli_export(self) -> None:
        """Desktop-only compat: no storage/session JSON tree, only an
        opencode.global.dat file. Previously the adapter returned 0 events
        because local scan found nothing and `opencode session list`
        returns [] when invoked outside any project cwd. Now the session
        list falls back to sessions parsed from .dat, and export uses the
        cwd carried on each .dat session entry."""
        created_at = int(datetime(2026, 3, 25, 10, 0, tzinfo=PACIFIC_TZ).timestamp() * 1000)
        completed_at = int(datetime(2026, 3, 25, 10, 0, 30, tzinfo=PACIFIC_TZ).timestamp() * 1000)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_project = root / "project-utf8"
            real_project.mkdir()

            # Write only opencode.global.dat — NO storage/session/ tree
            (root / "opencode.global.dat").write_text(
                json.dumps({
                    "sessions": [
                        {"id": "ses_dat", "directory": str(real_project),
                         "time": {"created": created_at}},
                    ],
                }),
                encoding="utf-8",
            )
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            def fake_run(*args, timeout: int, cwd: str | None = None):
                if args == ("session", "list", "--format", "json"):
                    # opencode's `session list` returns empty when the
                    # current cwd isn't any session's project dir —
                    # simulate that failure mode.
                    return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")
                if args == ("export", "ses_dat"):
                    assert cwd == str(real_project), f"export didn't receive .dat's cwd, got: {cwd}"
                    return subprocess.CompletedProcess(args, 0, stdout=json.dumps({
                        "messages": [{
                            "info": {
                                "id": "msg_1", "sessionID": "ses_dat", "role": "assistant",
                                "providerID": "opencode", "modelID": "minimax-m2.1-free",
                                "time": {"created": created_at, "completed": completed_at},
                                "path": {"root": str(real_project)},
                            },
                            "parts": [{"type": "reasoning", "tokens": {"input": 800, "output": 40, "reasoning": 2, "cache": {"read": 0, "write": 0}}}],
                        }],
                    }), stderr="")
                raise AssertionError(f"unexpected args: {args}")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                result = adapter.collect(_window())

        self.assertEqual(len(result.events), 1, "desktop-with-only-.dat fallback produced 0 events")
        event = result.events[0]
        self.assertEqual(event.session_id, "ses_dat")
        self.assertEqual(event.total_tokens, 842)  # 800 + 40 + 2
        self.assertEqual(event.project_path, str(real_project))

    def test_cli_session_list_does_not_pass_max_count_flag(self) -> None:
        """Regression: some opencode builds don't support --max-count and
        silently fail. We trim in Python instead of passing the flag."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            observed_args: list[tuple] = []

            def fake_run(*args, timeout: int, cwd: str | None = None):
                observed_args.append(args)
                if args[0:2] == ("session", "list"):
                    return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")
                return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")

            with patch.object(adapter, "_resolve_cli", return_value="/usr/local/bin/opencode"), patch.object(
                adapter, "_run_cli", side_effect=fake_run,
            ):
                adapter._load_cli_inventory()

        session_list_calls = [a for a in observed_args if a[0:2] == ("session", "list")]
        self.assertTrue(session_list_calls, "adapter didn't call session list at all")
        for call_args in session_list_calls:
            self.assertNotIn("--max-count", call_args, f"--max-count must not be in session list args: {call_args}")

    def test_detect_reports_local_data_when_cli_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log").mkdir()
            (root / "log" / "2026-03-25.log").write_text("sample", encoding="utf-8")
            (root / "prompt-history.jsonl").write_text("{}", encoding="utf-8")

            adapter = OpenCodeAdapter()
            adapter.roots = [root]

            with patch.object(adapter, "_resolve_cli", return_value=None):
                detection = adapter.detect()

        self.assertFalse(detection.available)
        self.assertEqual(detection.status, "not-found")
        self.assertIn("no exact token-bearing assistant message JSON or CLI export", detection.summary)


if __name__ == "__main__":
    unittest.main()
