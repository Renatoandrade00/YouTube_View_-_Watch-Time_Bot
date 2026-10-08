from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List
import yaml
from pydantic import BaseModel, Field, field_validator


class BotConfig(BaseModel):
    """Configurações centrais do YouTube View & Watch-Time Bot."""

    target_url: Optional[str] = Field(default=None, description="URL do vídeo do YouTube alvo")
    urls_file: Optional[str] = Field(default=None, description="Caminho para arquivo com lista de URLs")
    urls_list: List[str] = Field(default_factory=list, description="Lista carregada de URLs")

    workers: int = Field(default=2, ge=1, le=20, description="Quantidade de workers simultâneos")
    total_views: int = Field(default=10, ge=1, description="Total de sessões de visualização a realizar")

    min_watch: int = Field(default=45, ge=10, description="Tempo mínimo de exibição por sessão em segundos")
    max_watch: int = Field(default=120, ge=10, description="Tempo máximo de exibição por sessão em segundos")

    headless: bool = Field(default=False, description="Executar navegadores sem interface gráfica visível")
    mute_audio: bool = Field(default=True, description="Silenciar o áudio dos vídeos para poupar recursos")

    poll_interval: float = Field(default=5.0, ge=1.0, description="Intervalo de verificação de botões/diálogos em segundos")
    skip_ads: bool = Field(default=True, description="Tentar pular anúncios automaticamente")
    auto_continue: bool = Field(default=True, description="Clicar automaticamente em 'Continuar assistindo'")

    log_level: str = Field(default="INFO", description="Nível de log (DEBUG, INFO, WARNING, ERROR)")
    save_session_logs: bool = Field(default=True, description="Salvar logs de cada sessão em arquivo JSONL")
    logs_dir: str = Field(default="logs", description="Diretório de saída para arquivos de log")

    max_runtime_hours: Optional[float] = Field(default=None, description="Tempo máximo total de execução do bot em horas")
    continuous: bool = Field(default=False, description="Modo contínuo sem limite fixo de sessões")

    enable_anti_fingerprint: bool = Field(default=True, description="Ativar injeção de perfis anti-fingerprint (Canvas, WebGL, Audio)")
    enable_micro_interactions: bool = Field(default=True, description="Ativar micro-interações humanas (mouse, scroll, hover)")
    min_delay_between_videos: float = Field(default=5.0, ge=1.0, description="Pausa mínima entre vídeos em segundos")
    max_delay_between_videos: float = Field(default=15.0, ge=1.0, description="Pausa máxima entre vídeos em segundos")

    @field_validator("max_watch")
    @classmethod
    def validate_watch_range(cls, v: int, info) -> int:
        min_w = info.data.get("min_watch")
        if min_w is not None and v < min_w:
            raise ValueError(f"max_watch ({v}s) não pode ser menor que min_watch ({min_w}s)")
        return v

    def resolve_urls(self) -> List[str]:
        """Retorna lista consolidada de URLs a partir de target_url ou urls_file."""
        urls: List[str] = []
        if self.target_url:
            cleaned = self.target_url.strip()
            if cleaned:
                urls.append(cleaned)

        if self.urls_file:
            path = Path(self.urls_file)
            if path.exists() and path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#"):
                        urls.append(cleaned)

        self.urls_list = urls
        return urls


def load_config(
    yaml_path: Optional[str] = None,
    cli_overrides: Optional[dict] = None
) -> BotConfig:
    """Carrega configuração combinando variáveis de ambiente, arquivo YAML e parâmetros CLI."""
    data: dict = {}

    # 1. Carrega do arquivo YAML se existir ou se foi passado
    target_yaml = Path(yaml_path) if yaml_path else Path("config.yaml")
    if target_yaml.exists():
        try:
            with open(target_yaml, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
                # Mapeia chaves aninhadas comuns do YAML de exemplo
                if "target" in yaml_data:
                    data["target_url"] = yaml_data["target"].get("url")
                    data["urls_file"] = yaml_data["target"].get("urls_file")
                    data["total_views"] = yaml_data["target"].get("total_views", 10)
                if "execution" in yaml_data:
                    data["workers"] = yaml_data["execution"].get("workers", 2)
                    data["min_watch"] = yaml_data["execution"].get("min_watch_seconds", 45)
                    data["max_watch"] = yaml_data["execution"].get("max_watch_seconds", 120)
                    data["headless"] = yaml_data["execution"].get("headless", False)
                    data["mute_audio"] = yaml_data["execution"].get("mute_audio", True)
                if "monitoring" in yaml_data:
                    data["poll_interval"] = yaml_data["monitoring"].get("poll_interval_seconds", 5.0)
                    data["skip_ads"] = yaml_data["monitoring"].get("skip_ads", True)
                    data["auto_continue"] = yaml_data["monitoring"].get("auto_continue", True)
                if "logging" in yaml_data:
                    data["log_level"] = yaml_data["logging"].get("level", "INFO")
                    data["save_session_logs"] = yaml_data["logging"].get("save_session_logs", True)
                    data["logs_dir"] = yaml_data["logging"].get("logs_dir", "logs")
        except Exception:
            pass

    # 2. Carrega de variáveis de ambiente
    env_mappings = {
        "TARGET_URL": ("target_url", str),
        "URLS_FILE": ("urls_file", str),
        "WORKERS": ("workers", int),
        "TOTAL_VIEWS": ("total_views", int),
        "MIN_WATCH": ("min_watch", int),
        "MAX_WATCH": ("max_watch", int),
        "HEADLESS": ("headless", lambda v: v.lower() in ("true", "1", "yes")),
        "MUTE_AUDIO": ("mute_audio", lambda v: v.lower() in ("true", "1", "yes")),
        "POLL_INTERVAL": ("poll_interval", float),
        "LOG_LEVEL": ("log_level", str),
        "SAVE_SESSION_LOGS": ("save_session_logs", lambda v: v.lower() in ("true", "1", "yes")),
        "LOGS_DIR": ("logs_dir", str),
        "MAX_RUNTIME_HOURS": ("max_runtime_hours", float),
        "CONTINUOUS": ("continuous", lambda v: v.lower() in ("true", "1", "yes")),
        "ENABLE_ANTI_FINGERPRINT": ("enable_anti_fingerprint", lambda v: v.lower() in ("true", "1", "yes")),
        "ENABLE_MICRO_INTERACTIONS": ("enable_micro_interactions", lambda v: v.lower() in ("true", "1", "yes")),
        "MIN_DELAY_BETWEEN_VIDEOS": ("min_delay_between_videos", float),
        "MAX_DELAY_BETWEEN_VIDEOS": ("max_delay_between_videos", float),
    }

    for env_var, (field_name, converter) in env_mappings.items():
        val = os.getenv(env_var)
        if val is not None and val != "":
            try:
                data[field_name] = converter(val)
            except Exception:
                pass

    # 3. Aplica overrides vindos da CLI
    if cli_overrides:
        for k, v in cli_overrides.items():
            if v is not None:
                data[k] = v

    config = BotConfig(**data)
    config.resolve_urls()
    return config
