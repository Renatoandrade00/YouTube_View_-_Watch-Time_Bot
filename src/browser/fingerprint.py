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
    Cobre: webdriver, hardwareConcurrency, deviceMemory, WebGL, Canvas,
    AudioContext, navigator.plugins, navigator.languages, navigator.platform,
    outerWidth/outerHeight, screen.colorDepth/pixelDepth.
    """
    profile_data = {
        "concurrency": profile.hardware_concurrency,
        "memory": profile.device_memory,
        "vendor": profile.gpu_vendor,
        "renderer": profile.gpu_renderer,
        "canvasNoise": profile.canvas_noise_seed,
        "audioNoise": profile.audio_noise_seed,
        "outerWidth": profile.outer_width,
        "outerHeight": profile.outer_height,
        "platform": profile.platform,
    }

    return f"""(() => {{
        const config = {json.dumps(profile_data)};

        // 1. Mascara navigator.webdriver e propriedades de hardware
        try {{
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined,
                configurable: true
            }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => config.concurrency,
                configurable: true
            }});
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => config.memory,
                configurable: true
            }});
            if (!window.chrome) {{
                window.chrome = {{ runtime: {{}} }};
            }}
        }} catch(e) {{}}

        // 2. Spoofing de WebGL (Vendor e Renderer da GPU)
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

        // 3. Injeção de micro-ruído imperceptível no Canvas 2D
        try {{
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
                const imageData = origGetImageData.apply(this, arguments);
                const d = imageData.data;
                const shift = Math.floor(config.canvasNoise * 10) || 1;
                // Aplica ruído sutil apenas em alguns pixels para alterar o hash do Canvas
                for (let i = 0; i < d.length; i += 256) {{
                    d[i] = (d[i] + shift) % 256;
                }}
                return imageData;
            }};

            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {{
                const ctx = this.getContext('2d');
                if (ctx && this.width > 16 && this.height > 16) {{
                    try {{
                        const img = ctx.getImageData(0, 0, 1, 1);
                        img.data[0] = (img.data[0] + 1) % 256;
                        ctx.putImageData(img, 0, 0);
                    }} catch(e) {{}}
                }}
                return origToDataURL.apply(this, arguments);
            }};
        }} catch(e) {{}}

        // 4. Injeção de ruído no AudioContext
        try {{
            if (window.AudioBuffer) {{
                const origGetChannelData = AudioBuffer.prototype.getChannelData;
                AudioBuffer.prototype.getChannelData = function() {{
                    const channelData = origGetChannelData.apply(this, arguments);
                    const noise = config.audioNoise;
                    for (let i = 0; i < channelData.length; i += 128) {{
                        channelData[i] += (Math.random() - 0.5) * noise;
                    }}
                    return channelData;
                }};
            }}
            if (window.AnalyserNode) {{
                const origGetFloatFreq = AnalyserNode.prototype.getFloatFrequencyData;
                AnalyserNode.prototype.getFloatFrequencyData = function(array) {{
                    origGetFloatFreq.apply(this, arguments);
                    const noise = config.audioNoise * 10;
                    for (let i = 0; i < array.length; i += 64) {{
                        array[i] += (Math.random() - 0.5) * noise;
                    }}
                }};
            }}
        }} catch(e) {{}}

        // 5. Stealth expandido: plugins, languages, platform, outerWidth/Height, colorDepth
        try {{
            // navigator.plugins vazio é o sinal mais imediato de browser headless.
            // Simula os 3 plugins padrão que todo Chrome real possui.
            const fakePlugins = [
                {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 }},
                {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 }},
                {{ name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 }},
            ];
            Object.defineProperty(navigator, 'plugins', {{
                get: () => fakePlugins,
                configurable: true
            }});
            Object.defineProperty(navigator, 'mimeTypes', {{
                get: () => [{{ type: 'application/pdf', suffixes: 'pdf', description: '' }}],
                configurable: true
            }});

            // Usuários reais têm múltiplos idiomas configurados
            Object.defineProperty(navigator, 'languages', {{
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
                configurable: true
            }});

            // Plataforma consistente com o User-Agent
            Object.defineProperty(navigator, 'platform', {{
                get: () => config.platform,
                configurable: true
            }});

            // outerWidth/outerHeight em headless = 0; em browser real = inner + chrome UI
            Object.defineProperty(window, 'outerWidth', {{
                get: () => config.outerWidth,
                configurable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: () => config.outerHeight,
                configurable: true
            }});

            // Profundidade de cor — sempre 24 em monitores modernos
            Object.defineProperty(screen, 'colorDepth', {{ get: () => 24, configurable: true }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => 24, configurable: true }});
        }} catch(e) {{}}
    }})();"""
