from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TimeWindow:
    start: datetime | None
    end: datetime | None
    label: str
    timezone_name: str


@dataclass(frozen=True)
class UsageEvent:
    source: str
    provider: str
    timestamp: datetime
    session_id: str
    project_path: str | None
    model: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int
    accuracy_level: str
    raw_event_kind: str
    source_path: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass
class SourceDetection:
    source_id: str
    display_name: str
    provider: str
    accuracy_level: str
    supported: bool
    available: bool
    summary: str
    candidate_paths: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.supported and self.available:
            return "ready"
        if self.supported and not self.available:
            return "not-found"
        if not self.supported and self.available:
            return "detected-no-parser"
        return "not-configured"

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "provider": self.provider,
            "accuracy_level": self.accuracy_level,
            "supported": self.supported,
            "available": self.available,
            "status": self.status,
            "summary": self.summary,
            "candidate_paths": self.candidate_paths,
            "details": self.details,
        }


@dataclass
class SourceCollectResult:
    detection: SourceDetection
    events: list[UsageEvent] = field(default_factory=list)
    scanned_files: int = 0
    verification_issues: list[str] = field(default_factory=list)
    skipped_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "detection": self.detection.as_dict(),
            "events": [event.as_dict() for event in self.events],
            "scanned_files": self.scanned_files,
            "verification_issues": self.verification_issues,
            "skipped_reasons": self.skipped_reasons,
        }
