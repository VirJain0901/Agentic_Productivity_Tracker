"""Tenant, person, device, and role primitives for the production path."""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


SAFE_CHANNEL_PART = re.compile(r"^[A-Za-z0-9_-]+$")
ALLOWED_CHANNEL_SCOPES = {"tenant", "team", "class", "person", "device"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


def new_secret() -> str:
    return secrets.token_urlsafe(32)


class Role(str, Enum):
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    TEACHER = "teacher"
    COMPLIANCE_AUDITOR = "compliance_auditor"
    MONITORED_PERSON = "monitored_person"
    DEVICE_SERVICE_ACCOUNT = "device_service_account"


@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    edition: str


@dataclass(frozen=True)
class Person:
    id: str
    tenant_id: str
    display_name: str
    external_ref: str


@dataclass(frozen=True)
class Device:
    id: str
    tenant_id: str
    person_id: str
    hostname: str


@dataclass(frozen=True)
class UserMembership:
    id: str
    tenant_id: str
    user_id: str
    role: Role
    scope_id: str | None = None


@dataclass
class EnrollmentToken:
    id: str
    tenant_id: str
    person_id: str
    device_id: str
    secret: str
    expires_at: datetime
    used_at: datetime | None = None


@dataclass
class DeviceCredential:
    id: str
    tenant_id: str
    person_id: str
    device_id: str
    secret: str
    issued_at: datetime
    revoked: bool = False


def _assert_tenant_exists(tenants: dict[str, Tenant], tenant_id: str) -> None:
    if tenant_id not in tenants:
        raise KeyError(f"Unknown tenant: {tenant_id}")


def _assert_safe_channel_part(value: str) -> None:
    if not SAFE_CHANNEL_PART.match(value):
        raise ValueError(f"Unsafe channel segment: {value}")


def tenant_channel_name(tenant_id: str, scope_kind: str = "tenant", scope_id: str | None = None) -> str:
    if scope_kind not in ALLOWED_CHANNEL_SCOPES:
        raise ValueError(f"Unsupported realtime scope: {scope_kind}")
    _assert_safe_channel_part(tenant_id)
    if scope_kind == "tenant":
        return f"tenant_{tenant_id}"
    if not scope_id:
        raise ValueError("scope_id is required for non-tenant channels")
    _assert_safe_channel_part(scope_id)
    return f"tenant_{tenant_id}_{scope_kind}_{scope_id}"


def can_access_person(
    memberships: list[UserMembership],
    person: Person,
    action: str,
    scope_id: str | None = None,
) -> bool:
    for membership in memberships:
        if membership.tenant_id != person.tenant_id:
            continue
        if membership.role == Role.TENANT_ADMIN:
            return True
        if action == "view" and membership.role in {Role.MANAGER, Role.TEACHER, Role.COMPLIANCE_AUDITOR}:
            if membership.scope_id is None or membership.scope_id == scope_id:
                return True
    return False


class IdentityStore:
    """Small in-memory identity service for adapters and tests.

    This deliberately avoids touching the existing Django models. A later
    human-reviewed integration can port these invariants into real models.
    """

    def __init__(self) -> None:
        self.tenants: dict[str, Tenant] = {}
        self.persons: dict[str, Person] = {}
        self.devices: dict[str, Device] = {}
        self.memberships: dict[str, UserMembership] = {}
        self.enrollment_tokens: dict[str, EnrollmentToken] = {}
        self.credentials: dict[str, DeviceCredential] = {}

    def create_tenant(self, name: str, edition: str) -> Tenant:
        if edition not in {"education", "workforce"}:
            raise ValueError("edition must be education or workforce")
        tenant = Tenant(id=new_id(), name=name, edition=edition)
        self.tenants[tenant.id] = tenant
        return tenant

    def create_person(self, tenant_id: str, display_name: str, external_ref: str) -> Person:
        _assert_tenant_exists(self.tenants, tenant_id)
        person = Person(id=new_id(), tenant_id=tenant_id, display_name=display_name, external_ref=external_ref)
        self.persons[person.id] = person
        return person

    def create_device(self, tenant_id: str, person_id: str, hostname: str) -> Device:
        _assert_tenant_exists(self.tenants, tenant_id)
        person = self.persons[person_id]
        if person.tenant_id != tenant_id:
            raise PermissionError("Device person does not belong to tenant")
        device = Device(id=new_id(), tenant_id=tenant_id, person_id=person_id, hostname=hostname)
        self.devices[device.id] = device
        return device

    def create_membership(
        self,
        tenant_id: str,
        user_id: str,
        role: Role,
        scope_id: str | None = None,
    ) -> UserMembership:
        _assert_tenant_exists(self.tenants, tenant_id)
        membership = UserMembership(id=new_id(), tenant_id=tenant_id, user_id=user_id, role=role, scope_id=scope_id)
        self.memberships[membership.id] = membership
        return membership

    def issue_enrollment_token(
        self,
        tenant_id: str,
        person_id: str,
        device_id: str,
        expires_at: datetime,
    ) -> EnrollmentToken:
        _assert_tenant_exists(self.tenants, tenant_id)
        person = self.persons[person_id]
        device = self.devices[device_id]
        if person.tenant_id != tenant_id or device.tenant_id != tenant_id or device.person_id != person_id:
            raise PermissionError("Enrollment target is outside tenant scope")
        token = EnrollmentToken(
            id=new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            device_id=device_id,
            secret=new_secret(),
            expires_at=expires_at,
        )
        self.enrollment_tokens[token.secret] = token
        return token

    def enroll_device(self, token_secret: str) -> DeviceCredential:
        token = self.enrollment_tokens.get(token_secret)
        if token is None:
            raise PermissionError("Invalid enrollment token")
        if token.used_at is not None:
            raise PermissionError("Enrollment token has already been used")
        if token.expires_at <= utcnow():
            raise PermissionError("Enrollment token has expired")

        token.used_at = utcnow()
        credential = DeviceCredential(
            id=new_id(),
            tenant_id=token.tenant_id,
            person_id=token.person_id,
            device_id=token.device_id,
            secret=new_secret(),
            issued_at=utcnow(),
        )
        self.credentials[credential.id] = credential
        return credential

    def authenticate_device(self, tenant_id: str, device_id: str, secret: str) -> DeviceCredential:
        for credential in self.credentials.values():
            if (
                credential.tenant_id == tenant_id
                and credential.device_id == device_id
                and credential.secret == secret
                and not credential.revoked
            ):
                return credential
        raise PermissionError("Invalid or revoked device credential")

    def revoke_device_credential(self, credential_id: str) -> None:
        credential = self.credentials[credential_id]
        credential.revoked = True
