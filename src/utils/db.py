from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bot")

DEFAULT_DB_PATH = Path("bot_history.db")


class DatabaseManager:
    """Gerenciador de persistência local SQLite para histórico de execuções do bot."""

    _instance: Optional[DatabaseManager] = None

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: Optional[Path | str] = None) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        elif db_path is not None and cls._instance.db_path != Path(db_path):
            cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        """Cria as tabelas caso não existam."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_seconds REAL DEFAULT 0.0,
                    target_watch_time REAL DEFAULT 0.0,
                    actual_watch_time REAL DEFAULT 0.0,
                    total_views INTEGER DEFAULT 0,
                    successful_views INTEGER DEFAULT 0,
                    blocked_views INTEGER DEFAULT 0,
                    failed_views INTEGER DEFAULT 0,
                    ads_skipped INTEGER DEFAULT 0,
                    continue_clicked INTEGER DEFAULT 0,
                    workers INTEGER DEFAULT 1,
                    urls_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'COMPLETED',
                    summary_message TEXT DEFAULT ''
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    session_id INTEGER,
                    worker_id INTEGER,
                    url TEXT,
                    target_watch_time REAL DEFAULT 0.0,
                    actual_watch_time REAL DEFAULT 0.0,
                    ads_skipped INTEGER DEFAULT 0,
                    continue_clicked INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'SUCCESS',
                    error_message TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_sessions_run_id ON run_sessions(run_id);")
            conn.commit()

    def save_run(self, run_data: Dict[str, Any], sessions: Optional[List[Dict[str, Any]]] = None) -> int:
        """Salva uma rodada finalizada e suas sessões filhas no banco SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO runs (
                    started_at, finished_at, duration_seconds, target_watch_time,
                    actual_watch_time, total_views, successful_views, blocked_views,
                    failed_views, ads_skipped, continue_clicked, workers, urls_count,
                    status, summary_message
                ) VALUES (
                    :started_at, :finished_at, :duration_seconds, :target_watch_time,
                    :actual_watch_time, :total_views, :successful_views, :blocked_views,
                    :failed_views, :ads_skipped, :continue_clicked, :workers, :urls_count,
                    :status, :summary_message
                );
                """,
                {
                    "started_at": run_data.get("started_at"),
                    "finished_at": run_data.get("finished_at"),
                    "duration_seconds": float(run_data.get("duration_seconds", 0.0)),
                    "target_watch_time": float(run_data.get("target_watch_time", 0.0)),
                    "actual_watch_time": float(run_data.get("actual_watch_time", 0.0)),
                    "total_views": int(run_data.get("total_views", 0)),
                    "successful_views": int(run_data.get("successful_views", 0)),
                    "blocked_views": int(run_data.get("blocked_views", 0)),
                    "failed_views": int(run_data.get("failed_views", 0)),
                    "ads_skipped": int(run_data.get("ads_skipped", 0)),
                    "continue_clicked": int(run_data.get("continue_clicked", 0)),
                    "workers": int(run_data.get("workers", 1)),
                    "urls_count": int(run_data.get("urls_count", 0)),
                    "status": run_data.get("status", "COMPLETED"),
                    "summary_message": run_data.get("summary_message", ""),
                },
            )
            run_id = cursor.lastrowid

            if sessions:
                session_records = [
                    (
                        run_id,
                        s.get("session_id"),
                        s.get("worker_id"),
                        s.get("url"),
                        float(s.get("target_watch_time", 0.0)),
                        float(s.get("actual_watch_time", 0.0)),
                        int(s.get("ads_skipped", 0)),
                        int(s.get("continue_clicked", s.get("continue_dialogs_clicked", 0))),
                        s.get("status", "SUCCESS"),
                        s.get("error_message"),
                        s.get("started_at"),
                        s.get("finished_at"),
                    )
                    for s in sessions
                ]
                cursor.executemany(
                    """
                    INSERT INTO run_sessions (
                        run_id, session_id, worker_id, url, target_watch_time,
                        actual_watch_time, ads_skipped, continue_clicked, status,
                        error_message, started_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    session_records,
                )

            conn.commit()
            logger.info(f"💾 Rodada #{run_id} persistida com sucesso no banco de dados com {len(sessions or [])} sessões.")
            return run_id

    def get_all_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retorna histórico de rodadas paginado em ordem decrescente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM runs
                ORDER BY id DESC
                LIMIT ? OFFSET ?;
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_run_details(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Retorna detalhes de uma rodada específica e todas as sessões registradas nela."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE id = ?;", (run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                return None

            cursor.execute(
                """
                SELECT * FROM run_sessions
                WHERE run_id = ?
                ORDER BY id ASC;
                """,
                (run_id,),
            )
            sessions = [dict(s) for s in cursor.fetchall()]

            run_dict = dict(run_row)
            run_dict["sessions"] = sessions
            return run_dict

    def get_run_summary_stats(self) -> Dict[str, Any]:
        """Calcula métricas globais agregadas de todas as rodadas armazenadas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(id) AS total_runs,
                    COALESCE(SUM(actual_watch_time), 0.0) AS total_watch_seconds,
                    COALESCE(SUM(total_views), 0) AS total_views,
                    COALESCE(SUM(successful_views), 0) AS successful_views,
                    COALESCE(SUM(blocked_views), 0) AS blocked_views,
                    COALESCE(SUM(failed_views), 0) AS failed_views,
                    COALESCE(SUM(ads_skipped), 0) AS total_ads_skipped,
                    COALESCE(SUM(continue_clicked), 0) AS total_continue_clicked
                FROM runs;
                """
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "total_runs": 0,
                    "total_watch_hours": 0.0,
                    "total_views": 0,
                    "successful_views": 0,
                    "blocked_views": 0,
                    "failed_views": 0,
                    "success_rate": 100.0,
                    "total_ads_skipped": 0,
                    "total_continue_clicked": 0,
                }

            data = dict(row)
            tot_views = data["total_views"]
            succ_views = data["successful_views"]
            success_rate = round((succ_views / tot_views * 100.0), 1) if tot_views > 0 else 100.0
            watch_hours = round(data["total_watch_seconds"] / 3600.0, 2)

            return {
                "total_runs": data["total_runs"],
                "total_watch_hours": watch_hours,
                "total_views": tot_views,
                "successful_views": succ_views,
                "blocked_views": data["blocked_views"],
                "failed_views": data["failed_views"],
                "success_rate": success_rate,
                "total_ads_skipped": data["total_ads_skipped"],
                "total_continue_clicked": data["total_continue_clicked"],
            }

    def delete_run(self, run_id: int) -> bool:
        """Exclui uma rodada e todas as suas sessões associadas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runs WHERE id = ?;", (run_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_history(self) -> int:
        """Limpa todo o histórico de execuções."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runs;")
            deleted = cursor.rowcount
            conn.commit()
            return deleted
