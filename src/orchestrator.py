from __future__ import annotations

import asyncio
from datetime import datetime
import itertools
import logging
import random
import time
from typing import List, Optional

from src.browser.playwright_worker import PlaywrightWorker
from src.config import BotConfig
from src.utils.helpers import random_async_sleep
from src.utils.logger import MetricsTracker, SessionMetric

logger = logging.getLogger("bot")


class BotOrchestrator:
    """Orquestrador responsável pelo gerenciamento de concorrência, filas e métricas."""

    def __init__(self, config: BotConfig, tracker: MetricsTracker):
        self.config = config
        self.tracker = tracker
        self.stop_event = asyncio.Event()
        self.semaphore = asyncio.Semaphore(config.workers)
        self.active_tasks: List[asyncio.Task] = []
        self._session_lock = asyncio.Lock()
        self._global_session_id = 0
        self._monitor_task: Optional[asyncio.Task] = None
        self.max_end_time: Optional[float] = None
        self.worker_proxies: dict[int, Optional[str]] = {}
        self.worker_block_counts: dict[int, int] = {}
        self.worker_proxy_indices: dict[int, int] = {}
        self.quarantined_proxies: dict[str, float] = {}

    def is_proxy_quarantined(self, proxy_str: Optional[str]) -> bool:
        """Verifica se o proxy está atualmente em período de quarentena (cooldown por bloqueio)."""
        if not proxy_str:
            return False
        expiry = self.quarantined_proxies.get(proxy_str)
        if expiry is None:
            return False
        if time.time() >= expiry:
            del self.quarantined_proxies[proxy_str]
            return False
        return True

    def quarantine_proxy(self, proxy_str: Optional[str], duration_seconds: Optional[float] = None) -> None:
        """Coloca um proxy em quarentena temporária para evitar reutilização enquanto o IP estiver sinalizado."""
        if not proxy_str:
            return
        if duration_seconds is None:
            quarantine_mins = getattr(self.config, "proxy_quarantine_minutes", 30.0)
            duration_seconds = quarantine_mins * 60.0
        self.quarantined_proxies[proxy_str] = time.time() + duration_seconds
        from src.utils.helpers import format_proxy_display
        logger.warning(
            f"🔒 Proxy colocado em quarentena por {duration_seconds/60:.1f}min: {format_proxy_display(proxy_str)}"
        )

    def get_worker_proxy(self, worker_id: int) -> Optional[str]:
        """Retorna o proxy atualmente ativo atribuído a este worker, garantindo que não esteja em quarentena."""
        if worker_id not in self.worker_proxies:
            proxies = self.config.resolve_proxies()
            if not self.config.enable_proxy or not proxies:
                self.worker_proxies[worker_id] = self.config.get_proxy_for_worker(worker_id)
                self.worker_proxy_indices[worker_id] = (worker_id - 1)
            else:
                active_proxies = {p for w, p in self.worker_proxies.items() if w != worker_id and p}
                start_idx = (worker_id - 1) % len(proxies)
                chosen = None
                chosen_idx = start_idx
                for offset in range(len(proxies)):
                    idx = (start_idx + offset) % len(proxies)
                    candidate = proxies[idx]
                    if candidate not in active_proxies and not self.is_proxy_quarantined(candidate):
                        chosen = candidate
                        chosen_idx = idx
                        break

                if chosen is None:
                    # Todos os proxies da lista estão em uso ou quarentena: gera sessão dinâmica on-the-fly
                    base_p = proxies[start_idx]
                    from src.utils.helpers import rotate_proxy_session
                    chosen = rotate_proxy_session(base_p, worker_id)
                    chosen_idx = start_idx

                self.worker_proxies[worker_id] = chosen
                self.worker_proxy_indices[worker_id] = chosen_idx

            self.worker_block_counts[worker_id] = 0

        return self.worker_proxies[worker_id]

    def rotate_worker_proxy(self, worker_id: int) -> Optional[str]:
        """
        Substitui automaticamente o proxy/IP do worker após múltiplos bloqueios consecutivos.
        1. Coloca o proxy/IP atual em quarentena (padrão: 30 minutos).
        2. Varre a lista (pool de 100+ proxies) procurando o próximo IP livre não quarentenado.
        3. Caso a lista se esgote ou todos os 100 estejam em quarentena/uso, ativa o fallback dinâmico:
           gera um token aleatório único de sessão (sessid.w{worker_id}_{uuid}), garantindo um pool infinito
           de IPs residenciais novos entregues pela DataImpulse sem risco de repetição.
        """
        from src.utils.helpers import rotate_proxy_session, format_proxy_display

        current_proxy = self.get_worker_proxy(worker_id)
        if current_proxy:
            self.quarantine_proxy(current_proxy)

        proxies = self.config.resolve_proxies()
        active_proxies = {p for w, p in self.worker_proxies.items() if w != worker_id and p}

        new_proxy = None
        new_idx = self.worker_proxy_indices.get(worker_id, worker_id - 1)

        if proxies and len(proxies) > 1:
            curr_idx = self.worker_proxy_indices.get(worker_id, worker_id - 1)
            for offset in range(1, len(proxies) + 1):
                cand_idx = (curr_idx + offset) % len(proxies)
                candidate = proxies[cand_idx]
                if candidate not in active_proxies and not self.is_proxy_quarantined(candidate):
                    new_proxy = candidate
                    new_idx = cand_idx
                    break

        if not new_proxy:
            # Fallback dinâmico: gera sessão residencial única on-the-fly (pool infinito)
            base_proxy = current_proxy or (proxies[0] if proxies else (self.config.get_proxy_for_worker(worker_id) or ""))
            new_proxy = rotate_proxy_session(base_proxy, worker_id)
        else:
            new_proxy = rotate_proxy_session(new_proxy, worker_id)

        self.worker_proxy_indices[worker_id] = new_idx
        self.worker_proxies[worker_id] = new_proxy
        self.worker_block_counts[worker_id] = 0

        display_name = format_proxy_display(new_proxy)
        logger.warning(
            f"🔄 [Worker {worker_id}] 3 bloqueios consecutivos atingidos! "
            f"IP substituído automaticamente por novo IP residencial: {display_name}"
        )

        try:
            from src.web.state import StateManager
            sm = StateManager.get_instance()
            if sm.is_running:
                sm.update_worker(
                    worker_id=worker_id,
                    status="Novo IP Atribuído",
                    proxy_info=display_name,
                    current_watch_time=0.0
                )
                sm.append_log(
                    f"🔄 [Worker {worker_id}] 3 bloqueios atingidos! "
                    f"IP substituído automaticamente por novo IP residencial ({display_name})."
                )
        except Exception:
            pass

        return new_proxy

    def stop(self) -> None:
        """Sinaliza para todos os workers pararem a execução imediatamente."""

        if not self.stop_event.is_set():
            logger.warning("🛑 Sinal de interrupção recebido. Finalizando tarefas ativas...")
            self.stop_event.set()
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
        for task in self.active_tasks:
            if not task.done():
                task.cancel()

    async def _round_duration_monitor(self, max_seconds: float) -> None:
        """Monitora o tempo total da rodada. Quando atingir a duração máxima, encerra todos os workers."""
        try:
            logger.info(
                f"⏱️ Temporizador da Rodada ativado: Duração Total de {self.config.max_runtime_hours}h "
                f"({max_seconds:.0f}s)."
            )
            await asyncio.wait_for(self.stop_event.wait(), timeout=max_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                f"⏰ [Duração Total da Rodada Atingida] O tempo de {self.config.max_runtime_hours}h "
                f"({max_seconds:.0f}s) expirou! Encerrando todos os workers imediatamente..."
            )
            try:
                from src.web.state import StateManager
                sm = StateManager.get_instance()
                sm.append_log(
                    f"⏰ Duração Total da Rodada atingida ({self.config.max_runtime_hours}h). "
                    "Encerrando todos os workers automaticamente..."
                )
            except Exception:
                pass
            self.stop()
        except asyncio.CancelledError:
            pass

    async def _get_next_session_id(self) -> int:
        """Gera um ID único e incremental de sessão de forma assíncrona segura."""
        async with self._session_lock:
            self._global_session_id += 1
            return self._global_session_id

    async def _execute_single_session(self, worker_id: int, url: str, session_id: int) -> dict:
        """Executa uma sessão de visualização individual e registra suas métricas."""
        started_at = datetime.now().isoformat()
        proxy_url = self.get_worker_proxy(worker_id)
        worker = PlaywrightWorker(worker_id=worker_id, config=self.config, proxy_url=proxy_url)

        try:
            stats = await worker.execute_session(
                url=url,
                session_id=session_id,
                stop_event=self.stop_event,
                max_end_time=self.max_end_time
            )
        except asyncio.CancelledError:
            stats = {
                "session_id": session_id,
                "worker_id": worker_id,
                "url": url,
                "target_watch_time": 0,
                "actual_watch_time": 0.0,
                "ads_skipped": 0,
                "continue_dialogs_clicked": 0,
                "status": "INTERRUPTED",
                "error_message": "Sessão cancelada por encerramento da rodada ou pelo usuário",
            }
        except Exception as e:
            stats = {
                "session_id": session_id,
                "worker_id": worker_id,
                "url": url,
                "target_watch_time": 0,
                "actual_watch_time": 0.0,
                "ads_skipped": 0,
                "continue_dialogs_clicked": 0,
                "status": "FAILED",
                "error_message": str(e),
            }

        finished_at = datetime.now().isoformat()
        metric = SessionMetric(
            session_id=session_id,
            worker_id=worker_id,
            url=url,
            target_watch_time=stats.get("target_watch_time", 0),
            actual_watch_time=stats.get("actual_watch_time", 0.0),
            ads_skipped=stats.get("ads_skipped", 0),
            continue_dialogs_clicked=stats.get("continue_dialogs_clicked", 0),
            status=stats.get("status", "FAILED"),
            error_message=stats.get("error_message"),
            started_at=started_at,
            finished_at=finished_at,
        )
        self.tracker.record_session(metric)
        try:
            from src.web.state import StateManager
            sm = StateManager.get_instance()
            if sm.is_running:
                sm.update_metrics(metric)
        except Exception:
            pass

        return stats


    async def _worker_continuous_loop(
        self,
        worker_id: int,
        urls: List[str],
        max_runtime_seconds: Optional[float],
        global_start: float
    ) -> None:
        # Escalonamento gradual (stagger ramp-up) para evitar disparar todas as requisições juntas
        base_stagger = (worker_id - 1) * getattr(self.config, "worker_stagger_delay", 15.0)
        stagger = base_stagger + random.uniform(0.5, 2.5) if worker_id > 1 else random.uniform(0.5, 1.5)

        if stagger > 2.0:
            logger.info(
                f"[Worker {worker_id}] ⏳ Escalonamento ativo: aguardando {stagger:.1f}s antes de iniciar para evitar disparos simultâneos..."
            )
            try:
                from src.web.state import StateManager
                sm = StateManager.get_instance()
                if sm.is_running:
                    sm.update_worker(
                        worker_id=worker_id,
                        status=f"Inicia em {int(round(stagger))}s",
                        current_watch_time=0.0
                    )
            except Exception:
                pass

            start_wait = time.time()
            while (time.time() - start_wait) < stagger:
                if self.stop_event.is_set():
                    return
                remaining = int(round(stagger - (time.time() - start_wait)))
                try:
                    from src.web.state import StateManager
                    sm = StateManager.get_instance()
                    if sm.is_running and remaining > 0:
                        sm.update_worker(
                            worker_id=worker_id,
                            status=f"Inicia em {remaining}s",
                            current_watch_time=0.0
                        )
                except Exception:
                    pass
                try:
                    await asyncio.sleep(min(1.0, max(0.1, stagger - (time.time() - start_wait))))
                except asyncio.CancelledError:
                    return
        else:
            try:
                await asyncio.sleep(stagger)
            except asyncio.CancelledError:
                return

        # Distribui cada worker em um ponto diferente da lista de vídeos
        url_idx = (worker_id - 1) % len(urls)

        while not self.stop_event.is_set():
            if max_runtime_seconds is not None:
                elapsed = time.time() - global_start
                if elapsed >= max_runtime_seconds:
                    logger.info(
                        f"[Worker {worker_id}] ⏳ Duração Total da Rodada atingida ({elapsed / 3600:.2f}h). "
                        "Encerrando worker."
                    )
                    break

            target_url = urls[url_idx]
            if len(urls) > 1:
                url_idx = (url_idx + 1) % len(urls)

            session_id = await self._get_next_session_id()

            stats = await self._execute_single_session(worker_id=worker_id, url=target_url, session_id=session_id)
            session_status = stats.get("status", "FAILED") if isinstance(stats, dict) else "FAILED"

            if session_status == "SUCCESS":
                self.worker_block_counts[worker_id] = 0
            elif session_status == "BLOCKED":
                self.worker_block_counts[worker_id] = self.worker_block_counts.get(worker_id, 0) + 1
                blocks = self.worker_block_counts[worker_id]

                if blocks < 3:
                    cooloff = random.uniform(6.0, 10.0)
                    logger.warning(
                        f"[Worker {worker_id}] ⚠️ IP bloqueado pelo Google ({blocks}/3). "
                        f"Aguardando cooldown de {cooloff:.1f}s antes de tentar novamente..."
                    )
                    try:
                        from src.web.state import StateManager
                        sm = StateManager.get_instance()
                        if sm.is_running:
                            sm.update_worker(
                                worker_id=worker_id,
                                status=f"Bloqueado ({blocks}/3) - Cooldown",
                                current_watch_time=0.0
                            )
                    except Exception:
                        pass
                    try:
                        await asyncio.sleep(cooloff)
                    except asyncio.CancelledError:
                        break
                else:
                    # 3 bloqueios atingidos! Substitui o IP/proxy automaticamente
                    self.rotate_worker_proxy(worker_id)
                    try:
                        await asyncio.sleep(4.0)
                    except asyncio.CancelledError:
                        break

                # Pula a mensagem de "Watch time concluído" e tenta o próximo ciclo com o novo IP
                continue

            # Após o watch time máximo atingido da sessão bem-sucedida:
            if not self.stop_event.is_set():
                if max_runtime_seconds is not None:
                    elapsed = time.time() - global_start
                    if elapsed >= max_runtime_seconds:
                        logger.info(
                            f"[Worker {worker_id}] ⏳ Duração Total da Rodada atingida ({elapsed / 3600:.2f}h). "
                            "Encerrando worker."
                        )
                        break

                logger.info(
                    f"[Worker {worker_id}] 🔄 Watch time máximo concluído. Reiniciando vídeo para continuar assistindo até a Duração Total da Rodada."
                )

                delay_between = random.uniform(
                    self.config.min_delay_between_videos,
                    self.config.max_delay_between_videos
                )
                logger.info(
                    f"[Worker {worker_id}] ☕ Pausa breve antes de reiniciar o vídeo: {delay_between:.1f}s"
                )
                try:
                    from src.web.state import StateManager
                    sm = StateManager.get_instance()
                    if sm.is_running:
                        sm.update_worker(
                            worker_id=worker_id,
                            status="Reiniciando Vídeo",
                            current_watch_time=0.0
                        )
                except Exception:
                    pass

                try:
                    await asyncio.sleep(delay_between)
                except asyncio.CancelledError:
                    break


    async def run(self) -> None:
        """Executa a orquestração dos workers de acordo com as configurações."""
        urls = self.config.resolve_urls()
        if not urls:
            logger.error("❌ Nenhuma URL fornecida. Use --url ou configure um arquivo com --urls-file.")
            return

        is_continuous = self.config.continuous or (self.config.max_runtime_hours is not None)
        global_start = time.time()
        max_runtime_seconds = (
            self.config.max_runtime_hours * 3600.0 if self.config.max_runtime_hours else None
        )
        self.max_end_time = (global_start + max_runtime_seconds) if max_runtime_seconds else None

        logger.info(f"🚀 Iniciando orquestrador com [bold cyan]{self.config.workers}[/bold cyan] workers.")
        logger.info(f"📋 Total de vídeos na lista: [bold yellow]{len(urls)}[/bold yellow] URLs.")

        if self.config.enable_proxy:
            proxies = self.config.resolve_proxies()
            if self.config.proxy_session_template:
                logger.info("🌐 Modo Proxy: Gateway único com isolamento de sessão por worker.")
            else:
                logger.info(f"🌐 Modo Proxy: [bold green]{len(proxies)}[/bold green] proxies carregados na rotação.")
            if self.config.proxy_low_bandwidth_mode:
                logger.info("💡 Modo Economia de Banda do Proxy ativado (144p + Bloqueio de Imagens/Fontes).")
        else:
            logger.info("🌐 Conexão de Rede: Direta / Local (Sem proxy configurado).")

        tasks: List[asyncio.Task] = []


        # Se houver limite de tempo definido, ativa o monitor automático da rodada
        if max_runtime_seconds is not None:
            self._monitor_task = asyncio.create_task(
                self._round_duration_monitor(max_runtime_seconds)
            )

        if is_continuous:
            duration_desc = f"{self.config.max_runtime_hours}h" if self.config.max_runtime_hours else "ininterrupto"
            logger.info(f"🔁 Modo contínuo ativado (Duração planejada: [bold green]{duration_desc}[/bold green]).")
            tasks = [
                asyncio.create_task(
                    self._worker_continuous_loop(
                        worker_id=worker_id,
                        urls=urls,
                        max_runtime_seconds=max_runtime_seconds,
                        global_start=global_start
                    )
                )
                for worker_id in range(1, self.config.workers + 1)
            ]
            self.active_tasks.extend(tasks)
        else:
            logger.info(f"🎯 Meta total de visualizações: [bold green]{self.config.total_views}[/bold green] sessões.")
            url_cycle = itertools.cycle(urls)
            for _ in range(self.config.total_views):
                if self.stop_event.is_set():
                    break
                session_id = await self._get_next_session_id()
                target_url = next(url_cycle)
                worker_id = ((session_id - 1) % self.config.workers) + 1

                async def _task_wrapper(w_id=worker_id, u=target_url, s_id=session_id):
                    async with self.semaphore:
                        base_stagger = (w_id - 1) * getattr(self.config, "worker_stagger_delay", 15.0)
                        stagger = base_stagger + random.uniform(0.5, 2.5) if w_id > 1 else random.uniform(0.5, 1.5)
                        try:
                            await asyncio.sleep(stagger)
                        except asyncio.CancelledError:
                            return
                        stats = await self._execute_single_session(worker_id=w_id, url=u, session_id=s_id)
                        if isinstance(stats, dict) and stats.get("status") == "BLOCKED":
                            self.worker_block_counts[w_id] = self.worker_block_counts.get(w_id, 0) + 1
                            if self.worker_block_counts[w_id] >= 3:
                                self.rotate_worker_proxy(w_id)


                task = asyncio.create_task(_task_wrapper())
                tasks.append(task)
                self.active_tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception) and not isinstance(res, asyncio.CancelledError):
                    logger.error(f"Erro inesperado em worker: {res}")
        except asyncio.CancelledError:
            pass
        finally:
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
            logger.info("🏁 Todos os workers foram encerrados.")
