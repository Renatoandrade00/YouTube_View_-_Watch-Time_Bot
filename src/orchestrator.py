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

    def stop(self) -> None:
        """Sinaliza para todos os workers pararem a execução imediatamente."""
        logger.warning("🛑 Sinal de interrupção recebido. Finalizando tarefas ativas...")
        self.stop_event.set()
        for task in self.active_tasks:
            if not task.done():
                task.cancel()

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
            stats = await worker.execute_session(url=url, session_id=session_id)
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
                "error_message": "Sessão cancelada por interrupção do usuário",
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
        """Loop contínuo de um worker: assiste vídeos da lista sequencialmente até o tempo limite."""
        stagger = (worker_id - 1) * 1.5 + random.uniform(0.5, 2.0)
        await asyncio.sleep(stagger)

        # Distribui cada worker em um ponto diferente da lista de vídeos
        url_idx = (worker_id - 1) % len(urls)

        while not self.stop_event.is_set():
            if max_runtime_seconds is not None:
                elapsed = time.time() - global_start
                if elapsed >= max_runtime_seconds:
                    logger.info(
                        f"[Worker {worker_id}] ⏳ Meta total de tempo atingida ({elapsed / 3600:.1f}h). "
                        "Encerrando rotina do worker."
                    )
                    break

            target_url = urls[url_idx]
            url_idx = (url_idx + 1) % len(urls)
            session_id = await self._get_next_session_id()

            await self._execute_single_session(worker_id=worker_id, url=target_url, session_id=session_id)

            if not self.stop_event.is_set():
                # Pausa natural realista entre a troca de vídeos (tempo de escolha do usuário)
                delay_between = random.uniform(
                    self.config.min_delay_between_videos,
                    self.config.max_delay_between_videos
                )
                logger.info(
                    f"[Worker {worker_id}] ☕ Pausa natural antes do próximo vídeo: {delay_between:.1f}s"
                )
                try:
                    from src.web.state import StateManager
                    sm = StateManager.get_instance()
                    if sm.is_running:
                        sm.update_worker(
                            worker_id=worker_id,
                            status="Pausa Natural",
                            current_watch_time=0.0
                        )
                except Exception:
                    pass
                await asyncio.sleep(delay_between)

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

        logger.info(f"🚀 Iniciando orquestrador com [bold cyan]{self.config.workers}[/bold cyan] workers.")
        logger.info(f"📋 Total de vídeos na lista: [bold yellow]{len(urls)}[/bold yellow] URLs.")

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
            tasks = []
            for _ in range(self.config.total_views):
                if self.stop_event.is_set():
                    break
                session_id = await self._get_next_session_id()
                target_url = next(url_cycle)
                worker_id = ((session_id - 1) % self.config.workers) + 1

                async def _task_wrapper(w_id=worker_id, u=target_url, s_id=session_id):
                    async with self.semaphore:
                        if not self.stop_event.is_set():
                            stagger = (w_id - 1) * 1.5 + random.uniform(0.5, 2.0)
                            await asyncio.sleep(stagger)
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
            logger.info("🏁 Todas as sessões foram processadas.")
