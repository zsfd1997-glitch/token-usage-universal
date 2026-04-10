from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from core.file_cache import FileEventCache
from core.models import UsageEvent
from test_time import PACIFIC_TZ


BASELINE = json.loads(
    (
        Path(__file__).resolve().parent / "fixtures" / "performance" / "file_cache_baseline.json"
    ).read_text(encoding="utf-8")
)


def _sample_event(source_path: str) -> UsageEvent:
    return UsageEvent(
        source="codex",
        provider="openai",
        timestamp=datetime(2026, 3, 30, 10, 0, tzinfo=PACIFIC_TZ),
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

    def test_file_cache_1000_session_performance_stays_within_baseline(self) -> None:
        session_count = int(BASELINE["session_count"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "sessions"
            source_dir.mkdir(parents=True)
            source_files = []
            for index in range(session_count):
                source_file = source_dir / f"rollout-{index:04d}.jsonl"
                source_file.write_text('{"type":"token_count"}\n', encoding="utf-8")
                source_files.append(source_file)

            cache = FileEventCache(root / "cache")

            save_start = time.perf_counter()
            for source_file in source_files:
                cache.save(
                    source_id="codex",
                    parser_version="codex-v1",
                    path=source_file,
                    events=[_sample_event(str(source_file))],
                    verification_issues=[],
                )
            save_seconds = time.perf_counter() - save_start

            load_start = time.perf_counter()
            for source_file in source_files:
                loaded = cache.load(
                    source_id="codex",
                    parser_version="codex-v1",
                    path=source_file,
                )
                self.assertIsNotNone(loaded)
            load_seconds = time.perf_counter() - load_start

        self.assertLessEqual(
            save_seconds,
            float(BASELINE["max_save_seconds"]),
            f"1000 session save regression: {save_seconds:.3f}s > baseline {BASELINE['max_save_seconds']}s",
        )
        self.assertLessEqual(
            load_seconds,
            float(BASELINE["max_load_seconds"]),
            f"1000 session load regression: {load_seconds:.3f}s > baseline {BASELINE['max_load_seconds']}s",
        )


if __name__ == "__main__":
    unittest.main()
