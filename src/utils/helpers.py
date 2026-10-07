from __future__ import annotations

import asyncio
import random
from typing import Tuple

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
]


def get_random_user_agent() -> str:
    """Retorna um User-Agent moderno aleatório."""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    """Retorna uma resolução comum de viewport aleatória."""
    return random.choice(VIEWPORTS)


async def random_async_sleep(min_seconds: float, max_seconds: float) -> float:
    """Aguarda um intervalo de tempo aleatório de forma assíncrona."""
    if min_seconds > max_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
    return delay


def normalize_youtube_url(url: str) -> str:
    """Normaliza links curtos ou variações de URLs do YouTube."""
    url = url.strip()
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
    return url
