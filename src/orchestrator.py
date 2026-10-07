from __future__ import annotations

import asyncio
from datetime import datetime
import itertools
import logging
import random
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

    def stop(self) -> None:
        """Sinaliza para todos os workers pararem a execução imediatamente."""
        logger.warning("🛑 Sinal de interrupção recebido. Finalizando tarefas ativas...")
        self.stop_event.set()
        for task in self.active_tasks:
            if not task.done():
                task.cancel()

    async def _worker_routine(self, worker_id: int, url: str, session_id: int) -> None:
        """Rotina individual executada dentro do semáforo de concorrência."""
        if self.stop_event.is_set():
            return

        async with self.semaphore:
            if self.stop_event.is_set():
                return

            started_at = datetime.now().isoformat()
            worker = PlaywrightWorker(worker_id=worker_id, config=self.config)

            try:
                # Escalonamento suave para inicializar instâncias sem sobrecarregar a CPU
                stagger = (worker_id - 1) * 1.5 + random.uniform(0.5, 2.0)
                await asyncio.sleep(stagger)

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

    async def run(self) -> None:
        """Executa a orquestração de todas as sessões configuradas."""
        urls = self.config.resolve_urls()
        if not urls:
            logger.error("❌ Nenhuma URL fornecida. Use --url ou configure um arquivo com --urls-file.")
            return

        logger.info(f"🚀 Iniciando orquestrador com [bold cyan]{self.config.workers}[/bold cyan] workers.")
        logger.info(f"🎯 Meta total de visualizações: [bold green]{self.config.total_views}[/bold green] sessões.")

        url_cycle = itertools.cycle(urls)
        tasks = []

        for session_id in range(1, self.config.total_views + 1):
            if self.stop_event.is_set():
                break

            target_url = next(url_cycle)
            worker_id = ((session_id - 1) % self.config.workers) + 1
            task = asyncio.create_task(
                self._worker_routine(
                    worker_id=worker_id,
                    url=target_url,
                    session_id=session_id
                )
            )
            tasks.append(task)
            self.active_tasks.append(task)

        # Aguarda a finalização de todas as sessões
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception) and not isinstance(res, asyncio.CancelledError):
                    logger.error(f"Erro inesperado em worker: {res}")
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("🏁 Todas as sessões foram processadas.")
