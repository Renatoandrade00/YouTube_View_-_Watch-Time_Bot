from __future__ import annotations

import logging
from typing import List
from playwright.async_api import Page

logger = logging.getLogger("bot")

CONTINUE_WATCHING_SELECTORS: List[str] = [
    "yt-confirm-dialog-renderer #confirm-button button",
    "yt-confirm-dialog-renderer #confirm-button",
    "tp-yt-paper-dialog #confirm-button button",
    "tp-yt-paper-dialog #confirm-button",
    "ytd-popup-container yt-button-renderer#confirm-button",
    "button:has-text('Continuar assistindo')",
    "button:has-text('Continue watching')",
    "button:has-text('Sim')",
    "button:has-text('Yes')",
]


async def handle_continue_watching_dialog(page: Page) -> bool:
    """Detecta se o diálogo de inatividade do YouTube surgiu e clica no botão para prosseguir."""
    for selector in CONTINUE_WATCHING_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=250):
                await btn.click(timeout=800, force=True)
                logger.info(f"🔄 Diálogo 'Continuar assistindo' detectado e clicado ([cyan]{selector}[/cyan])")
                return True
        except Exception:
            continue

    # Fallback via DOM evaluation para diálogos que podem estar ocultos ou presos no overlay
    try:
        clicked = await page.evaluate("""() => {
            const confirmBtn = document.querySelector('yt-confirm-dialog-renderer #confirm-button') ||
                               document.querySelector('tp-yt-paper-dialog #confirm-button');
            if (confirmBtn && confirmBtn.offsetParent !== null) {
                confirmBtn.click();
                return true;
            }
            return false;
        }""")
        if clicked:
            logger.info("🔄 Diálogo 'Continuar assistindo' acionado com sucesso via Fallback JS.")
            return True
    except Exception:
        pass

    return False
