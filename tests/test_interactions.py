import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.youtube.interactions import simulate_human_micro_interactions


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_idle():
    """Garante que a ação 'idle' não dispara movimentos no mouse."""
    mock_page = MagicMock()
    mock_page.viewport_size = {"width": 1280, "height": 720}
    mock_page.mouse = AsyncMock()

    with patch("random.choice", return_value="idle"):
        await simulate_human_micro_interactions(mock_page, worker_id=1)

    mock_page.mouse.move.assert_not_called()
    mock_page.mouse.wheel.assert_not_called()


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_mouse_move():
    """Garante que a ação 'mouse_move' move o mouse suavemente."""
    mock_page = MagicMock()
    mock_page.viewport_size = {"width": 1920, "height": 1080}
    mock_page.mouse = AsyncMock()

    with patch("random.choice", return_value="mouse_move"), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        await simulate_human_micro_interactions(mock_page, worker_id=1)

    assert mock_page.mouse.move.await_count >= 1


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_scroll_sutil():
    """Garante que 'scroll_sutil' desce e depois sobe de volta."""
    mock_page = MagicMock()
    mock_page.mouse = AsyncMock()

    with patch("random.choice", return_value="scroll_sutil"), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        await simulate_human_micro_interactions(mock_page, worker_id=2)

    assert mock_page.mouse.wheel.await_count == 2
    # Primeira chamada rola para baixo (>0), segunda chamada rola de volta (<0)
    first_call_y = mock_page.mouse.wheel.await_args_list[0][0][1]
    second_call_y = mock_page.mouse.wheel.await_args_list[1][0][1]
    assert first_call_y > 0
    assert second_call_y < 0
    assert first_call_y == -second_call_y


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_progress_bar_hover():
    """Garante que 'progress_bar_hover' localiza a barra e move sem clicar."""
    mock_page = MagicMock()
    mock_page.mouse = AsyncMock()
    mock_bar = AsyncMock()
    mock_bar.is_visible.return_value = True
    mock_bar.bounding_box.return_value = {"x": 100, "y": 600, "width": 800, "height": 10}

    mock_locator = MagicMock()
    mock_locator.first = mock_bar
    mock_page.locator.return_value = mock_locator

    with patch("random.choice", return_value="progress_bar_hover"), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        await simulate_human_micro_interactions(mock_page, worker_id=3)

    assert mock_page.mouse.move.await_count >= 2


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_scroll_comments():
    """Garante que 'scroll_comments' rola para a seção de comentários e volta."""
    mock_page = MagicMock()
    mock_page.mouse = AsyncMock()

    with patch("random.choice", return_value="scroll_comments"), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        await simulate_human_micro_interactions(mock_page, worker_id=4)

    assert mock_page.mouse.wheel.await_count == 2
    first_y = mock_page.mouse.wheel.await_args_list[0][0][1]
    second_y = mock_page.mouse.wheel.await_args_list[1][0][1]
    assert first_y > 500
    assert second_y == -first_y


@pytest.mark.asyncio
async def test_simulate_human_micro_interactions_handles_exceptions_gracefully():
    """Garante que qualquer erro em DOM ou mouse é absorvido sem quebrar o loop do worker."""
    mock_page = MagicMock()
    mock_page.mouse = AsyncMock()
    mock_page.mouse.move.side_effect = RuntimeError("DOM disconnected")

    with patch("random.choice", return_value="mouse_move"):
        # Não deve lançar exceção
        await simulate_human_micro_interactions(mock_page, worker_id=5)
