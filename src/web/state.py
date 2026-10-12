from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket


@dataclass
class WorkerState:
    worker_id: int
    status: str = "Aguardando"
    current_url: str = ""
    current_watch_time: float = 0.0
    target_watch_time: float = 0.0
    progress_pct: float = 0.0
    gpu_info: str = "GPU Padrão"
    proxy_info: str = "Conexão Direta (Local)"
    ads_skipped: int = 0
    continue_clicked: int = 0
    last_update: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



class WebSocketLogHandler(logging.Handler):
    """Handler de log customizado que repassa logs para o StateManager."""

    def __init__(self, state_manager: StateManager):
        super().__init__()
        self.state_manager = state_manager

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname
            timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            self.state_manager.append_log(f"[{timestamp}] [{level}] {msg}")
        except Exception:
            self.handleError(record)


class StateManager:
    """Gerenciador central de estado da execução e ponte com clientes WebSocket."""

    _instance: Optional[StateManager] = None

    def __init__(self) -> None:
        self.is_running: bool = False
        self.workers: Dict[int, WorkerState] = {}
        self.recent_logs: deque[str] = deque(maxlen=200)
        self.active_connections: Set[WebSocket] = set()
        self.orchestrator: Any = None
        self.orchestrator_task: Optional[asyncio.Task] = None
        self.start_timestamp: Optional[datetime] = None
        self.finish_timestamp: Optional[datetime] = None
        self.current_urls_count: int = 0
        self.target_duration_hours: float = 1.0
        self.completed_sessions: List[Dict[str, Any]] = []

        # Métricas agregadas
        self.metrics_summary: Dict[str, Any] = {
            "total_watch_seconds": 0.0,
            "total_sessions": 0,
            "successful_sessions": 0,
            "blocked_sessions": 0,
            "failed_sessions": 0,
            "total_ads_skipped": 0,
            "total_continue_clicked": 0,
        }

        self._lock = asyncio.Lock()
        self._log_handler_attached = False

    @classmethod
    def get_instance(cls) -> StateManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def attach_logger(self) -> None:
        if not self._log_handler_attached:
            handler = WebSocketLogHandler(self)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            logging.getLogger("bot").addHandler(handler)
            self._log_handler_attached = True

    async def register_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        # Envia estado inicial completo para o novo cliente
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "data": self.get_full_state()
        })

    def remove_connection(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    def _safe_create_task(self, coro: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            if hasattr(coro, "close"):
                coro.close()

    def append_log(self, log_msg: str) -> None:
        self.recent_logs.append(log_msg)
        self._safe_create_task(self._broadcast({
            "type": "LOG_ENTRY",
            "data": log_msg
        }))

    def start_run(self, num_workers: int, urls_count: int = 0, target_duration_hours: float = 1.0) -> None:
        """Inicializa um novo ciclo de rodada resetando métricas e histórico de sessões."""
        self.init_workers(num_workers)
        self.is_running = True
        self.start_timestamp = datetime.now()
        self.finish_timestamp = None
        self.current_urls_count = urls_count
        self.target_duration_hours = target_duration_hours
        self.completed_sessions = []
        self.metrics_summary = {
            "total_watch_seconds": 0.0,
            "total_sessions": 0,
            "successful_sessions": 0,
            "blocked_sessions": 0,
            "failed_sessions": 0,
            "total_ads_skipped": 0,
            "total_continue_clicked": 0,
        }

    def init_workers(self, num_workers: int) -> None:
        self.workers.clear()
        for i in range(1, num_workers + 1):
            self.workers[i] = WorkerState(worker_id=i, status="Aguardando")

    def update_worker(
        self,
        worker_id: int,
        status: Optional[str] = None,
        current_url: Optional[str] = None,
        current_watch_time: Optional[float] = None,
        target_watch_time: Optional[float] = None,
        gpu_info: Optional[str] = None,
        proxy_info: Optional[str] = None,
        ads_skipped: Optional[int] = None,
        continue_clicked: Optional[int] = None,
    ) -> None:
        if worker_id not in self.workers:
            self.workers[worker_id] = WorkerState(worker_id=worker_id)

        w = self.workers[worker_id]
        if status is not None:
            w.status = status
        if current_url is not None:
            w.current_url = current_url
        if current_watch_time is not None:
            w.current_watch_time = round(current_watch_time, 1)
        if target_watch_time is not None:
            w.target_watch_time = round(target_watch_time, 1)
        if gpu_info is not None:
            w.gpu_info = gpu_info
        if proxy_info is not None:
            w.proxy_info = proxy_info
        if ads_skipped is not None:
            w.ads_skipped = ads_skipped
        if continue_clicked is not None:
            w.continue_clicked = continue_clicked


        if w.target_watch_time > 0:
            w.progress_pct = min(100.0, round((w.current_watch_time / w.target_watch_time) * 100, 1))

        w.last_update = datetime.now().strftime("%H:%M:%S")

        self._safe_create_task(self._broadcast({
            "type": "WORKER_UPDATE",
            "data": w.to_dict()
        }))

    def update_metrics(self, session_metric: Any) -> None:
        status = getattr(session_metric, "status", "FAILED")
        self.metrics_summary["total_sessions"] += 1
        if status == "SUCCESS":
            self.metrics_summary["successful_sessions"] += 1
        elif status == "BLOCKED":
            self.metrics_summary["blocked_sessions"] = self.metrics_summary.get("blocked_sessions", 0) + 1
        else:
            self.metrics_summary["failed_sessions"] += 1

        self.metrics_summary["total_watch_seconds"] += getattr(session_metric, "actual_watch_time", 0.0)
        self.metrics_summary["total_ads_skipped"] += getattr(session_metric, "ads_skipped", 0)
        self.metrics_summary["total_continue_clicked"] += getattr(session_metric, "continue_dialogs_clicked", 0)

        # Guarda sessão individual para persistência ao final da rodada
        s_data = {
            "session_id": getattr(session_metric, "session_id", None),
            "worker_id": getattr(session_metric, "worker_id", None),
            "url": getattr(session_metric, "url", ""),
            "target_watch_time": getattr(session_metric, "target_watch_time", 0.0),
            "actual_watch_time": getattr(session_metric, "actual_watch_time", 0.0),
            "ads_skipped": getattr(session_metric, "ads_skipped", 0),
            "continue_clicked": getattr(session_metric, "continue_dialogs_clicked", 0),
            "status": status,
            "error_message": getattr(session_metric, "error_message", None),
            "started_at": getattr(session_metric, "started_at", None),
            "finished_at": getattr(session_metric, "finished_at", None),
        }
        self.completed_sessions.append(s_data)

        self._safe_create_task(self._broadcast({
            "type": "METRICS_UPDATE",
            "data": self.metrics_summary
        }))

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        if not self.active_connections:
            return
        dead = []
        for ws in list(self.active_connections):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections.discard(ws)

    def finish_run(self, reason: str = "Rodada finalizada.") -> None:
        self.is_running = False
        self.finish_timestamp = datetime.now()

        # Persistência automática no SQLite se houve execução ativa
        if self.start_timestamp:
            try:
                from src.utils.db import DatabaseManager
                delta_sec = (self.finish_timestamp - self.start_timestamp).total_seconds()
                reason_lower = reason.lower()
                run_status = "CANCELLED" if ("cancelad" in reason_lower or "interrompid" in reason_lower) else "COMPLETED"
                run_data = {
                    "started_at": self.start_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "finished_at": self.finish_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": round(delta_sec, 1),
                    "target_watch_time": round(self.target_duration_hours * 3600.0, 1),
                    "actual_watch_time": round(self.metrics_summary["total_watch_seconds"], 1),
                    "total_views": self.metrics_summary["total_sessions"],
                    "successful_views": self.metrics_summary["successful_sessions"],
                    "blocked_views": self.metrics_summary.get("blocked_sessions", 0),
                    "failed_views": self.metrics_summary["failed_sessions"],
                    "ads_skipped": self.metrics_summary["total_ads_skipped"],
                    "continue_clicked": self.metrics_summary["total_continue_clicked"],
                    "workers": len(self.workers),
                    "urls_count": self.current_urls_count,
                    "status": run_status,
                    "summary_message": reason,
                }
                DatabaseManager.get_instance().save_run(run_data, self.completed_sessions)
            except Exception as e:
                logging.getLogger("bot").warning(f"Erro ao persistir histórico no SQLite: {e}")

        self.orchestrator = None
        self.orchestrator_task = None
        self.append_log(f"🏁 {reason}")
        for w in self.workers.values():
            w.status = "Finalizado"
            self._safe_create_task(self._broadcast({
                "type": "WORKER_UPDATE",
                "data": w.to_dict()
            }))
        self._safe_create_task(self._broadcast({
            "type": "INITIAL_STATE",
            "data": self.get_full_state()
        }))

    def get_full_state(self) -> Dict[str, Any]:
        elapsed_str = "00:00:00"
        if self.start_timestamp:
            end_time = datetime.now() if self.is_running else (self.finish_timestamp or datetime.now())
            delta = end_time - self.start_timestamp
            total_sec = max(0, int(delta.total_seconds()))
            hours, rem = divmod(total_sec, 3600)
            minutes, seconds = divmod(rem, 60)
            elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return {
            "is_running": self.is_running,
            "elapsed_time": elapsed_str,
            "workers": [w.to_dict() for w in self.workers.values()],
            "metrics": self.metrics_summary,
            "recent_logs": list(self.recent_logs),
        }
