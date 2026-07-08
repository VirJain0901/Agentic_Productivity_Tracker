import sqlite3
import uuid
import json
from datetime import datetime, UTC, timedelta

MAX_RETRIES = 3
DB_NAME = "sync_queue.db"


def _get_conn():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def initialize_db():
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sync_queue (
        event_id        TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL,
        event_type      TEXT NOT NULL,
        payload         TEXT NOT NULL,
        status          TEXT NOT NULL,
        retry_count     INTEGER DEFAULT 0,
        next_retry_time TEXT,
        last_error      TEXT,
        created_at      TEXT,
        captured_at     TEXT
    )
    """)

    try:
        cursor.execute("ALTER TABLE sync_queue ADD COLUMN captured_at TEXT")
    except Exception:
        pass  

    conn.commit()
    conn.close()


def add_event(event_type, payload, captured_at=None):
    conn = _get_conn()
    cursor = conn.cursor()

    event_id        = str(uuid.uuid4())
    idempotency_key = f"{event_type}_{event_id}"
    now             = datetime.now(UTC).isoformat()

    cap = captured_at or now

    cursor.execute("""
    INSERT INTO sync_queue (
        event_id,
        idempotency_key,
        event_type,
        payload,
        status,
        retry_count,
        created_at,
        captured_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        idempotency_key,
        event_type,
        json.dumps(payload),
        "pending",
        0,
        now,
        cap,
    ))

    conn.commit()
    conn.close()
    return event_id


def get_pending_events(limit=10):
    conn = _get_conn()
    cursor = conn.cursor()

    current_time = datetime.now(UTC).isoformat()

    cursor.execute("""
    SELECT *
    FROM sync_queue
    WHERE status = ?
    AND (
        next_retry_time IS NULL
        OR next_retry_time <= ?
    )
    LIMIT ?
    """, ("pending", current_time, limit))

    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_in_progress(event_id):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE sync_queue
    SET status = ?
    WHERE event_id = ?
    """, ("in_progress", event_id))
    conn.commit()
    conn.close()


def mark_synced(event_id):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE sync_queue
    SET status = ?
    WHERE event_id = ?
    """, ("synced", event_id))
    conn.commit()
    conn.close()


def move_to_dead_letter(event_id, reason):
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE sync_queue
    SET status     = ?,
        last_error = ?
    WHERE event_id = ?
    """, ("dead_letter", reason, event_id))
    conn.commit()
    conn.close()


def increment_retry(event_id, error_message):
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT retry_count FROM sync_queue WHERE event_id = ?
    """, (event_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return

    retry_count = row["retry_count"] + 1

    if retry_count >= MAX_RETRIES:
        cursor.execute("""
        UPDATE sync_queue
        SET status      = ?,
            retry_count = ?,
            last_error  = ?
        WHERE event_id  = ?
        """, (
            "dead_letter",
            retry_count,
            error_message,         
            event_id,
        ))
    else:
        next_retry = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        cursor.execute("""
        UPDATE sync_queue
        SET retry_count     = ?,
            last_error      = ?,
            next_retry_time = ?
        WHERE event_id      = ?
        """, (retry_count, error_message, next_retry, event_id))

    conn.commit()
    conn.close()


def get_queue_stats():
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT status, COUNT(*)
    FROM sync_queue
    GROUP BY status
    """)
    stats = cursor.fetchall()
    conn.close()
    return stats


def process_ack(event_id, ack_status, reason=None):
    """
    Handle backend ACK responses.
    accepted  -> synced
    duplicate -> synced
    rejected  -> dead_letter with actual reason
    """
    if ack_status in ("accepted", "duplicate"):
        mark_synced(event_id)

    elif ack_status == "rejected":
        move_to_dead_letter(
            event_id,
            reason or "backend rejected event",   
        )

    else:
        raise ValueError(f"Unknown ACK status: {ack_status}")


def fetch_and_lock_events(limit=10):
    conn = _get_conn()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE")
        now = datetime.now(UTC).isoformat()

        cursor.execute("""
            SELECT * FROM sync_queue
            WHERE status = 'pending'
            AND (
                next_retry_time IS NULL
                OR next_retry_time <= ?
                )
                ORDER BY created_at ASC
                LIMIT ?
            """, (now, limit))

        rows = cursor.fetchall()

        for row in rows:
            cursor.execute("""
                UPDATE sync_queue
                SET status = 'in_progress'
                WHERE event_id = ?
            """, (row["event_id"],))

        conn.commit()
        return [dict(r) for r in rows]

    except Exception:
        conn.rollback()
        return []

    finally:
        conn.close()


def mark_screenshot_synced(event_id):
    """Mark a screenshot event as synced after successful upload."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE sync_queue
    SET status     = 'synced',
        last_error = NULL
    WHERE event_id = ?
    """, (event_id,))
    conn.commit()
    conn.close()


def mark_screenshot_retry(event_id, reason):
    """Schedule a screenshot for retry after a failed upload."""
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT retry_count FROM sync_queue WHERE event_id = ?
    """, (event_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return

    retry_count = row["retry_count"] + 1
    if retry_count >= MAX_RETRIES:
        cursor.execute("""
        UPDATE sync_queue
        SET status      = 'dead_letter',
            retry_count = ?,
            last_error  = ?
        WHERE event_id  = ?
        """, (retry_count, reason, event_id))
    else:
        next_retry = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        cursor.execute("""
        UPDATE sync_queue
        SET status          = 'pending',
            retry_count     = ?,
            last_error      = ?,
            next_retry_time = ?
        WHERE event_id      = ?
        """, (retry_count, reason, next_retry, event_id))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    initialize_db()

    event_id = add_event(
        "heartbeat",
        {"device_id": "DEV001"},
    )
    print("Created:", event_id)

    process_ack(event_id, "rejected", "Invalid payload")

    print("\nQueue Stats:")
    print(get_queue_stats())