"""Gated screenshot metadata registry and access log.

This module does not stream, upload, or read screenshot binaries. It records
private object metadata only after the screenshot legal gate is open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .governance import AuditLog
from .identity import new_id
from .legal_gate import FeatureGate, GatedFeature


SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class ScreenshotObject:
    tenant_id: str
    screenshot_id: str
    device_id: str
    person_id: str
    storage_key: str
    captured_at: datetime
    content_sha256: str
    byte_size: int
    retention_days: int
    legal_hold: bool = False

    def is_expired(self, now: datetime) -> bool:
        if self.legal_hold:
            return False
        return self.captured_at + timedelta(days=self.retention_days) <= now


@dataclass(frozen=True)
class ScreenshotAccess:
    tenant_id: str
    screenshot_id: str
    actor_id: str
    purpose: str
    accessed_at: datetime


class ScreenshotRegistry:
    def __init__(self, feature_gate: FeatureGate, audit_log: AuditLog) -> None:
        self.feature_gate = feature_gate
        self.audit_log = audit_log
        self.objects: dict[str, ScreenshotObject] = {}
        self.access_log: list[ScreenshotAccess] = []

    def register_object(
        self,
        tenant_id: str,
        device_id: str,
        person_id: str,
        captured_at: datetime,
        content_sha256: str,
        byte_size: int,
        retention_days: int,
        legal_hold: bool = False,
    ) -> ScreenshotObject:
        self.feature_gate.require_allowed(GatedFeature.SCREENSHOT_STREAMING, tenant_id=tenant_id)
        if not SHA256_RE.match(content_sha256):
            raise ValueError("content_sha256 must be a 64-character hex digest")
        if byte_size <= 0:
            raise ValueError("byte_size must be positive")
        if retention_days < 0:
            raise ValueError("retention_days must be non-negative")

        screenshot_id = new_id()
        screenshot = ScreenshotObject(
            tenant_id=tenant_id,
            screenshot_id=screenshot_id,
            device_id=device_id,
            person_id=person_id,
            storage_key=f"tenants/{tenant_id}/screenshots/{screenshot_id}.bin",
            captured_at=captured_at,
            content_sha256=content_sha256.lower(),
            byte_size=byte_size,
            retention_days=retention_days,
            legal_hold=legal_hold,
        )
        self.objects[screenshot_id] = screenshot
        self.audit_log.record(
            tenant_id=tenant_id,
            actor_id=device_id,
            action="screenshot.register",
            target_type="screenshot",
            target_id=screenshot_id,
            occurred_at=captured_at,
            metadata={"person_id": person_id, "byte_size": byte_size},
        )
        return screenshot

    def record_access(
        self,
        tenant_id: str,
        screenshot_id: str,
        actor_id: str,
        purpose: str,
        accessed_at: datetime,
    ) -> ScreenshotAccess:
        self.feature_gate.require_allowed(GatedFeature.SCREENSHOT_STREAMING, tenant_id=tenant_id)
        screenshot = self.objects[screenshot_id]
        if screenshot.tenant_id != tenant_id:
            raise PermissionError("Screenshot access is outside tenant scope")
        if screenshot.is_expired(now=accessed_at):
            raise PermissionError("Screenshot is expired by retention policy")
        if not purpose.strip():
            raise ValueError("purpose is required")

        access = ScreenshotAccess(
            tenant_id=tenant_id,
            screenshot_id=screenshot_id,
            actor_id=actor_id,
            purpose=purpose,
            accessed_at=accessed_at,
        )
        self.access_log.append(access)
        self.audit_log.record(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="screenshot.access",
            target_type="screenshot",
            target_id=screenshot_id,
            occurred_at=accessed_at,
            metadata={"purpose": purpose},
        )
        return access
