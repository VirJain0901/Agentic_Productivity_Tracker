from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from . import models


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class IssuedEnrollmentToken:
    record: models.EnrollmentToken
    secret: str


@dataclass(frozen=True)
class IssuedDeviceCredential:
    record: models.DeviceCredential
    secret: str


class DeviceEnrollmentService:
    def issue_token(
        self,
        tenant: models.Tenant,
        person: models.Person,
        device: models.Device,
        expires_at: datetime,
        issued_by: str,
    ) -> IssuedEnrollmentToken:
        if person.tenant_id != tenant.id or device.tenant_id != tenant.id or device.person_id != person.id:
            raise PermissionError("Enrollment target is outside tenant scope")
        if expires_at <= timezone.now():
            raise ValueError("Enrollment token expiry must be in the future")

        secret = new_secret()
        record = models.EnrollmentToken.objects.create(
            tenant=tenant,
            person=person,
            device=device,
            token_hash=hash_secret(secret),
            expires_at=expires_at,
            issued_by=issued_by,
        )
        return IssuedEnrollmentToken(record=record, secret=secret)

    @transaction.atomic
    def enroll(self, secret: str) -> IssuedDeviceCredential:
        token_hash = hash_secret(secret)
        try:
            token = models.EnrollmentToken.objects.select_for_update().get(token_hash=token_hash)
        except models.EnrollmentToken.DoesNotExist as exc:
            raise PermissionError("Invalid enrollment token") from exc

        if token.used_at is not None:
            raise PermissionError("Enrollment token has already been used")
        if token.expires_at <= timezone.now():
            raise PermissionError("Enrollment token has expired")

        credential_secret = new_secret()
        credential = models.DeviceCredential.objects.create(
            tenant=token.tenant,
            person=token.person,
            device=token.device,
            secret_hash=hash_secret(credential_secret),
        )
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        return IssuedDeviceCredential(record=credential, secret=credential_secret)

    def authenticate(self, tenant_id: str, device_id: str, secret: str) -> models.DeviceCredential:
        try:
            return models.DeviceCredential.objects.get(
                tenant_id=tenant_id,
                device_id=device_id,
                secret_hash=hash_secret(secret),
                revoked_at__isnull=True,
            )
        except models.DeviceCredential.DoesNotExist as exc:
            raise PermissionError("Invalid or revoked device credential") from exc

    def revoke(self, credential: models.DeviceCredential) -> models.DeviceCredential:
        credential.revoked_at = timezone.now()
        credential.save(update_fields=["revoked_at"])
        return credential


class AuditLogService:
    def record(
        self,
        tenant: models.Tenant,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        occurred_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> models.AuditLog:
        return models.AuditLog.objects.create(
            tenant=tenant,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at,
            metadata=dict(metadata or {}),
        )

    def update(self, entry_id: str, **changes: Any) -> None:
        raise PermissionError("Audit entries are append-only")

    def delete(self, entry_id: str) -> None:
        raise PermissionError("Audit entries are append-only")


class PolicyPersistenceService:
    def publish(self, policy: models.Policy, published_by: str, published_at: datetime) -> models.Policy:
        policy.status = models.Policy.Status.PUBLISHED
        policy.published_by = published_by
        policy.published_at = published_at
        policy.save(update_fields=["status", "published_by", "published_at"])
        return policy

    def assign(
        self,
        tenant: models.Tenant,
        policy: models.Policy,
        scope_kind: str,
        scope_id: str,
        assigned_by: str,
        assigned_at: datetime,
    ) -> models.PolicyAssignment:
        if policy.tenant_id != tenant.id:
            raise PermissionError("Policy is outside tenant scope")
        if policy.status != models.Policy.Status.PUBLISHED:
            raise PermissionError("Only published policies can be assigned")
        return models.PolicyAssignment.objects.create(
            tenant=tenant,
            policy=policy,
            scope_kind=scope_kind,
            scope_id=scope_id,
            assigned_by=assigned_by,
            assigned_at=assigned_at,
        )
