from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from rich.console import Console
from rich.panel import Panel

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from src.config import load_config
from src.orchestrator import BotOrchestrator
from src.utils.logger import MetricsTracker, setup_logger

console = Console(safe_box=True)


def print_legal_disclaimer() -> None:
    """Exibe em destaque o aviso legal e de responsabilidade exigido pelo PRD."""
    disclaimer_text = (
        "[bold yellow]AVISO LEGAL E DE RISCO (EDUCATIONAL PURPOSES ONLY):[/bold yellow]\n\n"
        "O uso de bots para inflar artificialmente visualizações, watch time ou engajamento "
        "viola as diretrizes e os Termos de Serviço do YouTube.\n"
        "Este software foi criado exclusivamente para fins didáticos, testes de carga locais e estudos de automação.\n"
        "[bold red]O usuário é integralmente responsável pelo uso desta ferramenta.[/bold red]"
    )
    console.print(Panel(disclaimer_text, title="⚠️ TERMOS DE USO", border_style="yellow"))


def build_arg_parser() -> argparse.ArgumentParser:
    """Configura o analisador de argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="YouTube View & Watch-Time Bot - Automação educacional com Playwright",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--url", type=str, default=None, help="URL do vídeo do YouTube alvo")
    parser.add_argument("--urls-file", type=str, default=None, help="Caminho para arquivo com lista de URLs")
    parser.add_argument("--workers", type=int, default=None, help="Quantidade de workers simultâneos (padrão: 2)")
    parser.add_argument("--total-views", type=int, default=None, help="Total de visualizações a executar")
    parser.add_argument("--min-watch", type=int, default=None, help="Tempo mínimo de exibição por sessão em segundos")
    parser.add_argument("--max-watch", type=int, default=None, help="Tempo máximo de exibição por sessão em segundos")

    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=None,
        help="Executar navegadores em modo headless (sem janela)",
    )
    parser.add_argument(
        "--headful",
        dest="headless",
        action="store_false",
        help="Executar navegadores em modo visível",
    )

    parser.add_argument(
        "--mute",
        dest="mute_audio",
        action="store_true",
        default=None,
        help="Silenciar áudio do vídeo",
    )
    parser.add_argument(
        "--unmute",
        dest="mute_audio",
        action="store_false",
        help="Permitir áudio do vídeo",
    )

    parser.add_argument("--config", type=str, default="config.yaml", help="Caminho para arquivo YAML de configuração")
    return parser


async def main_async() -> None:
    """Ponto de entrada assíncrono do bot."""
    parser = build_arg_parser()
    args = parser.parse_args()

    print_legal_disclaimer()

    cli_overrides = {
        "target_url": args.url,
        "urls_file": args.urls_file,
        "workers": args.workers,
        "total_views": args.total_views,
        "min_watch": args.min_watch,
        "max_watch": args.max_watch,
        "headless": args.headless,
        "mute_audio": args.mute_audio,
    }

    try:
        config = load_config(yaml_path=args.config, cli_overrides=cli_overrides)
    except Exception as e:
        console.print(f"[bold red]Erro ao carregar configurações:[/bold red] {e}")
        sys.exit(1)

    logger = setup_logger(config.log_level)
    tracker = MetricsTracker(logs_dir=config.logs_dir, save_logs=config.save_session_logs)
    orchestrator = BotOrchestrator(config=config, tracker=tracker)

    # Configuração de captura de sinais no Windows e Unix
    def signal_handler(*_):
        orchestrator.stop()

    if sys.platform == "win32":
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                signal.signal(sig, signal_handler)

    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.warning("Interrupção via teclado.")
    finally:
        tracker.print_summary()


def main() -> None:
    """Wrapper síncrono para execução do script."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
