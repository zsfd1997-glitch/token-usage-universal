from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.file_cache import FileEventCache
from core.models import UsageEvent


def _sample_event(source_path: str) -> UsageEvent:
    return UsageEvent(
        source="codex",
        provider="openai",
        timestamp=datetime(2026, 3, 30, 10, 0, tzinfo=ZoneInfo("US/Pacific")),
        session_id="sess-1",
        project_path="/tmp/project-a",
        model="gpt-5.4",
        input_tokens=100,
        cached_input_tokens=40,
        output_tokens=20,
        reasoning_tokens=5,
        total_tokens=125,
        accuracy_level="exact",
        raw_event_kind="token_count",
        source_path=source_path,
        raw_model="gpt-5.4",
        model_resolution="exact",
        model_source="turn_context",
    )


class FileEventCacheTests(unittest.TestCase):
    def test_save_handles_concurrent_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_file = root / "rollout.jsonl"
            source_file.write_text('{"type":"token_count"}\n', encoding="utf-8")
            cache = FileEventCache(root / "cache")
            errors: list[BaseException] = []
            start = threading.Barrier(8)

            def worker() -> None:
                try:
                    start.wait()
                    for _ in range(25):
                        cache.save(
                            source_id="codex",
                            parser_version="codex-v1",
                            path=source_file,
                            events=[_sample_event(str(source_file))],
                            verification_issues=[],
                        )
                except BaseException as exc:  # pragma: no cover - assertion path
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            loaded = cache.load(
                source_id="codex",
                parser_version="codex-v1",
                path=source_file,
            )
            self.assertIsNotNone(loaded)
            events, issues = loaded or ([], [])
            self.assertEqual(issues, [])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].total_tokens, 125)


if __name__ == "__main__":
    unittest.main()
