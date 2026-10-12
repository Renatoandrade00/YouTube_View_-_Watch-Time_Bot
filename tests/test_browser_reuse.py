import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.config import BotConfig
from src.browser.playwright_worker import PlaywrightWorker
from src.orchestrator import BotOrchestrator
from src.utils.logger import MetricsTracker


@pytest.mark.asyncio
async def test_playwright_worker_browser_reuse():
    """Testa se a instância do Chromium é mantida aberta e reutilizada entre sessões consecutivas."""
    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=1,
        min_watch=10,
        max_watch=15,
    )
    worker = PlaywrightWorker(worker_id=1, config=config)

    mock_browser = MagicMock()
    mock_browser.is_connected.return_value = True
    mock_browser.close = AsyncMock()

    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    mock_context.route = AsyncMock()
    mock_context.new_page = AsyncMock()
    mock_context.close = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_chromium = MagicMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_playwright = MagicMock()
    mock_playwright.chromium = mock_chromium
    mock_playwright.stop = AsyncMock()

    with patch("src.browser.playwright_worker.async_playwright") as mock_ap_func, \
         patch("src.browser.playwright_worker.watch_video", new_callable=AsyncMock) as mock_watch:

        mock_ap_instance = MagicMock()
        mock_ap_instance.start = AsyncMock(return_value=mock_playwright)
        mock_ap_func.return_value = mock_ap_instance

        mock_watch.return_value = {
            "session_id": 1,
            "status": "SUCCESS",
            "actual_watch_time": 10.0,
        }

        # Sessão 1: Deve inicializar o navegador
        stats1 = await worker.execute_session(
            url="https://www.youtube.com/watch?v=video1",
            session_id=1,
        )
        assert stats1["status"] == "SUCCESS"
        assert mock_chromium.launch.call_count == 1
        assert mock_browser.new_context.call_count == 1
        assert mock_context.close.call_count == 1
        assert mock_browser.close.call_count == 0  # Não deve fechar o navegador!

        # Sessão 2: Deve reutilizar o mesmo navegador sem chamar chromium.launch novamente
        stats2 = await worker.execute_session(
            url="https://www.youtube.com/watch?v=video2",
            session_id=2,
        )
        assert stats2["status"] == "SUCCESS"
        assert mock_chromium.launch.call_count == 1  # Permanece 1 (reutilizado!)
        assert mock_browser.new_context.call_count == 2
        assert mock_context.close.call_count == 2
        assert mock_browser.close.call_count == 0  # Continua aberto!

        # Fechamento explícito ao término do worker
        await worker.close()
        assert mock_browser.close.call_count == 1
        assert mock_playwright.stop.call_count == 1


@pytest.mark.asyncio
async def test_playwright_worker_proxy_change_recycles_browser():
    """Testa se a mudança de proxy fecha a instância antiga para recriação com novo IP."""
    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=1,
    )
    worker = PlaywrightWorker(worker_id=1, config=config, proxy_url="http://p1:8080")

    mock_browser = MagicMock()
    mock_browser.is_connected.return_value = True
    mock_browser.close = AsyncMock()
    worker._browser = mock_browser

    # Mesmo proxy -> não recicla
    await worker.update_proxy("http://p1:8080")
    assert mock_browser.close.call_count == 0
    assert worker._browser is mock_browser

    # Novo proxy -> fecha instância antiga
    await worker.update_proxy("http://p2:8080")
    assert mock_browser.close.call_count == 1
    assert worker._browser is None
    assert worker.proxy_url == "http://p2:8080"


def test_orchestrator_worker_caching():
    """Testa se o orquestrador cria e reutiliza a mesma instância de worker."""
    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=2,
    )
    tracker = MetricsTracker()
    orchestrator = BotOrchestrator(config=config, tracker=tracker)

    w1 = orchestrator.get_or_create_worker(1)
    w2 = orchestrator.get_or_create_worker(2)
    w1_again = orchestrator.get_or_create_worker(1)

    assert w1 is w1_again
    assert w1 is not w2
    assert w1.worker_id == 1
    assert w2.worker_id == 2
