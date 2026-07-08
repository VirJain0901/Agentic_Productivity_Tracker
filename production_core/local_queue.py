"""Durable local sync queue adapter for the production path."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .events import SyncResult


@dataclass(frozen=True)
class QueueRecord:
    event_id: str
    payload: dict
    status: str
    retry_count: int
    last_error: str
    available_at: str = ""
    lease_until: str = ""


class LocalEventQueue:
    """SQLite-backed queue with explicit dead-letter state.

    This is a standalone adapter. It does not replace the intern sync client
    until a human-reviewed integration wires it in.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS local_events (
                    event_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    available_at TEXT NOT NULL DEFAULT '',
                    lease_until TEXT NOT NULL DEFAULT ''
                )
                """
            )
            existing_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(local_events)").fetchall()
            }
            if "available_at" not in existing_columns:
                conn.execute("ALTER TABLE local_events ADD COLUMN available_at TEXT NOT NULL DEFAULT ''")
            if "lease_until" not in existing_columns:
                conn.execute("ALTER TABLE local_events ADD COLUMN lease_until TEXT NOT NULL DEFAULT ''")
            conn.commit()

    def enqueue(self, event_id: str, payload: dict) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO local_events
                    (event_id, payload_json, status, retry_count, last_error, available_at, lease_until)
                VALUES (?, ?, 'pending', 0, '', '', '')
                """,
                (event_id, json.dumps(payload, sort_keys=True)),
            )
            conn.commit()

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("queue timestamps must be timezone-aware")
        return value.isoformat()

    @staticmethod
    def _row_to_record(row: sqlite3.Row | tuple) -> QueueRecord:
        return QueueRecord(
            event_id=row[0],
            payload=json.loads(row[1]),
            status=row[2],
            retry_count=row[3],
            last_error=row[4],
            available_at=row[5],
            lease_until=row[6],
        )

    def get(self, event_id: str) -> QueueRecord:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT event_id, payload_json, status, retry_count, last_error, available_at, lease_until
                FROM local_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
        if row is None:
            raise KeyError(event_id)
        return self._row_to_record(row)

    def abandon_expired_leases(self, now: datetime) -> int:
        now_iso = self._iso(now)
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE local_events
                SET status = 'pending', lease_until = ''
                WHERE status = 'in_progress'
                  AND lease_until != ''
                  AND lease_until <= ?
                """,
                (now_iso,),
            )
            conn.commit()
            return cursor.rowcount

    def lease_pending(self, limit: int, now: datetime, lease_seconds: int) -> list[QueueRecord]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

        self.abandon_expired_leases(now)
        now_iso = self._iso(now)
        lease_until = self._iso(now + timedelta(seconds=lease_seconds))
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT event_id, payload_json, status, retry_count, last_error, available_at, lease_until
                FROM local_events
                WHERE status = 'pending'
                  AND (available_at = '' OR available_at <= ?)
                ORDER BY rowid
                LIMIT ?
                """,
                (now_iso, limit),
            ).fetchall()
            event_ids = [row[0] for row in rows]
            for event_id in event_ids:
                conn.execute(
                    """
                    UPDATE local_events
                    SET status = 'in_progress', lease_until = ?
                    WHERE event_id = ? AND status = 'pending'
                    """,
                    (lease_until, event_id),
                )
            conn.commit()

        return [self.get(event_id) for event_id in event_ids]

    def mark_retry(
        self,
        event_id: str,
        error: str,
        now: datetime,
        base_delay_seconds: int = 30,
        max_retries: int = 5,
    ) -> QueueRecord:
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be non-negative")

        current = self.get(event_id)
        retry_count = current.retry_count + 1
        if retry_count >= max_retries:
            status = "dead_letter"
            available_at = ""
        else:
            status = "pending"
            delay = base_delay_seconds * (2 ** (retry_count - 1))
            available_at = self._iso(now + timedelta(seconds=delay))

        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE local_events
                SET status = ?,
                    retry_count = ?,
                    last_error = ?,
                    available_at = ?,
                    lease_until = ''
                WHERE event_id = ?
                """,
                (status, retry_count, error, available_at, event_id),
            )
            conn.commit()
        return self.get(event_id)

    def stats(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM local_events GROUP BY status ORDER BY status"
            ).fetchall()
        return {status: count for status, count in rows}

    def apply_sync_result(self, result: SyncResult) -> None:
        with closing(self._connect()) as conn:
            for event_id in result.accepted + result.duplicates:
                conn.execute(
                    """
                    UPDATE local_events
                    SET status = 'synced',
                        last_error = '',
                        available_at = '',
                        lease_until = ''
                    WHERE event_id = ?
                    """,
                    (event_id,),
                )
            for rejected in result.rejected:
                conn.execute(
                    """
                    UPDATE local_events
                    SET status = 'dead_letter',
                        retry_count = retry_count + 1,
                        last_error = ?,
                        available_at = '',
                        lease_until = ''
                    WHERE event_id = ?
                    """,
                    (rejected.get("error", ""), rejected.get("event_id")),
                )
            conn.commit()
