import asyncio
import hashlib
import logging
import random
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiofiles
import aiohttp
from decouple import config
from local_queue import get_queue_stats as local_queue_stats

from local_queue import (
    fetch_and_lock_events,
    mark_in_progress,
    mark_synced,
    move_to_dead_letter,
    increment_retry,
    mark_screenshot_synced,
    mark_screenshot_retry,
)

logger = logging.getLogger("sync.engine")

BACKEND_URL     = config("BACKEND_SYNC_URL",        default="http://localhost:8000/api/activity-sync/")
SCREENSHOT_URL  = config("BACKEND_SCREENSHOT_URL",  default="http://localhost:8000/api/screenshots/")
SYNC_INTERVAL   = int(config("SYNC_INTERVAL_SECONDS", default="30"))
BATCH_SIZE      = int(config("SYNC_BATCH_SIZE",       default="50"))
MAX_RETRY       = int(config("MAX_RETRY_COUNT",        default="5"))
CLIENT_VERSION  = config("CLIENT_VERSION",  default="1.2.0")
SCHEMA_VERSION  = config("SCHEMA_VERSION",  default="1.0")
TENANT_ID       = config("TENANT_ID",       default="")
DEVICE_ID       = config("DEVICE_ID",       default="")

_JWT_ACCESS      = config("JWT_TOKEN",           default="")
_JWT_REFRESH     = config("JWT_REFRESH_TOKEN",   default="")
JWT_REFRESH_URL  = config("JWT_REFRESH_URL",     default="http://localhost:8000/api/token/refresh/")
JWT_REFRESH_SECS = int(config("JWT_REFRESH_INTERVAL", default="300"))


class JWTManager:
    """
    Holds the current access + refresh tokens.
    Refreshes proactively every JWT_REFRESH_SECS seconds,
    and reactively on any 401 response.
    Token VALUES are never written to any log.
    """

    def __init__(self) -> None:
        self._access: str  = _JWT_ACCESS
        self._refresh: str = _JWT_REFRESH
        self._last_refresh = datetime.now(tz=timezone.utc)

    def auth_headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._access:
            h["Authorization"] = f"Bearer {self._access}"
        return h

    def multipart_headers(self) -> dict[str, str]:
        """No Content-Type — aiohttp sets it automatically for FormData."""
        h: dict[str, str] = {}
        if self._access:
            h["Authorization"] = f"Bearer {self._access}"
        return h

    def needs_refresh(self) -> bool:
        elapsed = (datetime.now(tz=timezone.utc) - self._last_refresh).total_seconds()
        return elapsed >= JWT_REFRESH_SECS

    async def refresh(self, session: aiohttp.ClientSession) -> bool:
        if not self._refresh:
            logger.warning("jwt: no refresh token configured")
            return False
        try:
            async with session.post(
                JWT_REFRESH_URL,
                json={"refresh": self._refresh},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    self._access  = body.get("access",  self._access)
                    self._refresh = body.get("refresh", self._refresh)
                    self._last_refresh = datetime.now(tz=timezone.utc)
                    logger.info("jwt: token refreshed successfully")
                    return True
                logger.warning("jwt: refresh failed status=%d", resp.status)
                return False
        except Exception as exc:
            logger.error("jwt: refresh exception type=%s", type(exc).__name__)
            return False


jwt = JWTManager()


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _backoff(attempt: int) -> float:
    return min(60.0, (2 ** attempt) + random.random())


def _sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_batch(events: list[dict]) -> dict[str, Any]:
    """
    Spec-required envelope:
        tenant_id, device_id, client_version, schema_version,
        batch_id, generated_at, events[]
    """
    tenant = TENANT_ID or str(events[0].get("tenant_id", ""))
    device = DEVICE_ID or str(events[0].get("device_id", ""))

    return {
        "tenant_id":      tenant,
        "device_id":      device,
        "client_version": CLIENT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "batch_id":       str(uuid.uuid4()),
        "generated_at":   _utcnow(),
        "events": [
            {
                "event_id":        str(e["event_id"]),
                "schema_version":  e.get("schema_version", SCHEMA_VERSION),
                "idempotency_key": str(e["idempotency_key"]),
                "event_type":      e["event_type"],
                "tenant_id":       str(e["tenant_id"]),
                "device_id":       str(e["device_id"]),
                "user_id":         e.get("user_id", ""),
                "source_module":   e.get("source_module", ""),
                "created_at":      e["created_at"].isoformat() if hasattr(e.get("created_at"), "isoformat") else str(e.get("created_at", "")),
                "captured_at":     e["captured_at"].isoformat() if hasattr(e.get("captured_at"), "isoformat") else str(e.get("captured_at", "")),
                "payload":         e.get("payload_json") or {},
            }
            for e in events
        ],
    }


def queue_row_to_event(row):
    """
    Convert SQLite queue row into the format expected by build_batch().
    """
    return {
        "event_id":        row["event_id"],
        "idempotency_key": row["idempotency_key"],
        "event_type":      row["event_type"],
        "payload_json":    json.loads(row["payload"]),
        "status":          row["status"],
        "tenant_id":       TENANT_ID,
        "device_id":       DEVICE_ID,
        "schema_version":  SCHEMA_VERSION,
        "created_at":      row["created_at"],
        "captured_at":     row["captured_at"] or row["created_at"],
    }


def handle_ack(ack: dict) -> None:
    """
    accepted   → mark_synced
    duplicates → mark_synced  (idempotent — treat as success)
    rejected   → move_to_dead_letter with backend's actual reason
    """
    batch_id = ack.get("batch_id", "unknown")

    for eid in ack.get("accepted", []):
        mark_synced(str(eid))
        logger.info("ack: accepted event_id=%s batch=%s", eid, batch_id)

    for eid in ack.get("duplicates", []):
        mark_synced(str(eid))
        logger.info("ack: duplicate→synced event_id=%s batch=%s", eid, batch_id)

    for item in ack.get("rejected", []):
        eid    = str(item.get("event_id", ""))
        reason = str(item.get("reason", "rejected"))
        move_to_dead_letter(eid, reason)
        logger.warning("ack: rejected event_id=%s reason=%s batch=%s", eid, reason, batch_id)


async def send_events(session: aiohttp.ClientSession, events: list[dict]) -> None:
    if not events:
        return

    batch     = build_batch(events)
    batch_id  = batch["batch_id"]
    event_ids = [str(e["event_id"]) for e in events]

    for eid in event_ids:
        mark_in_progress(eid)

    try:
        async with session.post(
            BACKEND_URL,
            json=batch,
            headers=jwt.auth_headers(),
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:

            if resp.status == 401:
                logger.warning("send_events: 401 — refreshing token batch=%s", batch_id)
                if await jwt.refresh(session):
                    async with session.post(
                        BACKEND_URL,
                        json=batch,
                        headers=jwt.auth_headers(),
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as retry_resp:
                        resp = retry_resp
                else:
                    for eid in event_ids:
                        increment_retry(eid, "401 token refresh failed")
                    return

            if resp.status not in (200, 201, 202, 207):
                logger.warning("send_events: http %d batch=%s", resp.status, batch_id)
                for eid in event_ids:
                    increment_retry(eid, f"http {resp.status}")
                return

            try:
                ack = await resp.json()
            except Exception:
                logger.error("send_events: unparseable ack batch=%s", batch_id)
                for eid in event_ids:
                    increment_retry(eid, "invalid ack response")
                return

            handle_ack(ack)

    except aiohttp.ClientConnectorError:
        logger.warning("send_events: network offline batch=%s", batch_id)
        for eid in event_ids:
            increment_retry(eid, "connection refused")

    except asyncio.TimeoutError:
        logger.warning("send_events: timeout batch=%s", batch_id)
        for eid in event_ids:
            increment_retry(eid, "request timeout")

    except Exception as exc:
        logger.error("send_events: unexpected type=%s batch=%s", type(exc).__name__, batch_id)
        for eid in event_ids:
            increment_retry(eid, f"unexpected: {type(exc).__name__}")


async def sync_loop() -> None:
    logger.info("sync_loop: starting interval=%ds batch_size=%d", SYNC_INTERVAL, BATCH_SIZE)

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:

        if jwt.needs_refresh():
            await jwt.refresh(session)

        while True:
            try:
                if jwt.needs_refresh():
                    await jwt.refresh(session)

                raw_events = fetch_and_lock_events(limit=BATCH_SIZE)
                events = [queue_row_to_event(row) for row in raw_events]

                if events:
                    logger.info("sync_loop: %d events queued", len(events))
                    await send_events(session, events)

            except Exception as exc:
                logger.error("sync_loop: unhandled type=%s", type(exc).__name__)

            await asyncio.sleep(SYNC_INTERVAL)


def start() -> None:
    """Blocking entry point — run in a daemon thread."""
    asyncio.run(sync_loop())


def get_queue_stats() -> dict:
    """Status breakdown from local SQLite queue."""
    stats = local_queue_stats()
    return {status: count for status, count in stats}


if __name__ == "__main__":
    print("Sync Manager Started")
    events = fetch_and_lock_events(limit=5)
    print(f"Found {len(events)} pending events")
    for event in events:
        print(event)