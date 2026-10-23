from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict, Any, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.config import BotConfig
from src.youtube.ads import try_skip_ad
from src.youtube.continue_watching import handle_continue_watching_dialog
from src.youtube.interactions import simulate_human_micro_interactions
from src.utils.helpers import random_async_sleep
from src.utils.telemetry import get_collector

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


async def ensure_video_playing(page: Page, mute_audio: bool = True, low_bandwidth: bool = False) -> bool:
    """Garante que o elemento de vídeo HTML5 está em reprodução ativa."""
    try:
        # Primeiro tenta via injeção JS direta no elemento <video> e configuração de bitrate
        result = await page.evaluate(f"""() => {{
            const video = document.querySelector('video');
            const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
            if (!video) return {{ found: false }};
            if ({str(mute_audio).lower()}) {{
                // Preserva muted=false com volume sutil para que o beacon /api/stats/watchtime
                // registre volume positivo e estado sonoro válido no algoritmo do YouTube.
                try {{
                    if (video.muted) {{ video.muted = false; }}
                    if (video.volume > 0.15) {{ video.volume = 0.05; }}
                }} catch(e) {{}}
            }}
            let pState = player && typeof player.getPlayerState === 'function' ? player.getPlayerState() : -1;
            // Se o player estiver pausado (pState == 2), em buffer inicial (pState == -1) ou video.paused
            if (video.paused || pState === 2 || pState === -1) {{
                if (player && typeof player.playVideo === 'function') {{
                    player.playVideo();
                }} else {{
                    video.play().catch(() => {{}});
                }}
            }}
            return {{
                found: true,
                paused: video.paused,
                playerState: pState,
                currentTime: video.currentTime,
                duration: video.duration
            }};
        }}""")

        if result.get("found"):
            return True
    except Exception as e:
        logger.debug(f"Aviso ao verificar status do player: {e}")

    return False



async def watch_video(
    page: Page,
    url: str,
    target_watch_seconds: int,
    config: BotConfig,
    worker_id: int,
    stop_event: asyncio.Event | None = None,
    max_end_time: float | None = None,
    session_id: int = 0,
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
        custom_kw = None
        if hasattr(config, "custom_keywords") and isinstance(config.custom_keywords, dict):
            custom_kw = config.custom_keywords.get(url)

        if getattr(config, "search_and_play", False):
            from src.youtube.search_flow import perform_search_and_play
            await perform_search_and_play(page, url, worker_id, custom_keyword=custom_kw)
        else:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except PlaywrightTimeoutError:
        stats["error_message"] = "Timeout de carregamento da página"
        logger.warning(f"[Worker {worker_id}] ⚠️ Timeout ao carregar a página inicial.")
        return stats
    except Exception as e:
        stats["error_message"] = str(e)
        logger.error(f"[Worker {worker_id}] ❌ Erro ao navegar para o vídeo: {e}")
        return stats

    # Detecta imediatamente redirecionamento para tela de CAPTCHA / bloqueio do Google
    raw_url = getattr(page, "url", "")
    page_url_str = raw_url if isinstance(raw_url, str) else str(raw_url)
    current_url_lower = page_url_str.lower()
    if "sorry/index" in current_url_lower or "google.com/sorry" in current_url_lower:
        if getattr(config, "telemetry_enabled", True):
            get_collector().record(worker_id, session_id, "blocked", "google_sorry_redirect")
        stats["status"] = "BLOCKED"
        stats["error_message"] = "Bloqueio temporário do Google (CAPTCHA / Tráfego Incomum detectado)"
        logger.error(
            f"[Worker {worker_id}] 🛑 Bloqueio temporário do Google detectado! (URL: {page_url_str[:80]}...). "
            "A rede/IP foi temporariamente sinalizada por requisições em massa simultâneas. "
            "Aguarde o esfriamento do IP ou utilize intervalo maior entre workers."
        )
        try:
            from src.web.state import StateManager
            sm = StateManager.get_instance()
            if sm.is_running:
                sm.update_worker(
                    worker_id=worker_id,
                    status="Bloqueio/CAPTCHA",
                    current_watch_time=0.0
                )
        except Exception:
            pass
        return stats

    # Se a rodada já acabou ou foi solicitado stop durante o carregamento
    if stop_event and stop_event.is_set():
        stats["error_message"] = "Interrupção solicitada"
        return stats
    if max_end_time and time.time() >= max_end_time:
        stats["error_message"] = "Duração Total da Rodada atingida"
        return stats

    # Lida com consentimento de cookies se aparecer
    await handle_consent_popups(page)
    await random_async_sleep(1.0, 2.5)

    # Inicia e confere o player
    is_low_bw = getattr(config, "block_heavy_media", True) or getattr(config, "proxy_low_bandwidth_mode", True)
    await ensure_video_playing(page, mute_audio=config.mute_audio, low_bandwidth=is_low_bw)

    start_time = time.time()
    last_active_time = start_time
    last_interaction_time = start_time
    last_progress_time = start_time
    last_recovery_time = 0.0
    accumulated_watch_time = 0.0
    last_video_current_time: float | None = None
    stuck_buffer_count = 0
    sleep_duration = max(1.0, config.poll_interval)
    stuck_level1_seconds = 15.0
    stuck_level2_seconds = 35.0
    stuck_level3_seconds = 60.0
    recovery_min_interval_seconds = 5.0

    while accumulated_watch_time < target_watch_seconds:
        # Verifica se o bot foi parado ou se a Duração Total da Rodada encerrou
        if stop_event and stop_event.is_set():
            logger.info(f"[Worker {worker_id}] 🛑 Interrupção detectada. Encerrando reprodução.")
            break
        if max_end_time and time.time() >= max_end_time:
            logger.info(f"[Worker {worker_id}] ⏰ Fim da Duração Total da Rodada atingido durante a reprodução. Encerrando.")
            break

        current_now = time.time()
        elapsed_loop = current_now - last_active_time
        last_active_time = current_now

        # Verifica se houve redirecionamento para tela de bloqueio durante o loop
        raw_loop_url = getattr(page, "url", "")
        loop_url = (raw_loop_url if isinstance(raw_loop_url, str) else str(raw_loop_url)).lower()
        if "sorry/index" in loop_url or "google.com/sorry" in loop_url:
            stats["status"] = "BLOCKED"
            stats["error_message"] = "Redirecionado para bloqueio do Google (CAPTCHA / Tráfego Incomum)"
            logger.error(f"[Worker {worker_id}] 🛑 Redirecionado para tela de bloqueio do Google Sorry.")
            try:
                from src.web.state import StateManager
                sm = StateManager.get_instance()
                if sm.is_running:
                    sm.update_worker(
                        worker_id=worker_id,
                        status="Bloqueio/CAPTCHA",
                        current_watch_time=accumulated_watch_time
                    )
            except Exception:
                pass
            break

        # 1. Pular anúncios se configurado
        if config.skip_ads:
            if await try_skip_ad(page):
                stats["ads_skipped"] += 1

        # 2. Clicar no popup de 'Continuar assistindo' se configurado
        if config.auto_continue:
            if await handle_continue_watching_dialog(page):
                stats["continue_dialogs_clicked"] += 1
                await ensure_video_playing(page, mute_audio=config.mute_audio, low_bandwidth=is_low_bw)

        # 3. Inspecionar estado do vídeo no DOM
        try:
            video_state = await page.evaluate("""() => {
                const video = document.querySelector('video');
                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                if (!video) return { exists: false };
                const isAd = Boolean(
                    document.querySelector('.ad-showing, .ad-interrupting, .ytp-ad-player-overlay') ||
                    (player && player.classList && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting')))
                );
                return {
                    exists: true,
                    paused: video.paused,
                    ended: video.ended,
                    currentTime: video.currentTime,
                    duration: video.duration,
                    readyState: video.readyState,
                    playerState: player && typeof player.getPlayerState === 'function' ? player.getPlayerState() : -1,
                    isAd: isAd
                };
            }""")

            if video_state.get("exists"):
                current_ct = float(video_state.get("currentTime") or 0.0)
                duration = float(video_state.get("duration") or 0.0)
                is_paused = video_state.get("paused", False)
                is_ended = video_state.get("ended", False)
                p_state = video_state.get("playerState", -1)
                is_ad = video_state.get("isAd", False)

                if is_ad:
                    if config.skip_ads:
                        if await try_skip_ad(page):
                            stats["ads_skipped"] += 1
                    # Não trata anúncio como buffering travado do vídeo principal
                    stuck_buffer_count = 0
                    last_progress_time = current_now

                elif last_video_current_time is None or current_ct < (last_video_current_time - 2.0):
                    # Primeira leitura do player ou vídeo reiniciou/voltou (seek/reload/loop)
                    last_video_current_time = current_ct
                    last_progress_time = current_now
                    stuck_buffer_count = 0

                elif is_ended:
                    # Conta o segmento restante até o fim antes de reiniciar o vídeo
                    segment = max(0.0, duration - last_video_current_time)
                    accumulated_watch_time += segment
                    last_progress_time = current_now
                    last_video_current_time = 0.0
                    stuck_buffer_count = 0
                    logger.info(
                        f"[Worker {worker_id}] 🔄 Vídeo finalizou aos {accumulated_watch_time:.0f}s. "
                        f"Reiniciando do início para continuar assistindo até a meta ({target_watch_seconds}s)..."
                    )
                    try:
                        await page.evaluate("""() => {
                            const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                            if (player && typeof player.playVideo === 'function') {
                                player.seekTo(0, true);
                                player.playVideo();
                            } else {
                                const video = document.querySelector('video');
                                if (video) {
                                    video.currentTime = 0;
                                    video.play().catch(() => {});
                                }
                            }
                        }""")
                        await ensure_video_playing(page, mute_audio=config.mute_audio, low_bandwidth=is_low_bw)
                    except Exception as err:
                        logger.debug(f"[Worker {worker_id}] Erro ao reiniciar reprodução do vídeo: {err}")

                elif is_paused or p_state == 2:
                    stuck_buffer_count += 1
                    await page.evaluate("""() => {
                        const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                        if (player && typeof player.playVideo === 'function') {
                            player.playVideo();
                        }
                        const v = document.querySelector('video');
                        if (v && v.paused) { v.play().catch(() => {}); }
                    }""")

                else:
                    # Conta o avanço real do currentTime do player (watch time efetivo),
                    # não apenas o tempo de parede, para não superestimar horas.
                    delta = max(0.0, current_ct - last_video_current_time)
                    if delta > 0.05:
                        accumulated_watch_time += delta
                        last_video_current_time = current_ct
                        last_progress_time = current_now
                        stuck_buffer_count = 0
                    else:
                        # Sem avanço de currentTime: possível buffering/travamento
                        stuck_buffer_count += 1

                # Mecanismo de Recuperação Adaptativa de Buffering / Travamento (Auto-Recovery)
                no_progress_for = current_now - last_progress_time
                if stuck_buffer_count >= 2 and getattr(config, "auto_player_recovery", True):
                    if getattr(config, "telemetry_enabled", True):
                        get_collector().record(worker_id, session_id, "buffering", f"stuck_{stuck_buffer_count}_no_progress_{no_progress_for:.1f}s")
                    try:
                        from src.web.state import StateManager
                        sm = StateManager.get_instance()
                        if sm.is_running:
                            sm.update_worker(
                                worker_id=worker_id,
                                status=f"Recuperando ({stuck_buffer_count}x)",
                                current_watch_time=accumulated_watch_time
                            )
                    except Exception:
                        pass

                    if current_now - last_recovery_time < recovery_min_interval_seconds:
                        # Evita disparos repetitivos de recuperação em curto intervalo
                        pass
                    elif no_progress_for >= stuck_level3_seconds:
                        logger.warning(
                            f"[Worker {worker_id}] 🔄 Buffering persistente sem avanço (~{stuck_level3_seconds:.0f}s). "
                            f"Recarregando página preservando tempo acumulado ({accumulated_watch_time:.0f}s)..."
                        )
                        last_recovery_time = current_now
                        stuck_buffer_count = 0
                        last_progress_time = current_now
                        last_video_current_time = None
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            await asyncio.sleep(2.0)
                            await handle_consent_popups(page)
                            await ensure_video_playing(page, mute_audio=config.mute_audio, low_bandwidth=is_low_bw)
                        except Exception as e:
                            logger.debug(f"[Worker {worker_id}] Falha ao recarregar página para auto-recovery: {e}")

                    elif no_progress_for >= stuck_level2_seconds:
                        logger.warning(
                            f"[Worker {worker_id}] ⚠️ Buffering persistente (~{stuck_level2_seconds:.0f}s). "
                            "Forçando avanço sutil de frame e play..."
                        )
                        last_recovery_time = current_now
                        try:
                            await page.evaluate("""() => {
                                const v = document.querySelector('video');
                                if (v) {
                                    v.currentTime = Math.min(v.duration || 9999, v.currentTime + 0.5);
                                }
                                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                                if (player && typeof player.playVideo === 'function') {
                                    player.playVideo();
                                }
                            }""")
                        except Exception:
                            pass

                    elif no_progress_for >= stuck_level1_seconds:
                        logger.warning(
                            f"[Worker {worker_id}] ⚠️ Player estagnado (~{stuck_level1_seconds:.0f}s). Acionando playVideo()..."
                        )
                        last_recovery_time = current_now
                        try:
                            await page.evaluate("""() => {
                                const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
                                if (player && typeof player.playVideo === 'function') {
                                    player.playVideo();
                                }
                                const v = document.querySelector('video');
                                if (v && v.paused) { v.play().catch(() => {}); }
                            }""")
                        except Exception:
                            pass
            else:
                # Se não encontrou o elemento de vídeo após 15s de navegação, verifica se caiu em bloqueio textual
                if (time.time() - start_time) > 15.0 and accumulated_watch_time == 0:
                    try:
                        body_txt = await page.inner_text("body")
                        if any(term in body_txt.lower() for term in ["tráfego incomum", "unusual traffic", "não é um robô", "not a robot"]):
                            stats["status"] = "BLOCKED"
                            stats["error_message"] = "Bloqueio do Google detectado no conteúdo da página"
                            logger.error(f"[Worker {worker_id}] 🛑 Mensagem de tráfego incomum detectada na página.")
                            try:
                                from src.web.state import StateManager
                                sm = StateManager.get_instance()
                                if sm.is_running:
                                    sm.update_worker(
                                        worker_id=worker_id,
                                        status="Bloqueio/CAPTCHA",
                                        current_watch_time=0.0
                                    )
                            except Exception:
                                pass
                            break
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"[Worker {worker_id}] Exceção na verificação periódica: {e}")

        # 4. Micro-interações humanas e renovação periódica de lact (Last Active User Time < 15s)
        now_ts = time.time()
        should_interact = config.enable_micro_interactions and (
            (now_ts - last_interaction_time) >= 12.0 or random.random() < 0.40
        )
        if should_interact:
            await simulate_human_micro_interactions(
                page, worker_id, getattr(config, "human_behavior_profile", "mixed")
            )
            last_interaction_time = now_ts

        stats["actual_watch_time"] = round(accumulated_watch_time, 1)

        # Log de progresso periódico a cada ~60 segundos
        if int(accumulated_watch_time) > 0 and int(accumulated_watch_time) % 60 < sleep_duration:
            logger.info(
                f"[Worker {worker_id}] ⏱️ Progresso: {accumulated_watch_time:.0f}s / {target_watch_seconds}s "
                f"({accumulated_watch_time / 60:.1f} / {target_watch_seconds / 60:.1f} min)"
            )

        # Intervalo do polling com jitter de ±30% para quebrar padrão mecânico detectável
        base_interval = max(1.0, config.poll_interval)
        jitter = random.uniform(-base_interval * 0.30, base_interval * 0.50)
        sleep_duration = max(1.0, base_interval + jitter)
        try:
            from src.web.state import StateManager
            sm = StateManager.get_instance()
            if sm.is_running:
                sm.update_worker(
                    worker_id=worker_id,
                    status="Assistindo",
                    current_watch_time=accumulated_watch_time,
                    target_watch_time=target_watch_seconds,
                    ads_skipped=stats["ads_skipped"],
                    continue_clicked=stats["continue_dialogs_clicked"]
                )
        except Exception:
            pass

        await asyncio.sleep(sleep_duration)

    stats["actual_watch_time"] = round(accumulated_watch_time, 1)
    stats["status"] = "SUCCESS" if accumulated_watch_time >= 25.0 else "FAILED"
    logger.info(f"[Worker {worker_id}] 🎯 Watch time máximo atingido! Assistido: {stats['actual_watch_time']}s / Meta: {target_watch_seconds}s")
    try:
        from src.web.state import StateManager
        sm = StateManager.get_instance()
        if sm.is_running:
            sm.update_worker(
                worker_id=worker_id,
                status="Concluído" if stats["status"] == "SUCCESS" else "Falha",
                current_watch_time=stats["actual_watch_time"],
                ads_skipped=stats["ads_skipped"],
                continue_clicked=stats["continue_dialogs_clicked"]
            )
    except Exception:
        pass
    return stats
