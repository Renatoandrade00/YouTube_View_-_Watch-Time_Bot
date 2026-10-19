from datetime import datetime
from src.config import BotConfig
from src.utils.scheduler import is_within_active_window


def test_scheduler_no_window():
    cfg = BotConfig(target_url="https://www.youtube.com/watch?v=x")
    assert is_within_active_window(cfg) is True


def test_scheduler_hour_window():
    cfg = BotConfig(target_url="https://www.youtube.com/watch?v=x", active_hours_start=8, active_hours_end=18)
    assert is_within_active_window(cfg, datetime(2026, 1, 1, 10, 0)) is True
    assert is_within_active_window(cfg, datetime(2026, 1, 1, 20, 0)) is False


def test_scheduler_wrap_midnight():
    cfg = BotConfig(target_url="https://www.youtube.com/watch?v=x", active_hours_start=22, active_hours_end=6)
    assert is_within_active_window(cfg, datetime(2026, 1, 1, 23, 0)) is True
    assert is_within_active_window(cfg, datetime(2026, 1, 1, 3, 0)) is True
    assert is_within_active_window(cfg, datetime(2026, 1, 1, 12, 0)) is False
