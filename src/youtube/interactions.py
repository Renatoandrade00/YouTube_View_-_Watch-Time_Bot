from __future__ import annotations

import asyncio
import logging
import random
from playwright.async_api import Page

logger = logging.getLogger("bot")


async def simulate_human_micro_interactions(page: Page, worker_id: int) -> None:
    """
    Simula comportamentos humanos orgânicos durante a reprodução do vídeo.

    Ações disponíveis (por peso de probabilidade):
      - idle             (25%): espectador passivo, sem movimento — o mais comum
      - mouse_move       (20%): movimento gradual de cursor para posição aleatória
      - hover_player     (20%): passa o mouse sobre o player (faz aparecer controles)
      - scroll_sutil     (15%): rola levemente para ler descrição e volta
      - progress_bar_hover (10%): passa o mouse sobre a barra de progresso (sem clicar)
      - scroll_comments  (10%): rola mais fundo para a seção de comentários e volta
    """
    try:
        # Pesos calibrados para manter lact saudável (<15s) e simular atenção humana realista
        actions = [
            "idle", "idle",                                           # 10%
            "mouse_move", "mouse_move", "mouse_move", "mouse_move",   # 25%
            "hover_player", "hover_player", "hover_player", "hover_player",  # 25%
            "scroll_sutil", "scroll_sutil", "scroll_sutil",           # 15%
            "progress_bar_hover", "progress_bar_hover",               # 10%
            "scroll_comments", "scroll_comments", "scroll_comments",  # 15%
        ]
        action_type = random.choice(actions)

        if action_type == "mouse_move":
            # Movimento aleatório com passos graduais simulando trajeto humano de cursor
            viewport = page.viewport_size or {"width": 1280, "height": 720}
            target_x = random.randint(150, max(200, viewport["width"] - 150))
            target_y = random.randint(150, max(200, viewport["height"] - 150))
            steps = random.randint(6, 16)
            await page.mouse.move(target_x, target_y, steps=steps)
            # Micro-pausa natural após chegar ao destino
            await asyncio.sleep(random.uniform(0.1, 0.5))

        elif action_type == "hover_player":
            # Passa o mouse sobre o player (faz aparecer a barra de controles)
            player = page.locator(".html5-video-player").first
            if await player.is_visible(timeout=300):
                box = await player.bounding_box()
                if box:
                    center_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
                    center_y = box["y"] + box["height"] * random.uniform(0.35, 0.80)
                    await page.mouse.move(center_x, center_y, steps=random.randint(6, 12))
                    await asyncio.sleep(random.uniform(0.6, 2.2))
                    # Retira o mouse suavemente para fora da área central
                    offset_x = random.randint(-120, 120)
                    offset_y = random.randint(60, 150)
                    await page.mouse.move(center_x + offset_x, center_y + offset_y, steps=random.randint(4, 8))

        elif action_type == "scroll_sutil":
            # Rola levemente para baixo (simula leitura de descrição do vídeo) e retorna
            scroll_delta = random.randint(120, 420)
            await page.mouse.wheel(0, scroll_delta)
            await asyncio.sleep(random.uniform(1.8, 4.5))
            # Rola de volta ao topo do player suavemente
            await page.mouse.wheel(0, -scroll_delta)

        elif action_type == "progress_bar_hover":
            # Passa o mouse sobre a barra de progresso do vídeo sem clicar
            # (comportamento comum de usuário verificando duração restante)
            try:
                bar = page.locator(".ytp-progress-bar").first
                if await bar.is_visible(timeout=400):
                    box = await bar.bounding_box()
                    if box:
                        hover_x = box["x"] + box["width"] * random.uniform(0.1, 0.9)
                        hover_y = box["y"] + box["height"] * 0.5
                        await page.mouse.move(hover_x, hover_y, steps=random.randint(8, 14))
                        await asyncio.sleep(random.uniform(0.4, 1.2))
                        # Retira o mouse sem clicar — não altera o currentTime
                        await page.mouse.move(hover_x, hover_y - random.randint(40, 80), steps=6)
            except Exception:
                pass

        elif action_type == "scroll_comments":
            # Rola mais abaixo para a área de comentários (comportamento orgânico frequente)
            # e retorna ao player após alguns segundos
            down_delta = random.randint(550, 1300)
            await page.mouse.wheel(0, down_delta)
            await asyncio.sleep(random.uniform(3.0, 7.5))
            # Retorna ao player gradualmente
            await page.mouse.wheel(0, -down_delta)
            await asyncio.sleep(random.uniform(0.5, 1.0))

        # idle: não faz nada — espectador passivo assistindo normalmente

    except Exception as e:
        logger.debug(f"[Worker {worker_id}] Exceção sutil na micro-interação: {e}")
