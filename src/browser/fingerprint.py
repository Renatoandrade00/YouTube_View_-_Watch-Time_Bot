from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Dict, Any, List


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

# Plataformas reais por frequência de uso (Win32 é a mais comum)
PLATFORM_PROFILES: List[str] = ["Win32", "Win32", "Win32", "MacIntel", "Linux x86_64"]

# Viewports comuns (inner size); outerHeight = inner + chrome UI (~88px)
VIEWPORT_PROFILES = [
    {"inner_w": 1280, "inner_h": 720},
    {"inner_w": 1366, "inner_h": 768},
    {"inner_w": 1440, "inner_h": 900},
    {"inner_w": 1920, "inner_h": 1080},
]


@dataclass
class FingerprintProfile:
    """Perfil único de hardware e assinaturas de renderização por worker."""
    worker_id: int
    hardware_concurrency: int
    device_memory: int
    gpu_vendor: str
    gpu_renderer: str
    canvas_noise_seed: float
    audio_noise_seed: float
    # Novos campos para stealth expandido
    outer_width: int
    outer_height: int
    platform: str


def generate_fingerprint_profile(worker_id: int) -> FingerprintProfile:
    """
    Gera um perfil de hardware variado por worker e por faixa horária.
    O seed varia a cada hora, garantindo que o mesmo worker não mantenha
    o mesmo fingerprint entre rodadas distintas — o que seria detectável
    pelo YouTube como padrão de automação.
    """
    hour_bucket = int(time.time() // 3600)
    rnd = random.Random(worker_id * 1000 + hour_bucket)

    gpu = rnd.choice(GPU_PROFILES)
    concurrency = rnd.choice([4, 6, 8, 12, 16])
    memory = rnd.choice([8, 16, 32])
    canvas_seed = rnd.uniform(0.0001, 0.0009)
    audio_seed = rnd.uniform(0.000001, 0.000009)
    platform = rnd.choice(PLATFORM_PROFILES)

    vp = rnd.choice(VIEWPORT_PROFILES)
    inner_w = vp["inner_w"]
    inner_h = vp["inner_h"]
    # outerHeight simula barra de título + abas + barra de endereços do Chrome (~88–100px)
    outer_h = inner_h + rnd.randint(85, 102)
    outer_w = inner_w  # outerWidth geralmente igual ao innerWidth

    return FingerprintProfile(
        worker_id=worker_id,
        hardware_concurrency=concurrency,
        device_memory=memory,
        gpu_vendor=gpu["vendor"],
        gpu_renderer=gpu["renderer"],
        canvas_noise_seed=canvas_seed,
        audio_noise_seed=audio_seed,
        outer_width=outer_w,
        outer_height=outer_h,
        platform=platform,
    )


def build_stealth_injection_script(profile: FingerprintProfile) -> str:
    """
    Gera o script JavaScript injetado antes de qualquer página carregar.
    Implementa mascaramento stealth de alta fidelidade sem anomalias detectáveis pelo BotGuard:
    - Mascara webdriver sem criar propriedade própria em navigator (hasOwnWebdriver: false)
    - Emula PluginArray e MimeTypeArray herdando dos protótipos nativos do Chromium
    - Emula objeto window.chrome real com app, csi, loadTimes e runtime
    - Spoofa WebGL Vendor/Renderer sem adulterar buffers determinísticos de Canvas/Audio
    - Emula dimensões realistas de janela desktop e idiomas
    """
    profile_data = {
        "concurrency": profile.hardware_concurrency,
        "memory": profile.device_memory,
        "vendor": profile.gpu_vendor,
        "renderer": profile.gpu_renderer,
        "outerWidth": profile.outer_width,
        "outerHeight": profile.outer_height,
        "platform": profile.platform,
    }

    return f"""(() => {{
        const config = {json.dumps(profile_data)};

        // 1. Mascara navigator.webdriver sem criar own property em navigator
        try {{
            const proto = Object.getPrototypeOf(navigator);
            if (proto && proto.hasOwnProperty('webdriver')) {{
                delete proto.webdriver;
            }}
            Object.defineProperty(proto || navigator, 'webdriver', {{
                get: () => undefined,
                configurable: true,
                enumerable: true
            }});
        }} catch(e) {{}}

        // 2. Hardware: Cores e Memória RAM
        try {{
            const proto = Object.getPrototypeOf(navigator) || navigator;
            Object.defineProperty(proto, 'hardwareConcurrency', {{
                get: () => config.concurrency,
                configurable: true,
                enumerable: true
            }});
            Object.defineProperty(proto, 'deviceMemory', {{
                get: () => config.memory,
                configurable: true,
                enumerable: true
            }});
        }} catch(e) {{}}

        // 3. Emulação completa e realista de window.chrome
        try {{
            if (!window.chrome) {{
                window.chrome = {{}};
            }}
            window.chrome.app = {{
                isInstalled: false,
                InstallState: {{ DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }},
                RunningState: {{ CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }}
            }};
            window.chrome.csi = function() {{
                return {{ startE: Date.now(), onloadT: Date.now() + 100, pageT: 500, tran: 15 }};
            }};
            window.chrome.loadTimes = function() {{
                return {{
                    requestTime: Date.now() / 1000,
                    startLoadTime: Date.now() / 1000,
                    commitLoadTime: Date.now() / 1000 + 0.1,
                    finishDocumentLoadTime: Date.now() / 1000 + 0.3,
                    firstPaintTime: Date.now() / 1000 + 0.35,
                    finishLoadTime: Date.now() / 1000 + 0.45,
                    wasFetchedViaSpdy: true,
                    wasNpnNegotiated: true,
                    npnNegotiatedProtocol: 'h2',
                    wasAlternateProtocolAvailable: false,
                    connectionInfo: 'h2'
                }};
            }};
            window.chrome.runtime = {{
                OnInstalledReason: {{ CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }},
                OnRestartRequiredReason: {{ APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }},
                PlatformArch: {{ ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                PlatformNaclArch: {{ ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }},
                PlatformOs: {{ ANDROID: 'android', CROS: 'cros', FUCHSIA: 'fuchsia', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }},
                RequestUpdateCheckStatus: {{ NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' }}
            }};
        }} catch(e) {{}}

        // 4. Spoofing de WebGL (Vendor e Renderer da GPU)
        const overrideWebGL = (proto) => {{
            if (!proto) return;
            const originalGetParameter = proto.getParameter;
            proto.getParameter = function(param) {{
                // UNMASKED_VENDOR_WEBGL
                if (param === 37445) return config.vendor;
                // UNMASKED_RENDERER_WEBGL
                if (param === 37446) return config.renderer;
                return originalGetParameter.apply(this, arguments);
            }};
        }};

        try {{
            overrideWebGL(window.WebGLRenderingContext?.prototype);
            overrideWebGL(window.WebGL2RenderingContext?.prototype);
        }} catch(e) {{}}

        // 5. Plugins e MimeTypes conformes com herança nativa de protótipo
        try {{
            const pluginArrayProto = window.PluginArray ? window.PluginArray.prototype : Object.prototype;
            const pluginProto = window.Plugin ? window.Plugin.prototype : Object.prototype;
            const mimeTypeArrayProto = window.MimeTypeArray ? window.MimeTypeArray.prototype : Object.prototype;
            const mimeTypeProto = window.MimeType ? window.MimeType.prototype : Object.prototype;

            function createPlugin(data) {{
                const p = Object.create(pluginProto);
                Object.defineProperties(p, {{
                    name: {{ value: data.name, enumerable: true }},
                    filename: {{ value: data.filename, enumerable: true }},
                    description: {{ value: data.description, enumerable: true }},
                    length: {{ value: data.mimeTypes.length, enumerable: true }}
                }});
                data.mimeTypes.forEach((m, idx) => {{
                    p[idx] = m;
                }});
                p.item = function(index) {{ return this[index] || null; }};
                p.namedItem = function(name) {{
                    for (let i = 0; i < this.length; i++) {{
                        if (this[i].type === name) return this[i];
                    }}
                    return null;
                }};
                return p;
            }}

            function createMimeType(data) {{
                const m = Object.create(mimeTypeProto);
                Object.defineProperties(m, {{
                    type: {{ value: data.type, enumerable: true }},
                    suffixes: {{ value: data.suffixes, enumerable: true }},
                    description: {{ value: data.description, enumerable: true }},
                    enabledPlugin: {{ value: data.enabledPlugin, writable: true, enumerable: true }}
                }});
                return m;
            }}

            const pdfMime = createMimeType({{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: null }});
            const textPdfMime = createMimeType({{ type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: null }});

            const pdfPlugin = createPlugin({{
                name: 'PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [pdfMime, textPdfMime]
            }});
            const chromePdf = createPlugin({{
                name: 'Chrome PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [pdfMime]
            }});
            const chromiumPdf = createPlugin({{
                name: 'Chromium PDF Viewer',
                filename: 'internal-pdf-viewer',
                description: 'Portable Document Format',
                mimeTypes: [pdfMime]
            }});

            pdfMime.enabledPlugin = pdfPlugin;
            textPdfMime.enabledPlugin = pdfPlugin;

            const pluginsList = Object.create(pluginArrayProto);
            pluginsList[0] = pdfPlugin;
            pluginsList[1] = chromePdf;
            pluginsList[2] = chromiumPdf;
            Object.defineProperty(pluginsList, 'length', {{ value: 3, enumerable: false }});
            pluginsList.item = function(index) {{ return this[index] || null; }};
            pluginsList.namedItem = function(name) {{
                for (let i = 0; i < this.length; i++) {{
                    if (this[i].name === name) return this[i];
                }}
                return null;
            }};
            pluginsList.refresh = function() {{}};

            Object.defineProperty(Object.getPrototypeOf(navigator) || navigator, 'plugins', {{
                get: () => pluginsList,
                configurable: true,
                enumerable: true
            }});

            const mimeList = Object.create(mimeTypeArrayProto);
            mimeList[0] = pdfMime;
            mimeList[1] = textPdfMime;
            Object.defineProperty(mimeList, 'length', {{ value: 2, enumerable: false }});
            mimeList.item = function(index) {{ return this[index] || null; }};
            mimeList.namedItem = function(name) {{
                for (let i = 0; i < this.length; i++) {{
                    if (this[i].type === name) return this[i];
                }}
                return null;
            }};

            Object.defineProperty(Object.getPrototypeOf(navigator) || navigator, 'mimeTypes', {{
                get: () => mimeList,
                configurable: true,
                enumerable: true
            }});
        }} catch(e) {{}}

        // 6. Configurações complementares de ambiente Desktop
        try {{
            const navProto = Object.getPrototypeOf(navigator) || navigator;
            Object.defineProperty(navProto, 'languages', {{
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
                configurable: true,
                enumerable: true
            }});

            Object.defineProperty(navProto, 'platform', {{
                get: () => config.platform,
                configurable: true,
                enumerable: true
            }});

            Object.defineProperty(window, 'outerWidth', {{
                get: () => config.outerWidth,
                configurable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: () => config.outerHeight,
                configurable: true
            }});

            Object.defineProperty(screen, 'colorDepth', {{ get: () => 24, configurable: true }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => 24, configurable: true }});
        }} catch(e) {{}}
    }})();"""
