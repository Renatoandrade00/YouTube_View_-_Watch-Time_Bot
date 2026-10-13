import pytest
from starlette.testclient import TestClient
from src.web.app import app
from src.web.state import StateManager


@pytest.fixture
def client():
    return TestClient(app)


def test_get_status_initial(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_running" in data
    assert "workers" in data
    assert "metrics" in data


def test_get_default_urls(client):
    response = client.get("/api/default-urls")
    assert response.status_code == 200
    data = response.json()
    assert "urls" in data
    assert isinstance(data["urls"], list)


def test_index_html_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "YouTube Watch-Time Bot" in response.text


def test_state_manager_singleton_and_worker_updates():
    sm = StateManager.get_instance()
    sm.init_workers(3)
    assert len(sm.workers) == 3

    sm.update_worker(
        worker_id=1,
        status="Assistindo",
        current_watch_time=30.0,
        target_watch_time=60.0
    )
    assert sm.workers[1].status == "Assistindo"
    assert sm.workers[1].progress_pct == 50.0


def test_bot_config_resolve_urls_from_list():
    from src.config import BotConfig
    cfg = BotConfig(urls_list=["https://www.youtube.com/watch?v=TESTE1", "https://www.youtube.com/watch?v=TESTE2"])
    resolved = cfg.resolve_urls()
    assert len(resolved) == 2
    assert "https://www.youtube.com/watch?v=TESTE1" in resolved


def test_get_default_proxies(client):
    response = client.get("/api/default-proxies")
    assert response.status_code == 200
    data = response.json()
    assert "proxies" in data
    assert isinstance(data["proxies"], list)


def test_state_manager_worker_proxy_info():
    sm = StateManager.get_instance()
    sm.init_workers(1)
    sm.update_worker(
        worker_id=1,
        proxy_info="http://user:***@proxy.com:8000"
    )
    assert sm.workers[1].proxy_info == "http://user:***@proxy.com:8000"


def test_duration_slider_limit_24h_in_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="duration-slider"' in response.text
    assert 'max="24"' in response.text


def test_start_bot_request_duration_hours_limits():
    from src.web.app import StartBotRequest
    # 24h deve ser aceito normalmente
    req_24 = StartBotRequest(
        urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
        duration_hours=24.0,
    )
    assert req_24.duration_hours == 24.0

    # Mais de 24h deve ser rejeitado pela validação
    with pytest.raises(Exception):
        StartBotRequest(
            urls=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            duration_hours=24.1,
        )


