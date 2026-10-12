import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.config import BotConfig, load_config
from src.web.app import StartBotRequest
from src.youtube.search_flow import parse_url_and_keyword, get_video_title, perform_search_and_play


def test_parse_url_and_keyword():
    # URL simples
    u1, k1 = parse_url_and_keyword("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert u1 == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert k1 is None

    # Formato com pipe
    u2, k2 = parse_url_and_keyword("https://www.youtube.com/watch?v=dQw4w9WgXcQ | Rick Astley Never Gonna Give You Up")
    assert u2 == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert k2 == "Rick Astley Never Gonna Give You Up"

    # Formato com ponto e vírgula
    u3, k3 = parse_url_and_keyword("https://www.youtube.com/watch?v=dQw4w9WgXcQ;Rick Astley")
    assert u3 == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert k3 == "Rick Astley"

    u4, k4 = parse_url_and_keyword("Rick Astley;https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert u4 == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert k4 == "Rick Astley"


def test_bot_config_resolve_urls_with_keywords(tmp_path):
    url_file = tmp_path / "urls_with_kw.txt"
    url_file.write_text(
        "https://www.youtube.com/watch?v=vid1 | termo de busca 1\n"
        "https://www.youtube.com/watch?v=vid2\n"
        "# comentario\n"
        "termo 3;https://www.youtube.com/watch?v=vid3\n",
        encoding="utf-8"
    )

    config = BotConfig(urls_file=str(url_file), search_and_play=True)
    urls = config.resolve_urls()

    assert len(urls) == 3
    assert urls[0] == "https://www.youtube.com/watch?v=vid1"
    assert urls[1] == "https://www.youtube.com/watch?v=vid2"
    assert urls[2] == "https://www.youtube.com/watch?v=vid3"

    assert config.custom_keywords.get("https://www.youtube.com/watch?v=vid1") == "termo de busca 1"
    assert config.custom_keywords.get("https://www.youtube.com/watch?v=vid3") == "termo 3"
    assert "https://www.youtube.com/watch?v=vid2" not in config.custom_keywords


def test_start_bot_request_search_and_play():
    req = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ | Rick Astley"],
        search_and_play=True,
    )
    assert req.search_and_play is True

    req_default = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )
    assert req_default.search_and_play is False


def test_cli_overrides_search_and_play():
    overrides = {
        "target_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "search_and_play": True,
    }
    cfg = load_config(cli_overrides=overrides)
    assert cfg.search_and_play is True


@pytest.mark.asyncio
async def test_get_video_title_cached():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"title": "Título de Teste do Vídeo"}
        mock_get.return_value = mock_resp

        title = await get_video_title("https://www.youtube.com/watch?v=abcdefghijk")
        assert title == "Título de Teste do Vídeo"


@pytest.mark.asyncio
async def test_perform_search_and_play_found():
    page = MagicMock()
    page.goto = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.wheel = AsyncMock()

    # Simula busca encontrada
    mock_input = MagicMock()
    mock_input.is_visible = AsyncMock(return_value=True)
    mock_input.click = AsyncMock()
    mock_input.type = AsyncMock()
    mock_input.press = AsyncMock()

    mock_target_item = MagicMock()
    mock_target_item.is_visible = AsyncMock(return_value=True)
    mock_target_item.scroll_into_view_if_needed = AsyncMock()
    mock_target_item.click = AsyncMock()

    def locator_side_effect(selector):
        loc = MagicMock()
        if "input" in selector or "search" in selector:
            loc.first = mock_input
        else:
            loc.first = mock_target_item
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    success = await perform_search_and_play(
        page=page,
        target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        worker_id=1,
        custom_keyword="Rick Astley",
    )

    assert success is True
    assert page.goto.call_count >= 1
    mock_input.type.assert_called()
    mock_input.press.assert_called_with("Enter")
    mock_target_item.click.assert_called()


@pytest.mark.asyncio
async def test_perform_search_and_play_fallback_when_not_found():
    page = MagicMock()
    page.goto = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.wheel = AsyncMock()

    mock_input = MagicMock()
    mock_input.is_visible = AsyncMock(return_value=True)
    mock_input.click = AsyncMock()
    mock_input.type = AsyncMock()
    mock_input.press = AsyncMock()

    mock_not_found = MagicMock()
    mock_not_found.is_visible = AsyncMock(return_value=False)

    def locator_side_effect(selector):
        loc = MagicMock()
        if "input" in selector or "search" in selector:
            loc.first = mock_input
        else:
            loc.first = mock_not_found
        return loc

    page.locator = MagicMock(side_effect=locator_side_effect)

    success = await perform_search_and_play(
        page=page,
        target_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        worker_id=1,
        custom_keyword="Rick Astley",
    )

    # Não encontrou após os scrolls -> aciona fallback para page.goto
    assert success is False
    assert page.goto.call_count >= 2  # 1 para youtube.com e 1 para fallback url
