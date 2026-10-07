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
