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
