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
    ".videoAdUiSkipButton",
    "button:has-text('Pular anúncio')",
    "button:has-text('Pular anúncios')",
    "button:has-text('Pular')",
    "button:has-text('Skip Ad')",
    "button:has-text('Skip Ads')",
    "button:has-text('Skip')",
]


async def try_skip_ad(page: Page) -> bool:
    """Tenta detectar e clicar em botões de pular anúncio se estiverem visíveis e clicáveis."""
    for selector in SKIP_AD_SELECTORS:
        try:
            locator = page.locator(selector).first
            if await locator.is_visible(timeout=200):
                await locator.click(timeout=500, force=True)
                logger.info(f"⏩ Anúncio pulado com sucesso via seletor: [cyan]{selector}[/cyan]")
                return True
        except Exception:
            continue
    return False
