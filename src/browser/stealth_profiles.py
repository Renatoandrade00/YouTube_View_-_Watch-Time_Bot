from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import List


GPU_PROFILES = [
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)"),
]

PLATFORM_BUNDLES = {
    "Win32": {
        "user_agents": [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36",
        ],
        "timezone": "America/Sao_Paulo",
        "locale": "pt-BR",
    },
    "MacIntel": {
        "user_agents": [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36",
        ],
        "timezone": "America/Sao_Paulo",
        "locale": "pt-BR",
    },
    "Linux x86_64": {
        "user_agents": [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36",
        ],
        "timezone": "America/Sao_Paulo",
        "locale": "pt-BR",
    },
}

VIEWPORTS = [
    (1280, 720),
    (1366, 768),
    (1440, 900),
    (1920, 1080),
]

CHROME_VERSIONS = [122, 123, 124, 125, 126]


@dataclass
class StealthBundle:
    worker_id: int
    user_agent: str
    platform: str
    locale: str
    timezone_id: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float
    color_scheme: str
    hardware_concurrency: int
    device_memory: int
    gpu_vendor: str
    gpu_renderer: str
    canvas_noise_seed: float
    audio_noise_seed: float
    outer_width: int
    outer_height: int


def generate_stealth_bundle(worker_id: int, hour_bucket: int | None = None) -> StealthBundle:
    if hour_bucket is None:
        hour_bucket = int(time.time() // 3600)
    rnd = random.Random(worker_id * 1009 + hour_bucket * 17)

    platform = rnd.choice(["Win32", "Win32", "Win32", "MacIntel", "Linux x86_64"])
    platform_info = PLATFORM_BUNDLES[platform]
    chrome_ver = rnd.choice(CHROME_VERSIONS)
    ua_template = rnd.choice(platform_info["user_agents"])
    user_agent = ua_template.format(ver=chrome_ver)

    vp_w, vp_h = rnd.choice(VIEWPORTS)
    dpr = rnd.choice([1.0, 1.0, 1.25, 1.5, 2.0])
    color_scheme = rnd.choice(["light", "light", "dark"])
    concurrency = rnd.choice([4, 6, 8, 12, 16])
    memory = rnd.choice([8, 16, 32])
    gpu_vendor, gpu_renderer = rnd.choice(GPU_PROFILES)
    canvas_seed = rnd.uniform(0.0001, 0.0009)
    audio_seed = rnd.uniform(0.000001, 0.000009)
    outer_h = vp_h + rnd.randint(85, 102)
    outer_w = vp_w

    return StealthBundle(
        worker_id=worker_id,
        user_agent=user_agent,
        platform=platform,
        locale=platform_info["locale"],
        timezone_id=platform_info["timezone"],
        viewport_width=vp_w,
        viewport_height=vp_h,
        device_scale_factor=dpr,
        color_scheme=color_scheme,
        hardware_concurrency=concurrency,
        device_memory=memory,
        gpu_vendor=gpu_vendor,
        gpu_renderer=gpu_renderer,
        canvas_noise_seed=canvas_seed,
        audio_noise_seed=audio_seed,
        outer_width=outer_w,
        outer_height=outer_h,
    )
