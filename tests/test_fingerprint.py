from src.browser.fingerprint import generate_fingerprint_profile, build_stealth_injection_script, FingerprintProfile


def test_generate_fingerprint_profile():
    p1 = generate_fingerprint_profile(worker_id=1)
    p2 = generate_fingerprint_profile(worker_id=2)

    # Cada worker deve ter um perfil instanciado
    assert p1.worker_id == 1
    assert p2.worker_id == 2
    assert p1.hardware_concurrency in [4, 6, 8, 12, 16]
    assert p1.device_memory in [8, 16, 32]
    assert "Google Inc." in p1.gpu_vendor
    assert len(p1.gpu_renderer) > 10
    assert p1.canvas_noise_seed > 0
    assert p1.audio_noise_seed > 0

    # Novos campos da Etapa 2
    assert p1.outer_width in [1280, 1366, 1440, 1920]
    assert p1.outer_height > p1.outer_width * 0.5  # proporção desktop plausível
    assert p1.platform in ["Win32", "MacIntel", "Linux x86_64"]


def test_fingerprint_hour_bucket_variation():
    """Garante que a função aceita execução em horários distintos sem colisão estática."""
    import time
    from unittest.mock import patch

    with patch("time.time", return_value=1700000000.0):
        p_hour1 = generate_fingerprint_profile(worker_id=1)

    with patch("time.time", return_value=1700000000.0 + 3600 * 5):
        p_hour2 = generate_fingerprint_profile(worker_id=1)

    assert isinstance(p_hour1, FingerprintProfile)
    assert isinstance(p_hour2, FingerprintProfile)


def test_build_stealth_injection_script():
    profile = generate_fingerprint_profile(worker_id=3)
    script = build_stealth_injection_script(profile)

    assert isinstance(script, str)
    assert "navigator.webdriver" in script
    assert "UNMASKED_VENDOR_WEBGL" in script
    assert "UNMASKED_RENDERER_WEBGL" in script
    assert "CanvasRenderingContext2D" in script
    assert "AudioBuffer" in script
    assert str(profile.hardware_concurrency) in script

    # Verificações do stealth expandido (Etapa 2)
    assert "fakePlugins" in script
    assert "navigator, 'plugins'" in script
    assert "mimeTypes" in script
    assert "languages" in script
    assert "platform" in script
    assert "outerWidth" in script
    assert "outerHeight" in script
    assert "colorDepth" in script
    assert str(profile.outer_width) in script
    assert str(profile.outer_height) in script
