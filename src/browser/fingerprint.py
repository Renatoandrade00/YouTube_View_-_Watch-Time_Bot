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

        const overrideWebGL = (proto) => {{
            if (!proto) return;
            const originalGetParameter = proto.getParameter;
            proto.getParameter = function(param) {{
                if (param === 37445) return config.vendor;
                if (param === 37446) return config.renderer;
                return originalGetParameter.apply(this, arguments);
            }};
        }};

        try {{
            overrideWebGL(window.WebGLRenderingContext?.prototype);
            overrideWebGL(window.WebGL2RenderingContext?.prototype);
        }} catch(e) {{}}

        try {{
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
                const imageData = origGetImageData.apply(this, arguments);
                const d = imageData.data;
                const shift = Math.floor(config.canvasNoise * 10) || 1;
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

        try {{
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

            Object.defineProperty(navigator, 'languages', {{
                get: () => [config.locale, config.locale.split('-')[0], 'en-US', 'en'],
                configurable: true
            }});

            Object.defineProperty(navigator, 'platform', {{
                get: () => config.platform,
                configurable: true
            }});

            Object.defineProperty(window, 'outerWidth', {{
                get: () => config.outerWidth,
                configurable: true
            }});
            Object.defineProperty(window, 'outerHeight', {{
                get: () => config.outerHeight,
                configurable: true
            }});

            Object.defineProperty(screen, 'width', {{ get: () => config.screenWidth, configurable: true }});
            Object.defineProperty(screen, 'height', {{ get: () => config.screenHeight, configurable: true }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => config.screenWidth, configurable: true }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => config.screenHeight - 40, configurable: true }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => 24, configurable: true }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => 24, configurable: true }});

            Object.defineProperty(window, 'devicePixelRatio', {{
                get: () => config.deviceScaleFactor,
                configurable: true
            }});

            // Timezone spoofing via Intl
            try {{
                const origResolved = Intl.DateTimeFormat.prototype.resolvedOptions;
                Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
                    const opts = origResolved.apply(this, arguments);
                    opts.timeZone = config.timezone;
                    return opts;
                }};
            }} catch(e) {{}}
        }} catch(e) {{}}
    }})();"""
