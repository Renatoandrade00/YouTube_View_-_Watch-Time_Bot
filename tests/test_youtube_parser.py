import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from src.youtube.parser import (
    is_playlist_url,
    is_channel_url,
    is_expandable_url,
    extract_direct_video_id,
    normalize_channel_url,
    extract_video_ids_from_html,
    expand_urls_list,
)
from src.web.app import app


def test_url_classification():
    # Playlists
    assert is_playlist_url("https://www.youtube.com/playlist?list=PL1234567890abcdef") is True
    assert is_playlist_url("https://youtube.com/watch?v=dQw4w9WgXcQ&list=PL1234567890abcdef") is True
    assert is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False

    # Channels
    assert is_channel_url("https://www.youtube.com/@CanalOficial") is True
    assert is_channel_url("https://www.youtube.com/@CanalOficial/videos") is True
    assert is_channel_url("https://www.youtube.com/channel/UC1234567890abcdef") is True
    assert is_channel_url("https://www.youtube.com/c/NomeCanal") is True
    assert is_channel_url("https://www.youtube.com/user/NomeCanal") is True
    assert is_channel_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False

    # Expandable
    assert is_expandable_url("https://www.youtube.com/playlist?list=PL123") is True
    assert is_expandable_url("https://www.youtube.com/@Canal/videos") is True
    assert is_expandable_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False


def test_extract_direct_video_id():
    assert extract_direct_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_direct_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_direct_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_direct_video_id("https://www.youtube.com/playlist?list=PL123") is None


def test_normalize_channel_url():
    assert normalize_channel_url("https://www.youtube.com/@Canal") == "https://www.youtube.com/@Canal/videos"
    assert normalize_channel_url("https://www.youtube.com/@Canal/videos") == "https://www.youtube.com/@Canal/videos"
    assert normalize_channel_url("https://www.youtube.com/channel/UC123/") == "https://www.youtube.com/channel/UC123/videos"


def test_extract_video_ids_from_html():
    sample_html = """
    <html>
      <script>
        var ytInitialData = {
          "contents": {
            "playlistVideoListRenderer": {
              "contents": [
                {"playlistVideoRenderer": {"videoId": "VID00000001", "title": "Video 1"}},
                {"playlistVideoRenderer": {"videoId": "VID00000002", "title": "Video 2"}},
                {"playlistVideoRenderer": {"videoId": "VID00000001", "title": "Video 1 duplicado"}}
              ]
            }
          }
        };
      </script>
    </html>
    """
    ids = extract_video_ids_from_html(sample_html)
    assert len(ids) == 2
    assert ids == ["VID00000001", "VID00000002"]


@pytest.mark.asyncio
async def test_expand_urls_list_mixed():
    mock_html = """
    <script>
      var ytInitialData = {
        "videoId": "EXTRAIDO001",
        "sub": {"videoId": "EXTRAIDO002"}
      };
    </script>
    """
    with patch("src.youtube.parser.fetch_html_httpx", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_html

        raw_list = [
            "https://www.youtube.com/watch?v=DIRETO_0001",
            "https://www.youtube.com/playlist?list=PLMOCK123",
            "https://www.youtube.com/watch?v=DIRETO_0002",
        ]

        expanded = await expand_urls_list(raw_list)

        # Deve conter o direto 1, os dois extraídos da playlist, e o direto 2
        assert "https://www.youtube.com/watch?v=DIRETO_0001" in expanded
        assert "https://www.youtube.com/watch?v=EXTRAIDO001" in expanded
        assert "https://www.youtube.com/watch?v=EXTRAIDO002" in expanded
        assert "https://www.youtube.com/watch?v=DIRETO_0002" in expanded
        assert len(expanded) == 4


def test_api_extract_videos_endpoint():
    client = TestClient(app)

    mock_html = """
    <script>
      var ytInitialData = {
        "item1": {"videoId": "ABCDEFGHIJ1"},
        "item2": {"videoId": "ABCDEFGHIJ2"}
      };
    </script>
    """
    with patch("src.youtube.parser.fetch_html_httpx", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_html

        resp = client.post("/api/extract-videos", json={"url": "https://www.youtube.com/playlist?list=PLTEST"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 2
        assert "https://www.youtube.com/watch?v=ABCDEFGHIJ1" in data["videos"]
        assert "https://www.youtube.com/watch?v=ABCDEFGHIJ2" in data["videos"]
