from __future__ import annotations

import asyncio
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple

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


def parse_cookies_file(cookies_path: str | Path, worker_id: Optional[int] = None) -> list[dict]:
    """
    Carrega e formata cookies de um arquivo para o formato aceito pelo Playwright.
    Suporta:
    1. Arquivo de cookies específico para o worker (ex: cookies_worker_1.json ou cookies/worker_1.json).
    2. Formato JSON (Array de cookies ou objeto de storage_state com chave 'cookies').
    3. Formato Netscape (.txt / .cookie com campos separados por tabulação).
    """
    path = Path(cookies_path)

    # 1. Tenta encontrar arquivo específico do worker se aplicável
    if worker_id is not None:
        candidates = [
            path.parent / f"worker_{worker_id}.json",
            path.parent / f"worker_{worker_id}.txt",
            path.parent / f"{path.stem}_worker_{worker_id}{path.suffix}",
        ]
        for cand in candidates:
            if cand.exists() and cand.is_file():
                path = cand
                break

    if not path.exists() or not path.is_file():
        return []

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    cookies = []

    # Tenta interpretar como JSON primeiro
    if content.startswith("[") or content.startswith("{"):
        import json
        try:
            data = json.loads(content)
            raw_list = data if isinstance(data, list) else data.get("cookies", [])
            for item in raw_list:
                if not isinstance(item, dict) or "name" not in item or "value" not in item:
                    continue
                c = {
                    "name": str(item["name"]),
                    "value": str(item["value"]),
                    "domain": item.get("domain", ".youtube.com"),
                    "path": item.get("path", "/"),
                }
                if "expires" in item and item["expires"] is not None:
                    try:
                        c["expires"] = float(item["expires"])
                    except (ValueError, TypeError):
                        pass
                if "httpOnly" in item:
                    c["httpOnly"] = bool(item["httpOnly"])
                if "secure" in item:
                    c["secure"] = bool(item["secure"])
                if "sameSite" in item and item["sameSite"] in ("Strict", "Lax", "None"):
                    c["sameSite"] = item["sameSite"]
                cookies.append(c)
            return cookies
        except Exception:
            pass

    # Tenta interpretar como formato Netscape (separado por tabulação)
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        http_only = False
        if line.startswith("#HttpOnly_"):
            line = line[10:]
            http_only = True
        elif line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) >= 7:
            domain, flag, path_val, secure, expiration, name, value = parts[:7]
            try:
                exp_float = float(expiration) if expiration != "0" else None
            except ValueError:
                exp_float = None

            c = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path_val,
                "httpOnly": http_only,
                "secure": secure.upper() == "TRUE",
            }
            if exp_float:
                c["expires"] = exp_float
            cookies.append(c)

    return cookies



