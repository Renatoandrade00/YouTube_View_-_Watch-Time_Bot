from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext

from src.browser.fingerprint import generate_fingerprint_profile, build_stealth_injection_script
from src.config import BotConfig
from src.utils.helpers import (
    format_proxy_display,
    get_random_user_agent,
    get_random_viewport,
    normalize_youtube_url,
    parse_playwright_proxy,
)
from src.youtube.player import watch_video

logger = logging.getLogger("bot")


class PlaywrightWorker:
    """Gerencia o ciclo de vida do Chromium reutilizando o processo do navegador entre sessões."""

    def __init__(self, worker_id: int, config: BotConfig, proxy_url: Optional[str] = None):
        self.worker_id = worker_id
        self.config = config
        self.proxy_url = proxy_url or self.config.get_proxy_for_worker(self.worker_id)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self) -> Browser:
        """
        Retorna a instância do Chromium ativa, reutilizando-a se já estiver aberta e conectada.
        Caso contrário, inicializa o driver Playwright e abre o Chromium.
        """
        async with self._lock:
            if self._browser is not None:
                try:
                    if self._browser.is_connected():
                        return self._browser
                except Exception:
                    pass
                # Se perdeu conexão ou encerrou, limpa recursos antes de reiniciar
                await self._cleanup_browser()

            if self._playwright is None:
                self._playwright = await async_playwright().start()

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
            # NOTA: --mute-audio NÃO é adicionado ao launch do Chromium.
            # O silenciamento é feito via JS (video.muted = true) para preservar
            # o pipeline de áudio do OS — o YouTube usa AudioContext como sinal
            # de engajamento real para contabilizar o watch time corretamente.

            proxy_dict = parse_playwright_proxy(self.proxy_url) if self.proxy_url else None
            proxy_desc = format_proxy_display(self.proxy_url) if self.proxy_url else "Conexão Direta (Local)"

            if proxy_dict:
                logger.info(f"[Worker {self.worker_id}] 🌐 Conectando Chromium via Proxy: [cyan]{proxy_desc}[/cyan]")

            launch_kwargs: Dict[str, Any] = {
                "headless": self.config.headless,
                "args": browser_args,
            }
            if proxy_dict:
                launch_kwargs["proxy"] = proxy_dict

            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
            logger.info(f"[Worker {self.worker_id}] ⚡ Instância Chromium iniciada e ativa para reuso.")
            return self._browser

    async def update_proxy(self, new_proxy_url: Optional[str]) -> None:
        """Atualiza o proxy do worker. Se o proxy mudou, reinicia a instância do navegador."""
        async with self._lock:
            if self.proxy_url == new_proxy_url:
                return
            self.proxy_url = new_proxy_url
            await self._cleanup_browser()

    async def _cleanup_browser(self) -> None:
        """Fecha com segurança a instância do navegador sem encerrar o driver Playwright."""
        if self._browser is not None:
            try:
                if self._browser.is_connected():
                    await self._browser.close()
            except Exception:
                pass
            self._browser = None

    async def close(self) -> None:
        """Encerra completamente o navegador e o driver Playwright deste worker."""
        async with self._lock:
            await self._cleanup_browser()
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            logger.debug(f"[Worker {self.worker_id}] Recursos finalizados.")

    async def execute_session(
        self,
        url: str,
        session_id: int,
        stop_event: Optional[asyncio.Event] = None,
        max_end_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executa uma sessão de visualização criando um BrowserContext leve e isolado,
        reaproveitando o mesmo processo Chromium já aberto.
        """
        normalized_url = normalize_youtube_url(url)
        target_watch_time = random.randint(self.config.min_watch, self.config.max_watch)

        browser = await self._ensure_browser()

        context_kwargs: Dict[str, Any] = {
            "user_agent": get_random_user_agent(),
            "viewport": get_random_viewport(),
            "locale": "pt-BR",
        }

        profile_state_path: Optional[Path] = None
        if getattr(self.config, "use_persistent_profiles", False):
            profiles_dir = Path(getattr(self.config, "profiles_dir", "profiles"))
            worker_profile_dir = profiles_dir / f"worker_{self.worker_id}"
            worker_profile_dir.mkdir(parents=True, exist_ok=True)
            profile_state_path = worker_profile_dir / "storage_state.json"
            if profile_state_path.exists() and profile_state_path.stat().st_size > 0:
                context_kwargs["storage_state"] = str(profile_state_path)
                logger.info(f"[Worker {self.worker_id}] 📂 Perfil persistente carregado com sucesso ({profile_state_path.name}).")

        context: BrowserContext = await browser.new_context(**context_kwargs)

        # Injeta cookies externos de arquivo se configurado
        cookies_file = getattr(self.config, "cookies_file", None)
        if cookies_file and (not profile_state_path or not profile_state_path.exists()):
            from src.utils.helpers import parse_cookies_file
            cookies_to_add = parse_cookies_file(cookies_file, worker_id=self.worker_id)
            if cookies_to_add:
                try:
                    await context.add_cookies(cookies_to_add)
                    logger.info(f"[Worker {self.worker_id}] 🍪 {len(cookies_to_add)} cookies injetados a partir de {cookies_file}.")
                except Exception as e:
                    logger.warning(f"[Worker {self.worker_id}] ⚠️ Falha ao injetar cookies: {e}")

        try:
            # Modo Ultra-Leve / Economia de tráfego: intercepta e bloqueia imagens, fontes, trackers e anúncios
            if getattr(self.config, "block_heavy_media", True) or self.config.proxy_low_bandwidth_mode:
                # Qualidade de vídeo variada entre 144p, 240p e 360p para parecer orgânica.
                # 144p com maior probabilidade para economizar banda, mas não sempre (padrão suspeito).
                quality_options = ["tiny", "small", "medium"]  # 144p, 240p, 360p
                quality_weights = [0.50, 0.35, 0.15]
                chosen_quality = random.choices(quality_options, weights=quality_weights, k=1)[0]
                logger.debug(f"[Worker {self.worker_id}] 🎬 Qualidade de vídeo selecionada: {chosen_quality} (144p/240p/360p sortido)")

                await context.add_init_script(f"""() => {{
                    try {{
                        const q = '{chosen_quality}';
                        localStorage.setItem('yt-player-quality', JSON.stringify({{
                            data: JSON.stringify({{quality: q, previousQuality: q}}),
                            expiration: Date.now() + 86400000000
                        }}));
                    }} catch(e) {{}}
                }}""")

                # BLOCKED_DOMAINS: apenas trackers e anúncios.
                # IMPORTANTE: play.google.com/log e i.ytimg.com NÃO são bloqueados —
                # play.google.com/log é o endpoint de heartbeat de reprodução pelo qual o
                # YouTube registra o watch time; i.ytimg.com serve storyboard sprites usados
                # para validação de progresso real. Bloqueá-los impede o registro no Analytics.
                BLOCKED_DOMAINS = [
                    "doubleclick.net",
                    "googleads",
                    "googleadservices.com",
                    "googlesyndication.com",
                    "adservice.google.com",
                    "yt3.ggpht.com",
                    # "i.ytimg.com",        # NÃO bloquear: storyboard validation
                    # "play.google.com/log", # NÃO bloquear: heartbeat de watch time
                ]

                async def _low_bandwidth_filter(route):
                    try:
                        req = route.request
                        url_lower = req.url.lower()

                        # Bloqueia domínios de anúncios e telemetria de ads
                        if any(domain in url_lower for domain in BLOCKED_DOMAINS) and "videoplayback" not in url_lower:
                            await route.abort()
                            return

                        # Bloqueia imagens e fontes estáticas secundárias
                        # Exceção: i.ytimg.com pode servir storyboard (resource_type=image), então é permitido
                        if req.resource_type in ["image", "font"] and "videoplayback" not in url_lower and "i.ytimg.com" not in url_lower:
                            await route.abort()
                            return

                        # Bloqueia media que não seja o stream de vídeo real
                        if req.resource_type == "media" and "videoplayback" not in url_lower:
                            await route.abort()
                            return
                    except Exception:
                        pass
                    try:
                        await route.continue_()
                    except Exception:
                        pass

                await context.route("**/*", _low_bandwidth_filter)

            # Silencia o vídeo via JS com MutationObserver — preserva o pipeline de áudio
            # do sistema operacional (usado pelo YouTube para confirmar engajamento real),
            # mas impede que o usuário ouça o som durante a automação.
            if self.config.mute_audio:
                await context.add_init_script("""() => {
                    try {
                        const muteAll = () => {
                            document.querySelectorAll('video').forEach(v => { v.muted = true; });
                        };
                        muteAll();
                        const observer = new MutationObserver(muteAll);
                        observer.observe(document.documentElement, { childList: true, subtree: true });
                    } catch(e) {}
                }""")
                logger.debug(f"[Worker {self.worker_id}] 🔇 Silenciamento via JS ativo (pipeline de áudio do OS preservado).")

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

            proxy_desc = format_proxy_display(self.proxy_url) if self.proxy_url else "Conexão Direta (Local)"

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
                        gpu_info=gpu_desc,
                        proxy_info=proxy_desc,
                    )
            except Exception:
                pass

            page = await context.new_page()

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
            if profile_state_path:
                try:
                    await context.storage_state(path=str(profile_state_path))
                    logger.debug(f"[Worker {self.worker_id}] 💾 Perfil persistente salvo em disco ({profile_state_path.name}).")
                except Exception as e:
                    logger.debug(f"[Worker {self.worker_id}] Falha ao salvar perfil persistente: {e}")
            try:
                await context.close()
            except Exception:
                pass

