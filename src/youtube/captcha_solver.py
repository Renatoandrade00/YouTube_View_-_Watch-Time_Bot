from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("bot")


class CaptchaSolver:
    def __init__(self, provider: Optional[str], api_key: Optional[str]) -> None:
        self.provider = (provider or "").lower().strip() or None
        self.api_key = api_key or os.getenv("CAPTCHA_SOLVER_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.provider and self.api_key)

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> Optional[str]:
        if not self.enabled:
            return None
        if self.provider == "2captcha":
            return await self._solve_2captcha(site_key, page_url)
        if self.provider == "capsolver":
            return await self._solve_capsolver(site_key, page_url)
        return None

    async def _solve_2captcha(self, site_key: str, page_url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "http://2captcha.com/in.php",
                    data={
                        "key": self.api_key,
                        "method": "userrecaptcha",
                        "googlekey": site_key,
                        "pageurl": page_url,
                        "json": 1,
                    },
                )
                data = resp.json()
                if data.get("status") != 1:
                    return None
                task_id = data.get("request")
                for _ in range(30):
                    await __import__("asyncio").sleep(5)
                    check = await client.get(
                        "http://2captcha.com/res.php",
                        params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                    )
                    result = check.json()
                    if result.get("status") == 1:
                        return result.get("request")
                    if result.get("request") != "CAPCHA_NOT_READY":
                        return None
        except Exception as e:
            logger.debug(f"2Captcha falhou: {e}")
        return None

    async def _solve_capsolver(self, site_key: str, page_url: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                create = await client.post(
                    "https://api.capsolver.com/createTask",
                    json={
                        "clientKey": self.api_key,
                        "task": {
                            "type": "ReCaptchaV2TaskProxyless",
                            "websiteKey": site_key,
                            "websiteURL": page_url,
                        },
                    },
                )
                data = create.json()
                task_id = data.get("taskId")
                if not task_id:
                    return None
                for _ in range(30):
                    await __import__("asyncio").sleep(3)
                    check = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.api_key, "taskId": task_id},
                    )
                    result = check.json()
                    if result.get("status") == "ready":
                        return result.get("solution", {}).get("gRecaptchaResponse")
                    if result.get("status") == "failed":
                        return None
        except Exception as e:
            logger.debug(f"CapSolver falhou: {e}")
        return None
