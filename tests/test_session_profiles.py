import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import BotConfig
from src.utils.helpers import parse_cookies_file
from src.browser.playwright_worker import PlaywrightWorker


def test_parse_cookies_json_array(tmp_path):
    cookie_file = tmp_path / "cookies.json"
    raw_cookies = [
        {
            "name": "LOGIN_INFO",
            "value": "token123",
            "domain": ".youtube.com",
            "path": "/",
            "expires": 1800000000,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        },
        {
            "name": "PREF",
            "value": "f6=400",
            "domain": ".youtube.com",
            "path": "/",
        },
    ]
    cookie_file.write_text(json.dumps(raw_cookies), encoding="utf-8")

    parsed = parse_cookies_file(cookie_file)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "LOGIN_INFO"
    assert parsed[0]["value"] == "token123"
    assert parsed[0]["httpOnly"] is True
    assert parsed[1]["name"] == "PREF"


def test_parse_cookies_storage_state_format(tmp_path):
    cookie_file = tmp_path / "storage_state.json"
    storage_state = {
        "cookies": [
            {
                "name": "SID",
                "value": "sid_secret",
                "domain": ".google.com",
                "path": "/",
            }
        ],
        "origins": [],
    }
    cookie_file.write_text(json.dumps(storage_state), encoding="utf-8")

    parsed = parse_cookies_file(cookie_file)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "SID"
    assert parsed[0]["value"] == "sid_secret"


def test_parse_cookies_netscape_format(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    netscape_content = """# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
.youtube.com\tTRUE\t/\tTRUE\t1789234800\tLOGIN_INFO\tnetscape_val
#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1789234800\tHSID\thttp_only_val
"""
    cookie_file.write_text(netscape_content, encoding="utf-8")

    parsed = parse_cookies_file(cookie_file)
    assert len(parsed) == 2
    assert parsed[0]["name"] == "LOGIN_INFO"
    assert parsed[0]["value"] == "netscape_val"
    assert parsed[0]["httpOnly"] is False

    assert parsed[1]["name"] == "HSID"
    assert parsed[1]["value"] == "http_only_val"
    assert parsed[1]["httpOnly"] is True


def test_parse_cookies_worker_specific_fallback(tmp_path):
    # Cria pasta com worker_2.json
    worker_2_file = tmp_path / "worker_2.json"
    worker_2_file.write_text(
        json.dumps([{"name": "W2_COOKIE", "value": "val2", "domain": ".youtube.com"}]),
        encoding="utf-8",
    )

    base_cookie_file = tmp_path / "cookies.json"
    base_cookie_file.write_text(
        json.dumps([{"name": "BASE_COOKIE", "value": "val_base", "domain": ".youtube.com"}]),
        encoding="utf-8",
    )

    # Worker 2 deve carregar worker_2.json
    parsed_w2 = parse_cookies_file(base_cookie_file, worker_id=2)
    assert len(parsed_w2) == 1
    assert parsed_w2[0]["name"] == "W2_COOKIE"

    # Worker 1 deve usar o base_cookie_file
    parsed_w1 = parse_cookies_file(base_cookie_file, worker_id=1)
    assert len(parsed_w1) == 1
    assert parsed_w1[0]["name"] == "BASE_COOKIE"


def test_config_profiles_defaults_and_custom():
    cfg = BotConfig(
        use_persistent_profiles=True,
        profiles_dir="custom_profiles",
        cookies_file="my_cookies.json",
    )
    assert cfg.use_persistent_profiles is True
    assert cfg.profiles_dir == "custom_profiles"
    assert cfg.cookies_file == "my_cookies.json"


@pytest.mark.asyncio
async def test_playwright_worker_persistent_profile_save_and_load(tmp_path):
    profiles_dir = tmp_path / "test_profiles"
    config = BotConfig(
        use_persistent_profiles=True,
        profiles_dir=str(profiles_dir),
        min_watch=10,
        max_watch=15,
    )

    worker = PlaywrightWorker(worker_id=1, config=config)

    # Simula mock do navegador e contexto
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    worker._ensure_browser = AsyncMock(return_value=mock_browser)

    # Mock do watch_video
    with patch("src.browser.playwright_worker.watch_video", new_callable=AsyncMock) as mock_watch:
        mock_watch.return_value = {
            "status": "SUCCESS",
            "actual_watch_time": 10.0,
            "ads_skipped": 0,
            "continue_dialogs_clicked": 0,
        }

        stats = await worker.execute_session(
            url="https://www.youtube.com/watch?v=mock_video",
            session_id=1,
        )

        assert stats["status"] == "SUCCESS"

        # Verifica se new_context foi chamado
        mock_browser.new_context.assert_called_once()

        # Verifica se storage_state foi chamado no context para persistir
        mock_context.storage_state.assert_called_once()
        saved_path = mock_context.storage_state.call_args[1]["path"]
        assert f"worker_1" in saved_path
        assert "storage_state.json" in saved_path
