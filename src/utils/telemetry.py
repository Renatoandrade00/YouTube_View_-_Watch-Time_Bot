from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class DetectionEvent:
    worker_id: int
    session_id: int
    event_type: str
    detail: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


_collector: TelemetryCollector | None = None


def get_collector() -> TelemetryCollector:
    global _collector
    if _collector is None:
        _collector = TelemetryCollector()
    return _collector


class TelemetryCollector:
    def __init__(self) -> None:
        self.events: List[DetectionEvent] = []

    def record(self, worker_id: int, session_id: int, event_type: str, detail: str = "") -> None:
        self.events.append(DetectionEvent(worker_id=worker_id, session_id=session_id, event_type=event_type, detail=detail))

    def summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.events:
            out[e.event_type] = out.get(e.event_type, 0) + 1
        return out

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [
            {
                "worker_id": e.worker_id,
                "session_id": e.session_id,
                "event_type": e.event_type,
                "detail": e.detail,
                "created_at": e.created_at,
            }
            for e in self.events[-limit:]
        ]
