from __future__ import annotations

from core.models import SourceCollectResult, SourceDetection, TimeWindow


class BaseAdapter:
    source_id = ""
    display_name = ""
    provider = ""
    accuracy_level = "unsupported"
    default_selected = True
    default_selected = True

    def detect(self) -> SourceDetection:
        raise NotImplementedError

    def collect(self, window: TimeWindow) -> SourceCollectResult:
        raise NotImplementedError

    def collect_chart(self, window: TimeWindow) -> SourceCollectResult:
        return self.collect(window)
