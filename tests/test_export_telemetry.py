from starlette.testclient import TestClient
from src.web.app import app


def test_export_runs_csv():
    client = TestClient(app)
    resp = client.get("/api/export/runs.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


def test_export_runs_json():
    client = TestClient(app)
    resp = client.get("/api/export/runs.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert "stats" in data


def test_telemetry_endpoint():
    client = TestClient(app)
    resp = client.get("/api/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "recent" in data
