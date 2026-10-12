import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.utils.db import DatabaseManager
from src.web.app import app
from src.web.state import StateManager


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_history.db"
    # Reseta singleton para usar banco temporário
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance(db_path=db_file)
    yield db
    DatabaseManager.reset_instance()


def test_db_save_and_query_run(temp_db):
    run_data = {
        "started_at": "2026-10-12 10:00:00",
        "finished_at": "2026-10-12 10:30:00",
        "duration_seconds": 1800.0,
        "target_watch_time": 3600.0,
        "actual_watch_time": 1750.5,
        "total_views": 10,
        "successful_views": 9,
        "blocked_views": 1,
        "failed_views": 0,
        "ads_skipped": 5,
        "continue_clicked": 2,
        "workers": 3,
        "urls_count": 4,
        "status": "COMPLETED",
        "summary_message": "Rodada finalizada com sucesso.",
    }
    sessions = [
        {
            "session_id": 1,
            "worker_id": 1,
            "url": "https://www.youtube.com/watch?v=video1",
            "target_watch_time": 180.0,
            "actual_watch_time": 180.0,
            "ads_skipped": 1,
            "continue_clicked": 0,
            "status": "SUCCESS",
            "error_message": None,
            "started_at": "2026-10-12 10:00:05",
            "finished_at": "2026-10-12 10:03:05",
        },
        {
            "session_id": 2,
            "worker_id": 2,
            "url": "https://www.youtube.com/watch?v=video2",
            "target_watch_time": 180.0,
            "actual_watch_time": 5.0,
            "ads_skipped": 0,
            "continue_clicked": 0,
            "status": "BLOCKED",
            "error_message": "CAPTCHA detectado",
            "started_at": "2026-10-12 10:00:10",
            "finished_at": "2026-10-12 10:00:15",
        },
    ]

    run_id = temp_db.save_run(run_data, sessions)
    assert run_id > 0

    all_runs = temp_db.get_all_runs()
    assert len(all_runs) == 1
    assert all_runs[0]["id"] == run_id
    assert all_runs[0]["workers"] == 3
    assert all_runs[0]["total_views"] == 10

    details = temp_db.get_run_details(run_id)
    assert details is not None
    assert details["id"] == run_id
    assert len(details["sessions"]) == 2
    assert details["sessions"][0]["status"] == "SUCCESS"
    assert details["sessions"][1]["status"] == "BLOCKED"
    assert details["sessions"][1]["error_message"] == "CAPTCHA detectado"


def test_db_summary_stats(temp_db):
    temp_db.save_run(
        {
            "started_at": "2026-10-12 10:00:00",
            "finished_at": "2026-10-12 10:10:00",
            "duration_seconds": 600.0,
            "actual_watch_time": 3600.0,
            "total_views": 10,
            "successful_views": 8,
            "blocked_views": 1,
            "failed_views": 1,
            "ads_skipped": 4,
            "continue_clicked": 1,
        }
    )
    temp_db.save_run(
        {
            "started_at": "2026-10-12 11:00:00",
            "finished_at": "2026-10-12 11:10:00",
            "duration_seconds": 600.0,
            "actual_watch_time": 1800.0,
            "total_views": 10,
            "successful_views": 10,
            "blocked_views": 0,
            "failed_views": 0,
            "ads_skipped": 2,
            "continue_clicked": 0,
        }
    )

    stats = temp_db.get_run_summary_stats()
    assert stats["total_runs"] == 2
    assert stats["total_watch_hours"] == 1.5  # (3600 + 1800) / 3600 = 1.5h
    assert stats["total_views"] == 20
    assert stats["successful_views"] == 18
    assert stats["success_rate"] == 90.0  # 18 / 20 * 100
    assert stats["total_ads_skipped"] == 6
    assert stats["total_continue_clicked"] == 1


def test_db_delete_and_clear(temp_db):
    r1 = temp_db.save_run({"total_views": 5}, [{"url": "http://v1"}])
    r2 = temp_db.save_run({"total_views": 8}, [{"url": "http://v2"}])

    assert len(temp_db.get_all_runs()) == 2
    deleted = temp_db.delete_run(r1)
    assert deleted is True
    assert len(temp_db.get_all_runs()) == 1

    cleared = temp_db.clear_history()
    assert cleared == 1
    assert len(temp_db.get_all_runs()) == 0


def test_state_manager_auto_save_run(temp_db):
    sm = StateManager.get_instance()
    sm.start_run(num_workers=2, urls_count=3, target_duration_hours=0.5)

    class MockMetric:
        session_id = 1
        worker_id = 1
        url = "https://youtube.com/watch?v=abc"
        target_watch_time = 120.0
        actual_watch_time = 120.0
        ads_skipped = 1
        continue_dialogs_clicked = 1
        status = "SUCCESS"
        error_message = None
        started_at = "2026-10-12 12:00:00"
        finished_at = "2026-10-12 12:02:00"

    sm.update_metrics(MockMetric())
    sm.finish_run(reason="Rodada concluída com sucesso.")

    runs = temp_db.get_all_runs()
    assert len(runs) >= 1
    latest = runs[0]
    assert latest["total_views"] == 1
    assert latest["successful_views"] == 1
    assert latest["actual_watch_time"] == 120.0
    assert latest["status"] == "COMPLETED"


def test_history_api_endpoints(temp_db):
    temp_db.save_run(
        {
            "started_at": "2026-10-12 08:00:00",
            "duration_seconds": 120.0,
            "actual_watch_time": 100.0,
            "total_views": 2,
            "successful_views": 2,
            "status": "COMPLETED",
        },
        [
            {
                "session_id": 1,
                "worker_id": 1,
                "url": "https://youtube.com/watch?v=xyz",
                "target_watch_time": 60.0,
                "actual_watch_time": 50.0,
                "status": "SUCCESS",
            }
        ],
    )

    client = TestClient(app)

    # GET /api/history
    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert "runs" in data
    assert "stats" in data
    assert len(data["runs"]) >= 1
    run_id = data["runs"][0]["id"]

    # GET /api/history/{run_id}
    res_detail = client.get(f"/api/history/{run_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == run_id
    assert len(detail["sessions"]) == 1

    # DELETE /api/history/{run_id}
    res_del = client.delete(f"/api/history/{run_id}")
    assert res_del.status_code == 200

    # DELETE 404
    res_del_404 = client.delete(f"/api/history/{run_id}")
    assert res_del_404.status_code == 404

    # DELETE /api/history
    res_clear = client.delete("/api/history")
    assert res_clear.status_code == 200
