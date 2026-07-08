import sys
import os
sys.path.insert(0, os.path.dirname(__file__))  
import pytest
import local_queue


@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    db = str(tmp_path / "test_queue.db")
    monkeypatch.setenv("LOCAL_QUEUE_DB", db)
    monkeypatch.setattr(local_queue, "DB_NAME", db)
    local_queue.initialize_db()
    yield db


# Test 1 — add_event creates a pending row
def test_add_event_creates_pending():
    eid = local_queue.add_event("keystroke", {"key_count": 10})
    assert eid is not None
    stats = dict(local_queue.get_queue_stats())
    assert stats.get("pending") == 1


# Test 2 — fetch_and_lock moves rows to in_progress atomically
def test_fetch_and_lock_marks_in_progress():
    local_queue.add_event("heartbeat", {"device": "DEV001"})
    rows = local_queue.fetch_and_lock_events(limit=10)
    assert len(rows) == 1
    import sqlite3
    conn = sqlite3.connect(local_queue.DB_NAME)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM sync_queue WHERE event_id = ?",
        (rows[0]["event_id"],)
    ).fetchone()
    conn.close()
    assert row["status"] == "in_progress"
    rows2 = local_queue.fetch_and_lock_events(limit=10)
    assert len(rows2) == 0


# Test 3 — process_ack accepted → synced
def test_process_ack_accepted():
    eid = local_queue.add_event("app_usage", {"app": "Chrome"})
    local_queue.process_ack(eid, "accepted")
    stats = dict(local_queue.get_queue_stats())
    assert stats.get("synced") == 1
    assert stats.get("pending", 0) == 0


# Test 4 — process_ack duplicate → synced
def test_process_ack_duplicate_treated_as_synced():
    eid = local_queue.add_event("app_usage", {"app": "VS Code"})
    local_queue.process_ack(eid, "duplicate")
    stats = dict(local_queue.get_queue_stats())
    assert stats.get("synced") == 1


# Test 5 — process_ack rejected → dead_letter with actual reason
def test_process_ack_rejected_stores_reason():
    eid = local_queue.add_event("keystroke", {"key_count": 5})
    local_queue.process_ack(eid, "rejected", "Invalid payload schema")
    stats = dict(local_queue.get_queue_stats())
    assert stats.get("dead_letter") == 1
    import sqlite3
    conn = sqlite3.connect(local_queue.DB_NAME)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT last_error FROM sync_queue WHERE event_id = ?", (eid,)
    ).fetchone()
    conn.close()
    assert row["last_error"] == "Invalid payload schema"