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

        # Métricas agregadas
        self.metrics_summary: Dict[str, Any] = {
            "total_watch_seconds": 0.0,
            "total_sessions": 0,
            "successful_sessions": 0,
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
        self.metrics_summary["total_sessions"] += 1
        if getattr(session_metric, "status", "") == "SUCCESS":
            self.metrics_summary["successful_sessions"] += 1
        else:
            self.metrics_summary["failed_sessions"] += 1

        self.metrics_summary["total_watch_seconds"] += getattr(session_metric, "actual_watch_time", 0.0)
        self.metrics_summary["total_ads_skipped"] += getattr(session_metric, "ads_skipped", 0)
        self.metrics_summary["total_continue_clicked"] += getattr(session_metric, "continue_dialogs_clicked", 0)

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

    def get_full_state(self) -> Dict[str, Any]:
        elapsed_str = "00:00:00"
        if self.is_running and self.start_timestamp:
            delta = datetime.now() - self.start_timestamp
            total_sec = int(delta.total_seconds())
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
