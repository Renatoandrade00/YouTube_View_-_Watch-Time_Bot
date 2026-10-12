from src.utils.helpers import (
    get_random_user_agent,
    get_random_viewport,
    normalize_youtube_url,
)


def test_get_random_user_agent():
    ua1 = get_random_user_agent()
    assert isinstance(ua1, str)
    assert len(ua1) > 10
    assert "Mozilla" in ua1


def test_get_random_viewport():
    vp = get_random_viewport()
    assert isinstance(vp, dict)
    assert "width" in vp
    assert "height" in vp
    assert vp["width"] >= 1280
    assert vp["height"] >= 720


def test_normalize_youtube_url_short():
    short_url = "https://youtu.be/dQw4w9WgXcQ?si=abcdef123"
    normalized = normalize_youtube_url(short_url)
    assert normalized == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_normalize_youtube_url_standard():
    standard_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    normalized = normalize_youtube_url(standard_url)
    assert normalized == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_parse_playwright_proxy():
    from src.utils.helpers import parse_playwright_proxy, format_proxy_display

    # Com autenticação
    p1 = parse_playwright_proxy("http://alice:secret123@proxy.com:8080")
    assert p1 == {"server": "http://proxy.com:8080", "username": "alice", "password": "secret123"}
    assert format_proxy_display("http://alice:secret123@proxy.com:8080") == "http://alice:***@proxy.com:8080"

    # Sem protocolo explícito
    p2 = parse_playwright_proxy("bob:pass@192.168.1.50:3128")
    assert p2 == {"server": "http://192.168.1.50:3128", "username": "bob", "password": "pass"}

    # SOCKS5
    p3 = parse_playwright_proxy("socks5://127.0.0.1:1080")
    assert p3 == {"server": "socks5://127.0.0.1:1080"}
    assert "username" not in p3
    assert format_proxy_display("socks5://127.0.0.1:1080") == "socks5://127.0.0.1:1080"

    # String vazia ou None
    assert parse_playwright_proxy("") is None
    assert parse_playwright_proxy(None) is None
    assert format_proxy_display(None) == "Conexão Direta (Local)"


def test_rotate_proxy_session():
    from src.utils.helpers import rotate_proxy_session

    original = "http://dummyuser__cr.br__sessid.worker4:dummypassword@gw.dataimpulse.com:823"
    rotated1 = rotate_proxy_session(original, worker_id=4)
    assert rotated1 != original
    assert "sessid.w4_" in rotated1
    assert "dummyuser__cr.br__" in rotated1
    assert "gw.dataimpulse.com:823" in rotated1

    rotated2 = rotate_proxy_session(rotated1, worker_id=4)
    assert rotated2 != rotated1
    assert "sessid.w4_" in rotated2


