import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.config import BotConfig
from src.orchestrator import BotOrchestrator
from src.utils.logger import MetricsTracker
from src.web.state import StateManager


@pytest.mark.asyncio
async def test_round_duration_monitor_triggers_stop():
    """Testa se o monitor da rodada chama stop() automaticamente quando o tempo limite expira."""
    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=1,
        max_runtime_hours=0.0001,  # Fração pequena para teste
        continuous=True,
    )
    tracker = MetricsTracker()
    orchestrator = BotOrchestrator(config=config, tracker=tracker)

    # Executa monitor com timeout de 0.05 segundos
    monitor_task = asyncio.create_task(orchestrator._round_duration_monitor(0.05))
    await asyncio.sleep(0.1)

    assert orchestrator.stop_event.is_set(), "O stop_event deveria ter sido acionado pelo monitor de timeout"
    if not monitor_task.done():
        monitor_task.cancel()


@pytest.mark.asyncio
async def test_state_manager_finish_run():
    """Testa se finish_run encerra workers, define is_running como False e preserva timestamps."""
    sm = StateManager.get_instance()
    sm.init_workers(3)
    sm.is_running = True
    sm.update_worker(1, status="Assistindo", current_watch_time=30.0, target_watch_time=60.0)
    sm.update_worker(2, status="Reiniciando Vídeo", current_watch_time=0.0, target_watch_time=60.0)

    sm.finish_run("Duração Total da Rodada concluída.")

    assert sm.is_running is False
    assert sm.finish_timestamp is not None
    assert sm.workers[1].status == "Finalizado"
    assert sm.workers[2].status == "Finalizado"
    assert sm.workers[3].status == "Finalizado"

    state = sm.get_full_state()
    assert state["is_running"] is False
    assert len(state["workers"]) == 3
    for w in state["workers"]:
        assert w["status"] == "Finalizado"


@pytest.mark.asyncio
async def test_worker_continuous_loop_repeats_video_and_stops_on_timeout():
    """Testa se o loop do worker reinicia o vídeo após cada sessão até o timeout da rodada."""
    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=1,
        min_watch=10,
        max_watch=10,
        min_delay_between_videos=1.0,
        max_delay_between_videos=1.0,
        max_runtime_hours=0.001,
        continuous=True,
    )
    tracker = MetricsTracker()
    orchestrator = BotOrchestrator(config=config, tracker=tracker)

    sessions_called = 0

    async def mock_execute_single_session(worker_id, url, session_id):
        nonlocal sessions_called
        sessions_called += 1
        # Simula tempo de exibição
        await asyncio.sleep(0.02)
        if sessions_called >= 2:
            orchestrator.stop()

    import time
    with patch("src.orchestrator.random.uniform", return_value=0.01), \
         patch.object(orchestrator, "_execute_single_session", side_effect=mock_execute_single_session):
        task = asyncio.create_task(
            orchestrator._worker_continuous_loop(
                worker_id=1,
                urls=config.urls_list,
                max_runtime_seconds=5.0,
                global_start=time.time()
            )
        )
        await asyncio.wait_for(task, timeout=2.0)

    # Verifica se o vídeo foi reiniciado (executou pelo menos 2 sessões antes de parar)
    assert sessions_called >= 2, f"O vídeo deveria ter sido reiniciado pelo menos 2 vezes, mas foi chamado {sessions_called} vezes"


@pytest.mark.asyncio
async def test_watch_video_stops_on_max_end_time():
    """Testa se watch_video encerra prontamente quando o max_end_time já expirou."""
    from src.youtube.player import watch_video

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value={"exists": True, "paused": False, "ended": False, "currentTime": 10.0, "duration": 100.0})

    config = BotConfig(
        urls_list=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        workers=1,
        min_watch=10,
        max_watch=10,
        poll_interval=1.0,
    )

    # max_end_time já no passado
    past_time = time.time() - 10.0
    stats = await watch_video(
        page=mock_page,
        url=config.urls_list[0],
        target_watch_seconds=60,
        config=config,
        worker_id=1,
        max_end_time=past_time
    )

    assert stats["error_message"] == "Duração Total da Rodada atingida"

