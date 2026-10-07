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
