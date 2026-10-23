from __future__ import annotations

import asyncio
import logging
import random
from playwright.async_api import Page

logger = logging.getLogger("bot")

BEHAVIOR_PROFILES = {
    "casual": {
        "idle": 0.40,
        "mouse_move": 0.15,
        "hover_player": 0.15,
        "scroll_sutil": 0.15,
        "progress_bar_hover": 0.08,
        "scroll_comments": 0.07,
    },
    "engaged": {
        "idle": 0.20,
        "mouse_move": 0.20,
        "hover_player": 0.25,
        "scroll_sutil": 0.15,
        "progress_bar_hover": 0.10,
        "scroll_comments": 0.10,
    },
    "skimmer": {
        "idle": 0.15,
        "mouse_move": 0.25,
        "hover_player": 0.10,
        "scroll_sutil": 0.20,
        "progress_bar_hover": 0.15,
        "scroll_comments": 0.15,
    },
}


def _expand_profile(profile_name: str) -> list[str]:
    weights = BEHAVIOR_PROFILES.get(profile_name, BEHAVIOR_PROFILES["casual"])
    expanded: list[str] = []
    for action, weight in weights.items():
        expanded.extend([action] * max(1, int(weight * 100)))
    return expanded


def _choose_action(profile_name: str) -> str:
    return random.choice(_expand_profile(profile_name))


async def simulate_human_micro_interactions(
    page: Page,
    worker_id: int,
    behavior_profile: str = "mixed",
) -> None:
    if behavior_profile == "mixed":
        behavior_profile = random.Random().choice(["casual", "engaged", "skimmer"])

    try:
        action_type = _choose_action(behavior_profile)

        if action_type == "idle":
            await asyncio.sleep(random.uniform(0.5, 2.0))
            return

        if action_type == "mouse_move":
            viewport = page.viewport_size or {"width": 1280, "height": 720}
            target_x = random.randint(150, max(200, viewport["width"] - 150))
            target_y = random.randint(150, max(200, viewport["height"] - 150))
            steps = random.randint(6, 16)
            await page.mouse.move(target_x, target_y, steps=steps)
            await asyncio.sleep(random.uniform(0.1, 0.5))

        elif action_type == "hover_player":
            player = page.locator(".html5-video-player").first
            if await player.is_visible(timeout=300):
                box = await player.bounding_box()
                if box:
                    center_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
                    center_y = box["y"] + box["height"] * random.uniform(0.35, 0.80)
                    await page.mouse.move(center_x, center_y, steps=random.randint(6, 12))
                    await asyncio.sleep(random.uniform(0.6, 2.2))
                    offset_x = random.randint(-120, 120)
                    offset_y = random.randint(60, 150)
                    await page.mouse.move(center_x + offset_x, center_y + offset_y, steps=random.randint(4, 8))

        elif action_type == "scroll_sutil":
            scroll_delta = random.randint(120, 420)
            await page.mouse.wheel(0, scroll_delta)
            await asyncio.sleep(random.uniform(1.8, 4.5))
            await page.mouse.wheel(0, -scroll_delta)

        elif action_type == "progress_bar_hover":
            try:
                bar = page.locator(".ytp-progress-bar").first
                if await bar.is_visible(timeout=400):
                    box = await bar.bounding_box()
                    if box:
                        hover_x = box["x"] + box["width"] * random.uniform(0.1, 0.9)
                        hover_y = box["y"] + box["height"] * 0.5
                        await page.mouse.move(hover_x, hover_y, steps=random.randint(8, 14))
                        await asyncio.sleep(random.uniform(0.4, 1.2))
                        await page.mouse.move(hover_x, hover_y - random.randint(40, 80), steps=6)
            except Exception:
                pass

        elif action_type == "scroll_comments":
            down_delta = random.randint(550, 1300)
            await page.mouse.wheel(0, down_delta)
            await asyncio.sleep(random.uniform(3.0, 7.5))
            await page.mouse.wheel(0, -down_delta)
            await asyncio.sleep(random.uniform(0.5, 1.0))


    except Exception as e:
        logger.debug(f"[Worker {worker_id}] Excecao sutil na micro-interacao: {e}")
