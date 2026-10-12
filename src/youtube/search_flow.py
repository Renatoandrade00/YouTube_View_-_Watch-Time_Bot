from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus

import httpx
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.youtube.parser import extract_direct_video_id

logger = logging.getLogger("bot")

_TITLE_CACHE: Dict[str, str] = {}


def parse_url_and_keyword(line: str) -> Tuple[str, Optional[str]]:
    """
    Analisa uma linha contendo URL e opcionalmente uma palavra-chave customizada.
    Formatos aceitos:
      - 'https://www.youtube.com/watch?v=xyz'
      - 'https://www.youtube.com/watch?v=xyz | palavra-chave de busca'
      - 'https://www.youtube.com/watch?v=xyz;palavra-chave'
      - 'palavra-chave;https://www.youtube.com/watch?v=xyz'
    """
    raw = line.strip()
    if not raw:
        return "", None

    # Separador por pipe '|'
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|", 1)]
        url_part = parts[0]
        kw_part = parts[1] if len(parts) > 1 and parts[1] else None
        return url_part, kw_part

    # Separador por ponto e vírgula ';'
    if ";" in raw:
        parts = [p.strip() for p in raw.split(";", 1)]
        if parts[0].startswith("http"):
            return parts[0], parts[1] if parts[1] else None
        elif parts[1].startswith("http"):
            return parts[1], parts[0] if parts[0] else None

    return raw, None


async def get_video_title(video_url: str) -> Optional[str]:
    """
    Obtém o título do vídeo via endpoint público oEmbed do YouTube ou cache local.
    Não requer autenticação ou chave de API.
    """
    vid = extract_direct_video_id(video_url)
    if not vid:
        return None

    if vid in _TITLE_CACHE:
        return _TITLE_CACHE[vid]

    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(oembed_url)
            if resp.status_code == 200:
                data = resp.json()
                title = data.get("title")
                if title:
                    clean_title = re.sub(r"[^\w\s\-\.,!?']", " ", title).strip()
                    _TITLE_CACHE[vid] = clean_title
                    return clean_title
    except Exception as e:
        logger.debug(f"Não foi possível obter título via oEmbed para {vid}: {e}")

    return None


async def perform_search_and_play(
    page: Page,
    target_url: str,
    worker_id: int,
    custom_keyword: Optional[str] = None,
) -> bool:
    """
    Simula o fluxo completo de busca orgânica no YouTube (Search & Play):
    1. Acessa https://www.youtube.com
    2. Localiza a caixa de busca e digita a palavra-chave/título com ritmo humano
    3. Pressiona Enter e aguarda os resultados
    4. Rola os resultados até encontrar o vídeo alvo pelo ID
    5. Clica no resultado para iniciar a reprodução orgânica
    6. Se o vídeo não for localizado após rolagens, faz fallback seguro para page.goto(target_url).
    """
    vid = extract_direct_video_id(target_url)
    if not vid:
        # Se não é vídeo direto reconhecível, navega normalmente
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        return False

    search_query = custom_keyword
    if not search_query:
        search_query = await get_video_title(target_url)

    if not search_query:
        search_query = vid

    # Trunca títulos excessivamente longos para uma busca mais natural
    words = search_query.split()
    if len(words) > 8:
        search_query = " ".join(words[:8])

    logger.info(
        f"[Worker {worker_id}] 🔍 Modo Search & Play ativado: Buscando no YouTube por \"{search_query}\"..."
    )

    try:
        from src.web.state import StateManager
        sm = StateManager.get_instance()
        if sm.is_running:
            sm.update_worker(
                worker_id=worker_id,
                status=f"Buscando \"{search_query[:20]}...\"",
                current_watch_time=0.0
            )
    except Exception:
        pass

    try:
        # 1. Navega até a página inicial do YouTube
        await page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=35000)
        await asyncio.sleep(random.uniform(1.2, 2.5))

        # Trata popups de consentimento se surgirem
        from src.youtube.player import handle_consent_popups
        await handle_consent_popups(page)

        # 2. Localiza o campo de busca
        search_selectors = [
            "input#search",
            "input.ytd-searchbox",
            "input[name='search_query']",
            "textarea.ytSearchboxComponentInput",
            "input.ytSearchboxComponentInput",
        ]

        search_input = None
        for sel in search_selectors:
            locator = page.locator(sel).first
            if await locator.is_visible(timeout=1500):
                search_input = locator
                break

        if not search_input:
            logger.warning(f"[Worker {worker_id}] ⚠️ Caixa de busca não encontrada no DOM. Fallback para navegação direta.")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            return False

        # Clica na caixa de busca e limpa
        await search_input.click()
        await asyncio.sleep(random.uniform(0.3, 0.7))

        # Digitação com cadência humana
        for char in search_query:
            await search_input.type(char, delay=random.randint(45, 120))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.1, 0.3))

        await asyncio.sleep(random.uniform(0.5, 1.0))
        await search_input.press("Enter")

        # 3. Aguarda os resultados carregarem
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # 4. Procura o link do vídeo correspondente nos resultados
        video_locator_sel = f"a[href*='{vid}']"
        target_item = None

        # Rola a página até 4 vezes buscando o resultado
        for scroll_round in range(4):
            item = page.locator(video_locator_sel).first
            if await item.is_visible(timeout=1000):
                target_item = item
                break

            # Rolagem suave para baixo
            scroll_amount = random.randint(350, 600)
            await page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(1.0, 2.0))

        if target_item:
            logger.info(
                f"[Worker {worker_id}] 🎯 Vídeo encontrado nos resultados orgânicos! Clicando no item..."
            )
            # Rola até o elemento e clica
            await target_item.scroll_into_view_if_needed(timeout=2000)
            await asyncio.sleep(random.uniform(0.4, 0.9))
            await target_item.click(timeout=3000)
            await asyncio.sleep(random.uniform(1.5, 3.0))
            return True
        else:
            logger.info(
                f"[Worker {worker_id}] ℹ️ Vídeo não avistado nos primeiros resultados da busca. "
                "Realizando acesso direto transparente como fallback."
            )
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            return False

    except Exception as e:
        logger.warning(
            f"[Worker {worker_id}] ⚠️ Falha durante fluxo de busca ({e}). Realizando navegação direta como fallback."
        )
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass
        return False
