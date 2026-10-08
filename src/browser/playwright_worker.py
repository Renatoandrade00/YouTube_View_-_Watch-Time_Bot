from __future__ import annotations

import asyncio
import logging
import random
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext

from src.browser.fingerprint import generate_fingerprint_profile, build_stealth_injection_script
from src.config import BotConfig
from src.utils.helpers import get_random_user_agent, get_random_viewport, normalize_youtube_url
from src.youtube.player import watch_video

logger = logging.getLogger("bot")


class PlaywrightWorker:
    """Gerencia o ciclo de vida de uma sessão isolada de navegador no Playwright."""

    def __init__(self, worker_id: int, config: BotConfig):
        self.worker_id = worker_id
        self.config = config

    async def execute_session(
        self,
        url: str,
        session_id: int,
        stop_event: Optional[asyncio.Event] = None,
        max_end_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Abre uma nova instância de navegador, executa a visualização e fecha todos os recursos."""
        normalized_url = normalize_youtube_url(url)
        target_watch_time = random.randint(self.config.min_watch, self.config.max_watch)

        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--autoplay-policy=no-user-gesture-required",
        ]
        if self.config.mute_audio:
            browser_args.append("--mute-audio")

        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=self.config.headless,
                args=browser_args,
            )

            context: BrowserContext = await browser.new_context(
                user_agent=get_random_user_agent(),
                viewport=get_random_viewport(),
                locale="pt-BR",
            )

            # Injeção de perfil anti-fingerprint (Canvas, WebGL, AudioContext, Hardware)
            gpu_desc = "Padrão do Sistema"
            if self.config.enable_anti_fingerprint:
                profile = generate_fingerprint_profile(self.worker_id)
                gpu_desc = profile.gpu_vendor
                stealth_script = build_stealth_injection_script(profile)
                await context.add_init_script(stealth_script)
                logger.info(
                    f"[Worker {self.worker_id}] 🛡️ Perfil Anti-Fingerprint ativado "
                    f"(GPU: {profile.gpu_vendor}, Cores: {profile.hardware_concurrency}, RAM: {profile.device_memory}GB)"
                )

            try:
                from src.web.state import StateManager
                sm = StateManager.get_instance()
                if sm.is_running:
                    sm.update_worker(
                        worker_id=self.worker_id,
                        status="Navegando",
                        current_url=normalized_url,
                        current_watch_time=0.0,
                        target_watch_time=target_watch_time,
                        gpu_info=gpu_desc
                    )
            except Exception:
                pass

            page = await context.new_page()

            try:
                stats = await watch_video(
                    page=page,
                    url=normalized_url,
                    target_watch_seconds=target_watch_time,
                    config=self.config,
                    worker_id=self.worker_id,
                    stop_event=stop_event,
                    max_end_time=max_end_time,
                )
                stats["target_watch_time"] = target_watch_time
                stats["url"] = normalized_url
                stats["session_id"] = session_id
                stats["worker_id"] = self.worker_id
                return stats
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Exceção não tratada na sessão {session_id}: {e}")
                return {
                    "session_id": session_id,
                    "worker_id": self.worker_id,
                    "url": normalized_url,
                    "target_watch_time": target_watch_time,
                    "actual_watch_time": 0.0,
                    "ads_skipped": 0,
                    "continue_dialogs_clicked": 0,
                    "status": "FAILED",
                    "error_message": str(e),
                }
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await context.close()
                except Exception:
                    pass
                try:
                    await browser.close()
                except Exception:
                    pass
