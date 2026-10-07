from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import sys
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

console = Console(safe_box=True)


@dataclass
class SessionMetric:
    """Métricas registradas para uma sessão de visualização."""
    session_id: int
    worker_id: int
    url: str
    target_watch_time: int
    actual_watch_time: float
    ads_skipped: int
    continue_dialogs_clicked: int
    status: str  # "SUCCESS", "FAILED", "INTERRUPTED"
    error_message: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""


class MetricsTracker:
    """Gerenciador central de métricas e relatório de execução."""

    def __init__(self, logs_dir: str = "logs", save_logs: bool = True):
        self.logs_dir = Path(logs_dir)
        self.save_logs = save_logs
        self.sessions: List[SessionMetric] = []

        if self.save_logs:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file = self.logs_dir / f"session_metrics_{timestamp}.jsonl"
        else:
            self.log_file = None

    def record_session(self, metric: SessionMetric) -> None:
        """Registra métrica de uma sessão e persiste no JSONL."""
        self.sessions.append(metric)
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(metric), ensure_ascii=False) + "\n")
            except Exception as e:
                logging.getLogger("bot").warning(f"Falha ao salvar métrica no arquivo: {e}")

    def print_summary(self) -> None:
        """Exibe resumo visual das sessões executadas no console."""
        total = len(self.sessions)
        if total == 0:
            console.print("[yellow]Nenhuma sessão foi finalizada.[/yellow]")
            return

        successes = sum(1 for s in self.sessions if s.status == "SUCCESS")
        failures = sum(1 for s in self.sessions if s.status == "FAILED")
        interrupted = sum(1 for s in self.sessions if s.status == "INTERRUPTED")
        total_watch_seconds = sum(s.actual_watch_time for s in self.sessions)
        total_ads = sum(s.ads_skipped for s in self.sessions)
        total_dialogs = sum(s.continue_dialogs_clicked for s in self.sessions)

        table = Table(title="📊 Resumo Geral da Execução", header_style="bold cyan")
        table.add_column("Métrica", style="bold")
        table.add_column("Valor", justify="right")

        table.add_row("Total de Sessões", str(total))
        table.add_row("Sessões Bem-sucedidas", f"[green]{successes}[/green]")
        table.add_row("Falhas", f"[red]{failures}[/red]" if failures else "0")
        table.add_row("Interrompidas", f"[yellow]{interrupted}[/yellow]" if interrupted else "0")
        table.add_row("Tempo Total Assistido", f"{total_watch_seconds:.1f} s ({total_watch_seconds / 60:.1f} min)")
        table.add_row("Anúncios Pulados", str(total_ads))
        table.add_row("Diálogos 'Continuar' Clicados", str(total_dialogs))

        console.print("\n")
        console.print(table)


def setup_logger(log_level: str = "INFO") -> logging.Logger:
    """Configura e retorna o logger principal da aplicação."""
    logger = logging.getLogger("bot")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Evita adicionar múltiplos handlers se já configurado
    if not logger.handlers:
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_time=True,
            show_path=False,
            markup=True
        )
        formatter = logging.Formatter("%(message)s", datefmt="[%X]")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
