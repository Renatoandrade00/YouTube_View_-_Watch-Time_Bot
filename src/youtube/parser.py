from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import List, Optional, Set
from urllib.parse import parse_qs, urlparse

import httpx

from src.utils.helpers import get_random_user_agent

logger = logging.getLogger("bot")

# Padrões de identificação de URLs de Playlist e Canal
PLAYLIST_REGEX = re.compile(r"youtube\.com/playlist\?.*list=([a-zA-Z0-9_\-]+)", re.IGNORECASE)
CHANNEL_REGEX = re.compile(
    r"youtube\.com/(@[a-zA-Z0-9_\-\.]+|(?:channel|c|user)/[a-zA-Z0-9_\-]+)",
    re.IGNORECASE
)
WATCH_VIDEO_REGEX = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/)|youtu\.be/)([a-zA-Z0-9_\-]{11})",
    re.IGNORECASE
)
VIDEO_ID_JSON_REGEX = re.compile(r'"videoId"\s*:\s*"([a-zA-Z0-9_\-]{11})"')


def is_playlist_url(url: str) -> bool:
    """Verifica se a URL aponta para uma playlist do YouTube."""
    if not url:
        return False
    return bool(PLAYLIST_REGEX.search(url)) or ("list=" in url and "youtube.com" in url)


def is_channel_url(url: str) -> bool:
    """Verifica se a URL aponta para a página principal ou aba de vídeos de um canal."""
    if not url:
        return False
    return bool(CHANNEL_REGEX.search(url))


def is_expandable_url(url: str) -> bool:
    """Retorna True se a URL for uma playlist ou um canal que pode ser expandido em vídeos."""
    return is_playlist_url(url) or is_channel_url(url)


def extract_direct_video_id(url: str) -> Optional[str]:
    """Extrai o ID de 11 caracteres de um link direto de vídeo do YouTube (watch, shorts, youtu.be)."""
    if not url:
        return None
    match = WATCH_VIDEO_REGEX.search(url)
    if match:
        return match.group(1)
    return None


def normalize_channel_url(url: str) -> str:
    """Garante que a URL do canal aponte diretamente para a aba /videos."""
    cleaned = url.strip().rstrip("/")
    # Se já tem /videos, /shorts, etc, mantém
    if cleaned.endswith("/videos") or cleaned.endswith("/featured"):
        return cleaned
    # Se for link puro do handle (@canal) ou canal (/channel/UC...)
    return f"{cleaned}/videos"


async def fetch_html_httpx(url: str, timeout: float = 12.0) -> Optional[str]:
    """Obtém o conteúdo HTML de uma página do YouTube com headers realistas."""
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Dest": "document",
    }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers=headers,
            timeout=timeout
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"⚠️ [Parser] Status {resp.status_code} ao acessar {url}")
            return None
    except Exception as e:
        logger.warning(f"⚠️ [Parser] Falha na requisição HTTP direta ({url}): {e}")
        return None


def extract_video_ids_from_html(html: str) -> List[str]:
    """Extrai IDs de vídeo a partir do payload ytInitialData embutido no HTML."""
    if not html:
        return []

    video_ids: List[str] = []
    seen: Set[str] = set()

    # 1. Tenta extrair a partir do bloco ytInitialData (mais limpo e ordenado)
    match = re.search(r"var ytInitialData\s*=\s*(\{.+?\});\s*(?:</script>|;)", html, re.DOTALL)
    if not match:
        match = re.search(r"ytInitialData\s*=\s*(\{.+?\});", html, re.DOTALL)

    target_text = match.group(1) if match else html

    for vid in VIDEO_ID_JSON_REGEX.findall(target_text):
        if vid not in seen:
            seen.add(vid)
            video_ids.append(vid)

    # 2. Se por ventura não encontrou no bloco, busca no HTML inteiro
    if not video_ids and match:
        for vid in VIDEO_ID_JSON_REGEX.findall(html):
            if vid not in seen:
                seen.add(vid)
                video_ids.append(vid)

    return video_ids


async def extract_with_playwright_fallback(url: str, timeout: float = 15.0) -> List[str]:
    """Fallback para Playwright headless caso o YouTube sirva desafio ou consentimento estático."""
    logger.info(f"🔄 [Parser] Acionando fallback Playwright para extrair links de: {url}")
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                # Aceita cookies se modal estiver presente
                try:
                    consent_btn = page.locator("button:has-text('Aceitar tudo'), button:has-text('Accept all')").first
                    if await consent_btn.is_visible(timeout=2000):
                        await consent_btn.click()
                except Exception:
                    pass

                # Espera 1.5s para carregamento do script do YouTube
                await asyncio.sleep(1.5)

                # Extrai hrefs com /watch?v= do DOM
                hrefs = await page.eval_on_selector_all(
                    "a[href*='/watch?v=']",
                    "elements => elements.map(el => el.getAttribute('href'))"
                )

                video_ids: List[str] = []
                seen: Set[str] = set()
                for h in hrefs:
                    if not h:
                        continue
                    m = re.search(r"v=([a-zA-Z0-9_\-]{11})", h)
                    if m:
                        vid = m.group(1)
                        if vid not in seen:
                            seen.add(vid)
                            video_ids.append(vid)

                return video_ids
            finally:
                await page.close()
                await browser.close()
    except Exception as e:
        logger.error(f"❌ [Parser] Falha no fallback Playwright ({url}): {e}")
        return []


async def extract_videos_from_url(url: str, max_videos: Optional[int] = None) -> List[str]:
    """
    Recebe a URL de uma playlist ou canal e retorna lista de URLs completas de vídeos (https://www.youtube.com/watch?v=...).
    """
    target_url = url.strip()
    if is_channel_url(target_url):
        target_url = normalize_channel_url(target_url)

    logger.info(f"🔍 [Parser] Extraindo vídeos de: [bold cyan]{target_url}[/bold cyan]...")

    # 1. Tenta método ultra-rápido via HTTP direto (~500ms)
    html = await fetch_html_httpx(target_url)
    video_ids = extract_video_ids_from_html(html) if html else []

    # 2. Se falhar ou vier vazio, aciona o fallback com Playwright
    if not video_ids:
        video_ids = await extract_with_playwright_fallback(target_url)

    if max_videos and max_videos > 0:
        video_ids = video_ids[:max_videos]

    result_urls = [f"https://www.youtube.com/watch?v={vid}" for vid in video_ids]
    logger.info(f"✅ [Parser] [bold green]{len(result_urls)}[/bold green] vídeos extraídos com sucesso de: {target_url}")
    return result_urls


async def expand_urls_list(urls: List[str], max_per_source: Optional[int] = None) -> List[str]:
    """
    Processa uma lista mista de URLs (vídeos diretos, playlists e canais).
    Mantém os vídeos individuais e expande qualquer playlist ou canal em links de vídeos correspondentes.
    Deduplica mantendo a ordem original.
    """
    expanded: List[str] = []
    seen: Set[str] = set()

    for item in urls:
        cleaned = item.strip()
        if not cleaned or cleaned.startswith("#"):
            continue

        if is_expandable_url(cleaned):
            extracted = await extract_videos_from_url(cleaned, max_videos=max_per_source)
            for v_url in extracted:
                if v_url not in seen:
                    seen.add(v_url)
                    expanded.append(v_url)
        else:
            # Vídeo individual comum
            if cleaned not in seen:
                seen.add(cleaned)
                expanded.append(cleaned)

    return expanded
