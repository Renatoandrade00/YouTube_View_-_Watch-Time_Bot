from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import BotConfig
from src.orchestrator import BotOrchestrator
from src.utils.logger import MetricsTracker
from src.web.state import StateManager

logger = logging.getLogger("bot")

app = FastAPI(
    title="YouTube View & Watch-Time Bot - Dashboard",
    description="Painel de controle visual e monitoramento em tempo real do bot",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

logging.getLogger("bot").setLevel(logging.INFO)

state_manager = StateManager.get_instance()
state_manager.attach_logger()


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

class StartBotRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, description="Lista de URLs de vídeos do YouTube")
    workers: int = Field(default=5, ge=1, le=30)
    duration_hours: Optional[float] = Field(default=1.0, ge=0.01, le=24.0)
    continuous: bool = Field(default=True)
    min_watch_minutes: Optional[float] = Field(default=None)
    max_watch_minutes: Optional[float] = Field(default=None)
    min_watch: Optional[float] = Field(default=None)
    max_watch: Optional[float] = Field(default=None)
    min_delay: float = Field(default=5.0, ge=1.0)
    max_delay: float = Field(default=15.0, ge=1.0)
    stagger_delay: float = Field(default=15.0, ge=0.0, le=120.0, description="Intervalo entre workers em segundos")
    headless: bool = Field(default=True)
    mute: bool = Field(default=True)
    anti_fingerprint: bool = Field(default=True)
    micro_interactions: bool = Field(default=True)
    skip_ads: bool = Field(default=True)
    auto_continue: bool = Field(default=True)


@app.get("/")
async def get_index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html não encontrado")
    return FileResponse(index_path)


@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    return state_manager.get_full_state()


@app.get("/api/default-urls")
async def get_default_urls() -> Dict[str, Any]:
    urls_file = Path("urls.txt")
    loaded_urls: List[str] = []
    if urls_file.exists():
        loaded_urls = [line.strip() for line in urls_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    return {"urls": loaded_urls}


async def _run_bot_task(config: BotConfig, orchestrator: BotOrchestrator) -> None:
    try:
        await orchestrator.run()
    except asyncio.CancelledError:
        logger.info("Execução do Bot interrompida com sucesso.")
    except Exception as e:
        logger.error(f"Erro inesperado durante a orquestração: {e}")
    finally:
        state_manager.finish_run("Duração Total da Rodada concluída. Todos os workers foram encerrados.")


@app.post("/api/start")
async def start_bot(req: StartBotRequest) -> Dict[str, Any]:
    if state_manager.is_running:
        raise HTTPException(status_code=400, detail="Uma execução já está em andamento!")

    cleaned_urls = [u.strip() for u in req.urls if u.strip().startswith("http")]
    if not cleaned_urls:
        raise HTTPException(status_code=400, detail="Nenhuma URL válida fornecida.")

    # O valor na tela é SEMPRE interpretado como MINUTOS
    if req.min_watch_minutes is not None:
        min_minutes = float(req.min_watch_minutes)
    elif req.min_watch is not None:
        min_minutes = float(req.min_watch)
    else:
        min_minutes = 1.0

    if req.max_watch_minutes is not None:
        max_minutes = float(req.max_watch_minutes)
    elif req.max_watch is not None:
        max_minutes = float(req.max_watch)
    else:
        max_minutes = 3.0

    if min_minutes > max_minutes:
        raise HTTPException(status_code=400, detail="O tempo mínimo não pode ser maior que o máximo.")

    # Converte minutos para segundos
    min_watch_sec = max(5, int(round(min_minutes * 60)))
    max_watch_sec = max(min_watch_sec, int(round(max_minutes * 60)))

    config = BotConfig(
        urls_list=cleaned_urls,
        target_url=cleaned_urls[0] if len(cleaned_urls) == 1 else None,
        workers=req.workers,
        max_runtime_hours=req.duration_hours,
        continuous=req.continuous,
        min_watch=min_watch_sec,
        max_watch=max_watch_sec,
        min_delay_between_videos=req.min_delay,
        max_delay_between_videos=req.max_delay,
        worker_stagger_delay=req.stagger_delay,
        headless=req.headless,
        mute_audio=req.mute,
        enable_anti_fingerprint=req.anti_fingerprint,
        enable_micro_interactions=req.micro_interactions,
        skip_ads=req.skip_ads,
        auto_continue=req.auto_continue,
    )

    tracker = MetricsTracker()
    orchestrator = BotOrchestrator(config=config, tracker=tracker)

    state_manager.init_workers(req.workers)
    state_manager.is_running = True
    state_manager.start_timestamp = datetime.now()
    state_manager.orchestrator = orchestrator
    state_manager.append_log(
        f"🚀 Inicializando Dashboard com {req.workers} workers, "
        f"{len(cleaned_urls)} vídeos, escalonamento de {req.stagger_delay}s e duração de {req.duration_hours}h."
    )

    task = asyncio.create_task(_run_bot_task(config, orchestrator))
    state_manager.orchestrator_task = task

    return {
        "status": "started",
        "workers": req.workers,
        "urls_count": len(cleaned_urls),
        "duration_hours": req.duration_hours
    }


@app.post("/api/stop")
async def stop_bot() -> Dict[str, Any]:
    if not state_manager.is_running:
        return {"status": "not_running", "message": "Nenhuma execução ativa no momento."}

    state_manager.append_log("🛑 Solicitando parada imediata de todos os workers...")
    if state_manager.orchestrator:
        state_manager.orchestrator.stop()

    if state_manager.orchestrator_task and not state_manager.orchestrator_task.done():
        state_manager.orchestrator_task.cancel()

    state_manager.finish_run("Execução cancelada pelo usuário.")
    return {"status": "stopping", "message": "Parada solicitada com sucesso."}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await state_manager.register_connection(websocket)
    try:
        while True:
            # Recebe mensagens opcionais do cliente como ping/pong ou comandos
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        state_manager.remove_connection(websocket)
    except Exception:
        state_manager.remove_connection(websocket)
