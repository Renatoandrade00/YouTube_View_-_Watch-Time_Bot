from __future__ import annotations

from datetime import datetime
from typing import Any


def is_within_active_window(config: Any, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now()

    active_days = getattr(config, "active_days", None) or []
    if active_days:
        if now.weekday() not in active_days:
            return False

    start = getattr(config, "active_hours_start", None)
    end = getattr(config, "active_hours_end", None)
    if start is None or end is None:
        return True

    hour = now.hour
    if start <= end:
        return start <= hour < end
    # Janela que cruza meia-noite
    return hour >= start or hour < end


def seconds_until_next_window(config: Any, now: datetime | None = None) -> float:
    if now is None:
        now = datetime.now()
    if is_within_active_window(config, now):
        return 0.0
    # Espera simples de 60s e reavalia
    return 60.0
