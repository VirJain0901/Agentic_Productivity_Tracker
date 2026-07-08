"""Tenant-scoped dashboard projection and access primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from .governance import AuditLog
from .identity import Role, UserMembership


DashboardSource = Literal["live", "sample"]
ALLOWED_DASHBOARD_ROLES = {
    Role.TENANT_ADMIN,
    Role.MANAGER,
    Role.TEACHER,
    Role.COMPLIANCE_AUDITOR,
}


@dataclass(frozen=True)
class DeviceHealth:
    tenant_id: str
    person_id: str
    device_id: str
    hostname: str
    last_seen_at: datetime | None
    pending_events: int
    dead_letter_events: int
    policy_version: str
    scope_id: str | None = None

    def status(self, now: datetime) -> str:
        if self.last_seen_at is None:
            return "offline"
        age = now - self.last_seen_at
        if age <= timedelta(minutes=5):
            return "healthy"
        if age <= timedelta(minutes=30):
            return "stale"
        return "offline"

    @property
    def has_sync_failure(self) -> bool:
        return self.pending_events > 0 or self.dead_letter_events > 0


@dataclass(frozen=True)
class SyncFailure:
    tenant_id: str
    device_id: str
    event_id: str
    reason: str


@dataclass(frozen=True)
class PolicyStatus:
    tenant_id: str
    person_id: str
    policy_version: str
    acknowledged: bool
    scope_id: str | None = None


@dataclass(frozen=True)
class DashboardProjection:
    tenant_id: str
    source: DashboardSource
    devices: list[DeviceHealth] = field(default_factory=list)
    sync_failures: list[SyncFailure] = field(default_factory=list)
    policy_statuses: list[PolicyStatus] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardOverview:
    tenant_id: str
    source_label: str
    total_devices: int
    device_status_counts: dict[str, int]
    sync_failure_count: int
    policy_acknowledged_count: int


@dataclass(frozen=True)
class PersonDashboardDetail:
    tenant_id: str
    person_id: str
    source_label: str
    devices: list[DeviceHealth]
    policy_statuses: list[PolicyStatus]


class DashboardService:
    """Access-checked dashboard service for future Django wiring."""

    def __init__(self, audit_log: AuditLog) -> None:
        self.audit_log = audit_log

    def _require_dashboard_access(self, membership: UserMembership, tenant_id: str) -> None:
        if membership.tenant_id != tenant_id:
            raise PermissionError("Dashboard access denied across tenants")
        if membership.role not in ALLOWED_DASHBOARD_ROLES:
            raise PermissionError("Dashboard access denied for role")

    @staticmethod
    def _source_label(projection: DashboardProjection) -> str:
        return "Sample data" if projection.source == "sample" else "Live data"

    @staticmethod
    def _in_membership_scope(membership: UserMembership, scope_id: str | None) -> bool:
        if membership.role == Role.TENANT_ADMIN:
            return True
        if membership.scope_id is None:
            return True
        return scope_id == membership.scope_id

    def overview(
        self,
        membership: UserMembership,
        projection: DashboardProjection,
        now: datetime,
    ) -> DashboardOverview:
        self._require_dashboard_access(membership, projection.tenant_id)
        counts = {"healthy": 0, "stale": 0, "offline": 0}
        scoped_devices = [
            device
            for device in projection.devices
            if self._in_membership_scope(membership, device.scope_id)
        ]
        for device in scoped_devices:
            if device.tenant_id != projection.tenant_id:
                raise PermissionError("Projection contains data from another tenant")
            counts[device.status(now)] += 1

        direct_failures = len(
            [
                failure
                for failure in projection.sync_failures
                if failure.tenant_id == projection.tenant_id
                and any(device.device_id == failure.device_id for device in scoped_devices)
            ]
        )
        device_failures = len([device for device in scoped_devices if device.has_sync_failure])

        return DashboardOverview(
            tenant_id=projection.tenant_id,
            source_label=self._source_label(projection),
            total_devices=len(scoped_devices),
            device_status_counts=counts,
            sync_failure_count=max(direct_failures, device_failures),
            policy_acknowledged_count=len(
                [
                    status
                    for status in projection.policy_statuses
                    if status.tenant_id == projection.tenant_id
                    and status.acknowledged
                    and self._in_membership_scope(membership, status.scope_id)
                ]
            ),
        )

    def person_detail(
        self,
        membership: UserMembership,
        projection: DashboardProjection,
        person_id: str,
        now: datetime,
    ) -> PersonDashboardDetail:
        self._require_dashboard_access(membership, projection.tenant_id)
        devices = [
            device
            for device in projection.devices
            if device.tenant_id == projection.tenant_id
            and device.person_id == person_id
            and self._in_membership_scope(membership, device.scope_id)
        ]
        policy_statuses = [
            status
            for status in projection.policy_statuses
            if status.tenant_id == projection.tenant_id
            and status.person_id == person_id
            and self._in_membership_scope(membership, status.scope_id)
        ]
        if membership.role != Role.TENANT_ADMIN and membership.scope_id is not None and not devices and not policy_statuses:
            raise PermissionError("Person detail access denied outside membership scope")

        self.audit_log.record(
            tenant_id=projection.tenant_id,
            actor_id=membership.user_id,
            action="dashboard.person_detail.view",
            target_type="person",
            target_id=person_id,
            occurred_at=now,
            metadata={"source": projection.source},
        )
        return PersonDashboardDetail(
            tenant_id=projection.tenant_id,
            person_id=person_id,
            source_label=self._source_label(projection),
            devices=devices,
            policy_statuses=policy_statuses,
        )
