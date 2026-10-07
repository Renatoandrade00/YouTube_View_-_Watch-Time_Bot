from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.config import BotConfig
from src.youtube.ads import try_skip_ad
from src.youtube.continue_watching import handle_continue_watching_dialog
from src.utils.helpers import random_async_sleep

logger = logging.getLogger("bot")

CONSENT_BUTTON_SELECTORS = [
    "button:has-text('Aceitar tudo')",
    "button:has-text('Accept all')",
    "button:has-text('Concordo')",
    "button:has-text('I agree')",
    "ytd-consent-bump-v2-lightbox button",
    "form[action*='consent.youtube.com'] button",
    "button[aria-label*='Aceitar']",
    "button[aria-label*='Accept']",
]


async def handle_consent_popups(page: Page) -> bool:
    """Detecta e aceita banners de consentimento de cookies da Google/YouTube."""
    for selector in CONSENT_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=1000)
                logger.info("🍪 Consentimento de cookies aceito com sucesso.")
                await asyncio.sleep(1.0)
                return True
        except Exception:
            continue
    return False


async def ensure_video_playing(page: Page, mute_audio: bool = True) -> bool:
    """Garante que o elemento de vídeo HTML5 está em reprodução ativa."""
    try:
        # Primeiro tenta via injeção JS direta no elemento <video>
        result = await page.evaluate(f"""() => {{
            const video = document.querySelector('video');
            if (!video) return {{ found: false }};
            if ({str(mute_audio).lower()}) {{
                video.muted = true;
            }}
            if (video.paused) {{
                video.play().catch(() => {{}});
            }}
            return {{
                found: true,
                paused: video.paused,
                currentTime: video.currentTime,
                duration: video.duration
            }};
        }}""")

        if result.get("found"):
            # Se ainda estava pausado, tenta clicar no player diretamente
            if result.get("paused"):
                play_button = page.locator(".ytp-play-button").first
                if await play_button.is_visible(timeout=500):
                    await play_button.click(timeout=500, force=True)
            return True
    except Exception as e:
        logger.debug(f"Aviso ao verificar status do player: {e}")

    return False


async def watch_video(
    page: Page,
    url: str,
    target_watch_seconds: int,
    config: BotConfig,
    worker_id: int
) -> Dict[str, Any]:
    """
    Navega até a URL do YouTube e monitora a reprodução até o tempo limite desejado.
    Retorna estatísticas detalhadas da sessão.
    """
    stats = {
        "actual_watch_time": 0.0,
        "ads_skipped": 0,
        "continue_dialogs_clicked": 0,
        "status": "FAILED",
        "error_message": None,
    }

    logger.info(f"[Worker {worker_id}] 🎬 Navegando para: {url} (Meta: {target_watch_seconds}s)")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except PlaywrightTimeoutError:
        stats["error_message"] = "Timeout de carregamento da página"
        logger.warning(f"[Worker {worker_id}] ⚠️ Timeout ao carregar a página inicial.")
        return stats
    except Exception as e:
        stats["error_message"] = str(e)
        logger.error(f"[Worker {worker_id}] ❌ Erro ao navegar para o vídeo: {e}")
        return stats

    # Lida com consentimento de cookies se aparecer
    await handle_consent_popups(page)
    await random_async_sleep(1.0, 2.5)

    # Inicia e confere o player
    await ensure_video_playing(page, mute_audio=config.mute_audio)

    start_time = time.time()
    last_active_time = start_time
    accumulated_watch_time = 0.0
    last_video_current_time = 0.0

    while accumulated_watch_time < target_watch_seconds:
        current_now = time.time()
        elapsed_loop = current_now - last_active_time
        last_active_time = current_now

        # 1. Pular anúncios se configurado
        if config.skip_ads:
            if await try_skip_ad(page):
                stats["ads_skipped"] += 1

        # 2. Clicar no popup de 'Continuar assistindo' se configurado
        if config.auto_continue:
            if await handle_continue_watching_dialog(page):
                stats["continue_dialogs_clicked"] += 1
                await ensure_video_playing(page, mute_audio=config.mute_audio)

        # 3. Inspecionar estado do vídeo no DOM
        try:
            video_state = await page.evaluate("""() => {
                const video = document.querySelector('video');
                if (!video) return { exists: false };
                return {
                    exists: true,
                    paused: video.paused,
                    ended: video.ended,
                    currentTime: video.currentTime,
                    duration: video.duration
                };
            }""")

            if video_state.get("exists"):
                if video_state.get("ended"):
                    logger.info(f"[Worker {worker_id}] 🏁 Vídeo finalizou antes da meta. Encerrando sessão.")
                    accumulated_watch_time += elapsed_loop
                    break

                if video_state.get("paused"):
                    # Se pausado, tenta retomar
                    await ensure_video_playing(page, mute_audio=config.mute_audio)
                else:
                    # Vídeo tocando ativamente
                    accumulated_watch_time += elapsed_loop
                    last_video_current_time = video_state.get("currentTime", 0.0)
            else:
                # Se não encontrou o vídeo ainda, aguarda
                pass

        except Exception as e:
            logger.debug(f"[Worker {worker_id}] Exceção na verificação periódica: {e}")

        stats["actual_watch_time"] = round(accumulated_watch_time, 1)

        # Log de progresso periódico a cada ~60 segundos
        if int(accumulated_watch_time) > 0 and int(accumulated_watch_time) % 60 < sleep_duration:
            logger.info(
                f"[Worker {worker_id}] ⏱️ Progresso: {accumulated_watch_time:.0f}s / {target_watch_seconds}s "
                f"({accumulated_watch_time / 60:.1f} / {target_watch_seconds / 60:.1f} min)"
            )

        # Intervalo do polling com pequeno jitter para simular comportamento natural
        sleep_duration = max(1.0, config.poll_interval)
        await asyncio.sleep(sleep_duration)

    stats["actual_watch_time"] = round(accumulated_watch_time, 1)
    stats["status"] = "SUCCESS" if accumulated_watch_time >= 25.0 else "FAILED"
    logger.info(f"[Worker {worker_id}] ✅ Sessão concluída! Assistido: {stats['actual_watch_time']}s / Meta: {target_watch_seconds}s")
    return stats
