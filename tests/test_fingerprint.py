from src.browser.fingerprint import generate_fingerprint_profile, build_stealth_injection_script


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
