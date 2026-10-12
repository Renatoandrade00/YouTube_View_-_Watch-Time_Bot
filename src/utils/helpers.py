from __future__ import annotations

import asyncio
import random
from typing import Tuple

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
]


def get_random_user_agent() -> str:
    """Retorna um User-Agent moderno aleatório."""
    return random.choice(USER_AGENTS)


def get_random_viewport() -> dict:
    """Retorna uma resolução comum de viewport aleatória."""
    return random.choice(VIEWPORTS)


async def random_async_sleep(min_seconds: float, max_seconds: float) -> float:
    """Aguarda um intervalo de tempo aleatório de forma assíncrona."""
    if min_seconds > max_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
    return delay


def normalize_youtube_url(url: str) -> str:
    """Normaliza links curtos ou variações de URLs do YouTube, isolando o ID do vídeo."""
    url = url.strip()
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
    if "watch?v=" in url:
        video_id = url.split("watch?v=")[1].split("&")[0]
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def parse_playwright_proxy(proxy_str: str) -> dict | None:
    """
    Analisa e formata uma string de proxy para o formato esperado pelo Playwright:
    dict(server="...", username="...", password="...")
    Suporta:
    - protocolo://usuario:senha@host:porta
    - usuario:senha@host:porta
    - protocolo://host:porta
    - host:porta
    """
    if not proxy_str or not proxy_str.strip():
        return None

    proxy_str = proxy_str.strip()
    from urllib.parse import urlsplit

    # Se não tiver protocolo, assume http://
    if "://" not in proxy_str:
        proxy_str = f"http://{proxy_str}"

    try:
        parsed = urlsplit(proxy_str)
        scheme = parsed.scheme.lower() if parsed.scheme else "http"
        host = parsed.hostname
        port = parsed.port

        if not host or not port:
            return None

        server = f"{scheme}://{host}:{port}"
        result: dict = {"server": server}

        if parsed.username:
            result["username"] = parsed.username
        if parsed.password:
            result["password"] = parsed.password

        return result
    except Exception:
        return None


def format_proxy_display(proxy_str: str) -> str:
    """Retorna uma representação limpa do proxy mascarando a senha para exibição segura."""
    if not proxy_str or not proxy_str.strip():
        return "Conexão Direta (Local)"

    parsed = parse_playwright_proxy(proxy_str)
    if not parsed:
        return "Proxy Inválido"

    server = parsed.get("server", "")
    username = parsed.get("username")
    if username:
        # Exibe protocolo://usuario:***@host:porta
        proto, rest = server.split("://", 1) if "://" in server else ("http", server)
        return f"{proto}://{username}:***@{rest}"
    return server


def rotate_proxy_session(proxy_str: str, worker_id: int) -> str:
    """
    Substitui ou injeta um ID de sessão único e aleatório no proxy para forçar o provedor
    (DataImpulse, Smartproxy, BrightData, etc.) a entregar imediatamente um novo IP residencial.
    """
    if not proxy_str or not proxy_str.strip():
        return proxy_str

    import re
    import uuid
    rand_token = uuid.uuid4().hex[:8]

    # 1. Padrão DataImpulse / Provedores com sessid: sessid.VALOR
    if re.search(r"sessid\.[a-zA-Z0-9_\-]+", proxy_str):
        new_sess = f"sessid.w{worker_id}_{rand_token}"
        return re.sub(r"sessid\.[a-zA-Z0-9_\-]+", new_sess, proxy_str)

    # 2. Padrão com session-VALOR:
    if re.search(r"session-[a-zA-Z0-9_\-]+", proxy_str):
        new_sess = f"session-w{worker_id}_{rand_token}"
        return re.sub(r"session-[a-zA-Z0-9_\-]+", new_sess, proxy_str)

    # 3. Padrão sem sessão no usuário, mas com credenciais (adiciona __sessid)
    from urllib.parse import urlsplit, urlunsplit
    try:
        parsed = urlsplit(proxy_str)
        if parsed.username:
            new_username = f"{parsed.username}__sessid.w{worker_id}_{rand_token}"
            user_info = f"{new_username}:{parsed.password}" if parsed.password else new_username
            netloc = f"{user_info}@{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
            return urlunsplit((parsed.scheme or "http", netloc, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        pass

    return proxy_str


