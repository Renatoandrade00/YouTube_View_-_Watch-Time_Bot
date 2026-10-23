from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List

from src.browser.stealth_profiles import generate_stealth_bundle, StealthBundle


GPU_PROFILES = [
    {
        "vendor": "Google Inc. (NVIDIA)",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (NVIDIA)",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (NVIDIA)",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (Intel)",
        "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (Intel)",
        "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (AMD)",
        "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "vendor": "Google Inc. (AMD)",
        "renderer": "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
]

PLATFORM_PROFILES: List[str] = ["Win32", "Win32", "Win32", "MacIntel", "Linux x86_64"]

VIEWPORT_PROFILES = [
    {"inner_w": 1280, "inner_h": 720},
    {"inner_w": 1366, "inner_h": 768},
    {"inner_w": 1440, "inner_h": 900},
    {"inner_w": 1920, "inner_h": 1080},
]


@dataclass
class FingerprintProfile:
    worker_id: int
    hardware_concurrency: int
    device_memory: int
    gpu_vendor: str
    gpu_renderer: str
    canvas_noise_seed: float
    audio_noise_seed: float
    outer_width: int
    outer_height: int
    platform: str
    # Campos adicionais para coerencia de stealth (v2.7)
    user_agent: str = ""
    locale: str = "pt-BR"
    timezone_id: str = "America/Sao_Paulo"
    viewport_width: int = 1280
    viewport_height: int = 720
    device_scale_factor: float = 1.0
    color_scheme: str = "light"


def _bundle_to_profile(bundle: StealthBundle) -> FingerprintProfile:
    return FingerprintProfile(
        worker_id=bundle.worker_id,
        hardware_concurrency=bundle.hardware_concurrency,
        device_memory=bundle.device_memory,
        gpu_vendor=bundle.gpu_vendor,
        gpu_renderer=bundle.gpu_renderer,
        canvas_noise_seed=bundle.canvas_noise_seed,
        audio_noise_seed=bundle.audio_noise_seed,
        outer_width=bundle.outer_width,
        outer_height=bundle.outer_height,
        platform=bundle.platform,
        user_agent=bundle.user_agent,
        locale=bundle.locale,
        timezone_id=bundle.timezone_id,
        viewport_width=bundle.viewport_width,
        viewport_height=bundle.viewport_height,
        device_scale_factor=bundle.device_scale_factor,
        color_scheme=bundle.color_scheme,
    )


def generate_fingerprint_profile(worker_id: int) -> FingerprintProfile:
    bundle = generate_stealth_bundle(worker_id)
    return _bundle_to_profile(bundle)


def build_stealth_injection_script(profile: FingerprintProfile) -> str:
    """
    Gera o script JavaScript injetado antes de qualquer página carregar.
    Implementa mascaramento stealth de alta fidelidade sem anomalias detectáveis pelo BotGuard:
    - Mascara webdriver sem criar propriedade própria em navigator (hasOwnWebdriver: false)
    - Emula PluginArray e MimeTypeArray herdando dos protótipos nativos do Chromium
    - Emula objeto window.chrome real com app, csi, loadTimes e runtime
    - Spoofa WebGL Vendor/Renderer sem adulterar buffers determinísticos de Canvas/Audio
    - Emula dimensões realistas de janela desktop, tela e timezone
    """
    profile_data = {
        "concurrency": profile.hardware_concurrency,
        "memory": profile.device_memory,
        "vendor": profile.gpu_vendor,
        "renderer": profile.gpu_renderer,
        "outerWidth": profile.outer_width,
        "outerHeight": profile.outer_height,
        "platform": profile.platform,
        "locale": profile.locale,
        "timezone": profile.timezone_id,
        "screenWidth": profile.viewport_width,
        "screenHeight": profile.viewport_height,
        "deviceScaleFactor": profile.device_scale_factor,
    }

    return f"""(() => {{
        const config = {json.dumps(profile_data)};
        // navigator.webdriver
        // UNMASKED_VENDOR_WEBGL
        // UNMASKED_RENDERER_WEBGL
        // PluginArray
        // plugins
        // mimeTypes
        // languages
        // platform
        // outerWidth
        // outerHeight
        // colorDepth
        // window.chrome

        // Helper para emular [native code] em funções modificadas
        const makeNative = (fn, name) => {{
            try {{
                Object.defineProperty(fn, 'name', {{ value: name || 'get' }});
                Object.defineProperty(fn, 'toString', {{
                    value: function() {{ return `function ${{name || ''}}() {{ [native code] }}`; }},
                    configurable: true,
                    writable: true
                }});
            }} catch(e) {{}}
            return fn;
        }};

        // 1. navigator.webdriver: preserva integridade nativa do Chrome
        try {{
            if (navigator.webdriver === true) {{
                const proto = Object.getPrototypeOf(navigator) || navigator;
                const getWd = makeNative(() => false, 'get webdriver');
                Object.defineProperty(proto, 'webdriver', {{
                    get: getWd,
                    configurable: true,
                    enumerable: true
                }});
            }}
        }} catch(e) {{}}

        // 2. Hardware: Cores e Memória RAM
        try {{
            const proto = Object.getPrototypeOf(navigator) || navigator;
            if (!navigator.hardwareConcurrency || navigator.hardwareConcurrency < 2) {{
                const getHc = makeNative(() => config.concurrency, 'get hardwareConcurrency');
                Object.defineProperty(proto, 'hardwareConcurrency', {{
                    get: getHc,
                    configurable: true,
                    enumerable: true
                }});
            }}
            if (!navigator.deviceMemory) {{
                const getDm = makeNative(() => config.memory, 'get deviceMemory');
                Object.defineProperty(proto, 'deviceMemory', {{
                    get: getDm,
                    configurable: true,
                    enumerable: true
                }});
            }}
        }} catch(e) {{}}

        // 3. Emulação não-intrusiva de window.chrome (só se ausente)
        try {{
            if (!window.chrome) {{
                window.chrome = {{
                    app: {{ isInstalled: false }},
                    runtime: {{
                        OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install' }},
                        PlatformArch: {{ X86_64: 'x86-64' }},
                        PlatformOs: {{ WIN: 'win' }}
                    }}
                }};
            }}
        }} catch(e) {{}}

        // 4. Spoofing de WebGL preservando assinatura [native code]
        const overrideWebGL = (proto) => {{
            if (!proto || proto._stealthPatched) return;
            proto._stealthPatched = true;
            const originalGetParameter = proto.getParameter;
            const customGetParameter = function(param) {{
                if (param === 37445) return config.vendor;
                if (param === 37446) return config.renderer;
                return originalGetParameter.apply(this, arguments);
            }};
            makeNative(customGetParameter, 'getParameter');
            proto.getParameter = customGetParameter;
        }};

        try {{
            overrideWebGL(window.WebGLRenderingContext?.prototype);
            overrideWebGL(window.WebGL2RenderingContext?.prototype);
        }} catch(e) {{}}

        // 5. Plugins e MimeTypes conformes com herança nativa
        try {{
            if (!navigator.plugins || navigator.plugins.length === 0) {{
                const pluginArrayProto = window.PluginArray ? window.PluginArray.prototype : Object.prototype;
                const mimeTypeArrayProto = window.MimeTypeArray ? window.MimeTypeArray.prototype : Object.prototype;
                const pluginsList = Object.create(pluginArrayProto);
                Object.defineProperty(pluginsList, 'length', {{ value: 3, enumerable: false }});
                Object.defineProperty(Object.getPrototypeOf(navigator) || navigator, 'plugins', {{
                    get: makeNative(() => pluginsList, 'get plugins'),
                    configurable: true,
                    enumerable: true
                }});
                const mimeList = Object.create(mimeTypeArrayProto);
                Object.defineProperty(mimeList, 'length', {{ value: 2, enumerable: false }});
                Object.defineProperty(Object.getPrototypeOf(navigator) || navigator, 'mimeTypes', {{
                    get: makeNative(() => mimeList, 'get mimeTypes'),
                    configurable: true,
                    enumerable: true
                }});
            }}
        }} catch(e) {{}}

        // 6. Configurações complementares de ambiente Desktop
        try {{
            const navProto = Object.getPrototypeOf(navigator) || navigator;
            const primaryLocale = config.locale || 'pt-BR';
            const baseLang = primaryLocale.split('-')[0];
            Object.defineProperty(navProto, 'languages', {{
                get: makeNative(() => [primaryLocale, baseLang, 'en-US', 'en'], 'get languages'),
                configurable: true,
                enumerable: true
            }});

            Object.defineProperty(navProto, 'platform', {{
                get: makeNative(() => config.platform || 'Win32', 'get platform'),
                configurable: true,
                enumerable: true
            }});

            Object.defineProperty(window, 'outerWidth', {{
                get: makeNative(() => config.outerWidth, 'get outerWidth'),
                configurable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: makeNative(() => config.outerHeight, 'get outerHeight'),
                configurable: true
            }});

            Object.defineProperty(screen, 'width', {{ get: makeNative(() => config.screenWidth, 'get width'), configurable: true }});
            Object.defineProperty(screen, 'height', {{ get: makeNative(() => config.screenHeight, 'get height'), configurable: true }});
            Object.defineProperty(screen, 'colorDepth', {{ get: makeNative(() => 24, 'get colorDepth'), configurable: true }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: makeNative(() => 24, 'get pixelDepth'), configurable: true }});
        }} catch(e) {{}}
    }})();"""
