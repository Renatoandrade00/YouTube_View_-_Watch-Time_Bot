from __future__ import annotations

import logging
from typing import List
from playwright.async_api import Page

logger = logging.getLogger("bot")

SKIP_AD_SELECTORS: List[str] = [
    ".ytp-ad-skip-button",
    ".ytp-skip-ad-button",
    ".ytp-ad-skip-button-modern",
    "button.ytp-ad-skip-button-modern",
    ".ytp-skip-ad-button-container button",
    "button.ytp-ad-skip-button-modern.ytp-button",
    ".videoAdUiSkipButton",
    ".ytp-ad-overlay-close-button",
    "button:has-text('Pular anúncio')",
    "button:has-text('Pular anúncios')",
    "button:has-text('Pular')",
    "button:has-text('Skip Ad')",
    "button:has-text('Skip Ads')",
    "button:has-text('Skip')",
]


async def try_skip_ad(page: Page) -> bool:
    """Tenta detectar anúncios ativos, acelera e clica em botões de pular anúncio."""
    skipped = False

    # 1. Se estiver mostrando anúncio no player, acelera 16x e busca o fim do ad
    try:
        await page.evaluate("""() => {
            const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
            const isAd = Boolean(
                document.querySelector('.ad-showing, .ad-interrupting, .ytp-ad-player-overlay') ||
                (player && player.classList && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting')))
            );
            const video = document.querySelector('video');
            if (isAd && video) {
                video.playbackRate = 16.0;
                if (video.duration && !isNaN(video.duration) && video.duration < 120) {
                    video.currentTime = video.duration;
                }
            } else if (!isAd && video && video.playbackRate > 2.0) {
                video.playbackRate = 1.0;
            }
        }""")
    except Exception:
        pass

    # 2. Tenta clicar no botão de pular se já estiver disponível no DOM
    for selector in SKIP_AD_SELECTORS:
        try:
            locator = page.locator(selector).first
            if await locator.is_visible(timeout=150):
                await locator.click(timeout=400, force=True)
                logger.info(f"⏩ Anúncio pulado com sucesso via seletor: [cyan]{selector}[/cyan]")
                skipped = True
                break
        except Exception:
            continue

    return skipped
