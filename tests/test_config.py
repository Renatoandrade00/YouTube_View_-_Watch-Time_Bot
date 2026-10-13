import pytest
from pydantic import ValidationError
from src.config import BotConfig, load_config


def test_bot_config_defaults():
    config = BotConfig(target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert config.workers == 2
    assert config.min_watch == 45
    assert config.max_watch == 120
    assert config.headless is False
    assert config.mute_audio is True


def test_bot_config_invalid_range():
    with pytest.raises(ValidationError):
        BotConfig(min_watch=100, max_watch=50)


def test_url_resolution_single():
    config = BotConfig(target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    urls = config.resolve_urls()
    assert len(urls) == 1
    assert urls[0] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_url_resolution_from_file(tmp_path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://www.youtube.com/watch?v=video1\n# comentário\nhttps://www.youtube.com/watch?v=video2\n\n",
        encoding="utf-8"
    )
    config = BotConfig(urls_file=str(url_file))
    urls = config.resolve_urls()
    assert len(urls) == 2
    assert urls[0] == "https://www.youtube.com/watch?v=video1"
    assert urls[1] == "https://www.youtube.com/watch?v=video2"


def test_load_config_cli_overrides():
    overrides = {
        "target_url": "https://www.youtube.com/watch?v=override",
        "workers": 5,
        "min_watch": 30,
        "max_watch": 60,
        "headless": True
    }
    cfg = load_config(cli_overrides=overrides)
    assert cfg.target_url == "https://www.youtube.com/watch?v=override"
    assert cfg.workers == 5
    assert cfg.min_watch == 30
    assert cfg.max_watch == 60
    assert cfg.headless is True


def test_proxy_resolution_and_distribution(tmp_path):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text(
        "http://proxy1:8000\n# comment\nhttp://proxy2:8000\n\n",
        encoding="utf-8"
    )
    cfg = BotConfig(
        enable_proxy=True,
        proxies_file=str(proxy_file),
    )
    resolved = cfg.resolve_proxies()
    assert len(resolved) == 2
    assert resolved[0] == "http://proxy1:8000"
    assert resolved[1] == "http://proxy2:8000"

    # Worker 1 -> Proxy 1
    assert cfg.get_proxy_for_worker(1) == "http://proxy1:8000"
    # Worker 2 -> Proxy 2
    assert cfg.get_proxy_for_worker(2) == "http://proxy2:8000"
    # Worker 3 -> Round-robin para Proxy 1
    assert cfg.get_proxy_for_worker(3) == "http://proxy1:8000"


def test_proxy_session_template():
    cfg = BotConfig(
        enable_proxy=True,
        proxy_session_template="http://user-session-{worker_id}:pass@gateway.com:7000"
    )
    assert cfg.get_proxy_for_worker(1) == "http://user-session-1:pass@gateway.com:7000"
    assert cfg.get_proxy_for_worker(5) == "http://user-session-5:pass@gateway.com:7000"


def test_load_config_yaml_full(tmp_path):
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(
        """
target:
  url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
stealth:
  search_and_play: true
performance:
  block_heavy_media: false
  auto_player_recovery: false
profiles:
  use_persistent_profiles: true
  profiles_dir: "custom_profiles"
  cookies_file: "my_cookies.json"
""",
        encoding="utf-8"
    )
    cfg = load_config(yaml_path=str(yaml_file))
    assert cfg.search_and_play is True
    assert cfg.block_heavy_media is False
    assert cfg.auto_player_recovery is False
    assert cfg.use_persistent_profiles is True
    assert cfg.profiles_dir == "custom_profiles"
    assert cfg.cookies_file == "my_cookies.json"


def test_load_config_env_vars(monkeypatch):
    monkeypatch.setenv("SEARCH_AND_PLAY", "true")
    monkeypatch.setenv("BLOCK_HEAVY_MEDIA", "false")
    monkeypatch.setenv("AUTO_PLAYER_RECOVERY", "false")
    monkeypatch.setenv("USE_PERSISTENT_PROFILES", "true")
    monkeypatch.setenv("PROFILES_DIR", "env_profiles")
    monkeypatch.setenv("COOKIES_FILE", "env_cookies.json")

    cfg = load_config()
    assert cfg.search_and_play is True
    assert cfg.block_heavy_media is False
    assert cfg.auto_player_recovery is False
    assert cfg.use_persistent_profiles is True
    assert cfg.profiles_dir == "env_profiles"
    assert cfg.cookies_file == "env_cookies.json"


