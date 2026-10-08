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

    parser.add_argument("--duration-hours", type=float, default=None, help="Tempo máximo total de execução em horas (ex: 6.0)")
    parser.add_argument("--continuous", action="store_true", default=None, help="Executar continuamente sem limite fixo de sessões")

    parser.add_argument(
        "--no-stealth",
        dest="enable_anti_fingerprint",
        action="store_false",
        default=None,
        help="Desativar perfis anti-fingerprint (Canvas, WebGL, Audio)",
    )
    parser.add_argument(
        "--no-interactions",
        dest="enable_micro_interactions",
        action="store_false",
        default=None,
        help="Desativar micro-interações humanas (mouse jitter, hover, scroll)",
    )
    parser.add_argument("--min-delay", type=float, default=None, help="Pausa mínima entre vídeos da lista em segundos (padrão: 5.0)")
    parser.add_argument("--max-delay", type=float, default=None, help="Pausa máxima entre vídeos da lista em segundos (padrão: 15.0)")

    # Argumentos do Modo Visual Web
    parser.add_argument("--web", "--gui", dest="web_mode", action="store_true", default=False, help="Iniciar painel de controle visual no navegador")
    parser.add_argument("--port", type=int, default=8000, help="Porta para o servidor web (padrão: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host para o servidor web (padrão: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", default=False, help="Não abrir o navegador automaticamente ao iniciar o modo web")

    parser.add_argument("--config", type=str, default="config.yaml", help="Caminho para arquivo YAML de configuração")
    return parser


async def main_async() -> None:
    """Ponto de entrada assíncrono do bot."""
    parser = build_arg_parser()
    args = parser.parse_args()

    print_legal_disclaimer()

    if args.web_mode:
        import threading
        import time
        import webbrowser
        import uvicorn

        web_url = f"http://{args.host}:{args.port}"
        console.print(f"\n[bold green]🌐 Iniciando Painel Visual Web em:[/bold green] [bold cyan]{web_url}[/bold cyan]")
        console.print("[dim]Pressione CTRL+C no terminal para encerrar o servidor web.[/dim]\n")

        if not args.no_browser:
            def _open_browser():
                time.sleep(1.2)
                webbrowser.open(web_url)
            threading.Thread(target=_open_browser, daemon=True).start()

        uvicorn_config = uvicorn.Config("src.web.app:app", host=args.host, port=args.port, log_level="warning")
        server = uvicorn.Server(uvicorn_config)
        await server.serve()
        return

    cli_overrides = {
        "target_url": args.url,
        "urls_file": args.urls_file,
        "workers": args.workers,
        "total_views": args.total_views,
        "min_watch": args.min_watch,
        "max_watch": args.max_watch,
        "headless": args.headless,
        "mute_audio": args.mute_audio,
        "max_runtime_hours": args.duration_hours,
        "continuous": args.continuous,
        "enable_anti_fingerprint": args.enable_anti_fingerprint,
        "enable_micro_interactions": args.enable_micro_interactions,
        "min_delay_between_videos": args.min_delay,
        "max_delay_between_videos": args.max_delay,
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
