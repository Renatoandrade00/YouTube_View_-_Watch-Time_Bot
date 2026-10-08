from __future__ import annotations

import asyncio
import logging
import random
from playwright.async_api import Page

logger = logging.getLogger("bot")


async def simulate_human_micro_interactions(page: Page, worker_id: int) -> None:
    """
    Simula pequenos comportamentos humanos orgânicos (movimento de mouse,
    hover sobre o player ou rolagem suave de página) para quebrar o padrão estático.
    """
    try:
        action_type = random.choice(["mouse_move", "hover_player", "scroll_sutle", "idle"])

        if action_type == "mouse_move":
            # Movimento aleatório com passos graduais simulando trajeto de cursor
            viewport = page.viewport_size or {"width": 1280, "height": 720}
            target_x = random.randint(150, max(200, viewport["width"] - 150))
            target_y = random.randint(150, max(200, viewport["height"] - 150))
            steps = random.randint(5, 12)
            await page.mouse.move(target_x, target_y, steps=steps)

        elif action_type == "hover_player":
            # Passa o mouse sobre o player do vídeo (faz aparecer a barra de controles temporariamente)
            player = page.locator(".html5-video-player").first
            if await player.is_visible(timeout=300):
                box = await player.bounding_box()
                if box:
                    center_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                    center_y = box["y"] + box["height"] * random.uniform(0.4, 0.8)
                    await page.mouse.move(center_x, center_y, steps=8)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    # Retira o mouse da área central suavemente
                    await page.mouse.move(center_x + 50, center_y + 100, steps=5)

        elif action_type == "scroll_sutle":
            # Rola levemente para baixo (simula leitura de descrição/comentários) e volta
            scroll_delta = random.randint(150, 350)
            await page.mouse.wheel(0, scroll_delta)
            await asyncio.sleep(random.uniform(1.5, 3.5))
            # Rola de volta para o topo do player
            await page.mouse.wheel(0, -scroll_delta)

        elif action_type == "idle":
            # Permanece assistindo sem interações (comportamento de espectador passivo)
            pass

    except Exception as e:
        logger.debug(f"[Worker {worker_id}] Exceção sutil na micro-interação: {e}")
