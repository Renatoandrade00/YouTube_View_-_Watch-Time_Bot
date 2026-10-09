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

    async def _execute_single_session(self, worker_id: int, url: str, session_id: int) -> None:
        """Executa uma sessão de visualização individual e registra suas métricas."""
        started_at = datetime.now().isoformat()
        worker = PlaywrightWorker(worker_id=worker_id, config=self.config)

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

            await self._execute_single_session(worker_id=worker_id, url=target_url, session_id=session_id)

            # Após o watch time máximo atingido da sessão:
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
                            await self._execute_single_session(worker_id=w_id, url=u, session_id=s_id)

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
