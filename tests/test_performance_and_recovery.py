import pytest
from unittest.mock import AsyncMock, MagicMock
from src.config import BotConfig, load_config
from src.web.app import StartBotRequest


def test_config_block_heavy_media_defaults():
    config = BotConfig(target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert config.block_heavy_media is True
    assert config.auto_player_recovery is True


def test_config_block_heavy_media_custom():
    config = BotConfig(
        target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        block_heavy_media=False,
        auto_player_recovery=False,
    )
    assert config.block_heavy_media is False
    assert config.auto_player_recovery is False


def test_cli_overrides_recovery_and_media():
    overrides = {
        "target_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "block_heavy_media": False,
        "auto_player_recovery": False,
    }
    cfg = load_config(cli_overrides=overrides)
    assert cfg.block_heavy_media is False
    assert cfg.auto_player_recovery is False


def test_start_bot_request_model():
    req = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        block_heavy_media=False,
        auto_player_recovery=False,
    )
    assert req.block_heavy_media is False
    assert req.auto_player_recovery is False

    req_default = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    assert req_default.block_heavy_media is True
    assert req_default.auto_player_recovery is True

    # Suporte a até 50 workers
    req_50 = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=50,
    )
    assert req_50.workers == 50

    # Rejeição acima de 50 workers
    with pytest.raises(Exception):
        StartBotRequest(
            urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            workers=51,
        )


@pytest.mark.asyncio
async def test_low_bandwidth_route_filter_logic():
    """Valida a lógica de filtragem de rotas bloqueando imagens, fontes e domínios pesados."""
    blocked_domains = [
        "doubleclick.net",
        "googleads",
        "googleadservices.com",
        "googlesyndication.com",
        "adservice.google.com",
        "yt3.ggpht.com",
        "i.ytimg.com",
        "play.google.com/log",
    ]

    async def filter_route(url: str, resource_type: str):
        url_lower = url.lower()
        aborted = False
        if any(d in url_lower for d in blocked_domains) and "videoplayback" not in url_lower:
            aborted = True
        elif resource_type in ["image", "font", "media"] and "videoplayback" not in url_lower:
            aborted = True
        return aborted

    # Testes com URLs bloqueadas
    assert await filter_route("https://i.ytimg.com/vi/123/hqdefault.jpg", "image") is True
    assert await filter_route("https://yt3.ggpht.com/avatar.jpg", "image") is True
    assert await filter_route("https://googleads.g.doubleclick.net/pagead/id", "script") is True
    assert await filter_route("https://fonts.gstatic.com/s/roboto.woff2", "font") is True

    # Testes com stream de vídeo permitido
    assert await filter_route("https://rr1---sn-abc.googlevideo.com/videoplayback?id=123", "media") is False
    # Teste com script essencial do player permitido
    assert await filter_route("https://www.youtube.com/s/desktop/123/base.js", "script") is False
