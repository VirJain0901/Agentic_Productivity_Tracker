"""Validated client event envelopes and sync acknowledgement handling."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .contracts import validate_contract_payload


SUPPORTED_EVENT_TYPES = {
    "activity",
    "idle",
    "session.start",
    "session.end",
    "heartbeat",
    "policy",
    "sync_error",
}


@dataclass(frozen=True)
class ClientEventEnvelope:
    schema_version: str
    tenant_id: str
    device_id: str
    event_id: str
    idempotency_key: str
    event_type: str
    occurred_at: datetime
    captured_at: datetime
    payload: dict[str, Any]


@dataclass
class SyncResult:
    accepted: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class DeadLetter:
    tenant_id: str
    device_id: str
    event_id: str
    idempotency_key: str
    error: str


class EventStore:
    """Append-only event store with tenant/device scoped idempotency."""

    def __init__(self) -> None:
        self.events: list[ClientEventEnvelope] = []
        self.dead_letters: list[DeadLetter] = []
        self._event_keys: set[tuple[str, str, str]] = set()
        self._idempotency_keys: set[tuple[str, str]] = set()

    def is_duplicate(self, envelope: ClientEventEnvelope) -> bool:
        event_key = (envelope.tenant_id, envelope.device_id, envelope.event_id)
        idempotency_key = (envelope.tenant_id, envelope.idempotency_key)
        return event_key in self._event_keys or idempotency_key in self._idempotency_keys

    def append(self, envelope: ClientEventEnvelope) -> None:
        self.events.append(envelope)
        self._event_keys.add((envelope.tenant_id, envelope.device_id, envelope.event_id))
        self._idempotency_keys.add((envelope.tenant_id, envelope.idempotency_key))

    def dead_letter(self, envelope: ClientEventEnvelope, error: str) -> None:
        self.dead_letters.append(
            DeadLetter(
                tenant_id=envelope.tenant_id,
                device_id=envelope.device_id,
                event_id=envelope.event_id,
                idempotency_key=envelope.idempotency_key,
                error=error,
            )
        )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_client_event_payload(payload: dict[str, Any]) -> ClientEventEnvelope:
    validate_contract_payload("client_event", payload)
    envelope = ClientEventEnvelope(
        schema_version=payload["schema_version"],
        tenant_id=payload["tenant_id"],
        device_id=payload["device_id"],
        event_id=payload["event_id"],
        idempotency_key=payload["idempotency_key"],
        event_type=payload["event_type"],
        occurred_at=_parse_datetime(payload["occurred_at"]),
        captured_at=_parse_datetime(payload["captured_at"]),
        payload=dict(payload["payload"]),
    )
    validate_event_envelope(envelope)
    return envelope


def _require(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def validate_event_envelope(envelope: ClientEventEnvelope) -> None:
    if envelope.schema_version != "1.0":
        raise ValueError("Unsupported schema_version")
    _require(envelope.tenant_id, "tenant_id")
    _require(envelope.device_id, "device_id")
    _require(envelope.event_id, "event_id")
    _require(envelope.idempotency_key, "idempotency_key")

    try:
        uuid.UUID(envelope.event_id)
    except ValueError as exc:
        raise ValueError("event_id must be a UUID") from exc

    if envelope.event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(f"Unsupported event_type: {envelope.event_type}")

    _require_aware(envelope.occurred_at, "occurred_at")
    _require_aware(envelope.captured_at, "captured_at")

    if envelope.captured_at < envelope.occurred_at:
        raise ValueError("captured_at cannot be before occurred_at")
    if envelope.occurred_at > datetime.now(timezone.utc):
        raise ValueError("occurred_at cannot be in the future")
    if not isinstance(envelope.payload, dict):
        raise ValueError("payload must be an object")


def sync_events(store: EventStore, envelopes: list[ClientEventEnvelope]) -> SyncResult:
    result = SyncResult()
    for envelope in envelopes:
        try:
            validate_event_envelope(envelope)
            if store.is_duplicate(envelope):
                result.duplicates.append(envelope.event_id)
                continue
            store.append(envelope)
            result.accepted.append(envelope.event_id)
        except ValueError as exc:
            error = str(exc)
            store.dead_letter(envelope, error)
            result.rejected.append({"event_id": envelope.event_id, "error": error})
    return result
