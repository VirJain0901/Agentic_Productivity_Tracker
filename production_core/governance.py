"""Privacy, retention, consent, and immutable audit primitives."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from .identity import new_id


@dataclass(frozen=True)
class AuditEntry:
    id: str
    tenant_id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    occurred_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """Append-only audit log facade.

    A later database-backed integration should enforce immutability with DB
    permissions/triggers. This wrapper expresses and tests the invariant.
    """

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        occurred_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=new_id(),
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at,
            metadata=dict(metadata or {}),
        )
        self.entries.append(entry)
        return entry

    def update(self, entry_id: str, **changes: Any) -> None:
        raise PermissionError("Audit entries are append-only")

    def delete(self, entry_id: str) -> None:
        raise PermissionError("Audit entries are append-only")


@dataclass(frozen=True)
class ConsentRecord:
    id: str
    tenant_id: str
    person_id: str
    policy_version: str
    consent_basis: str
    captured_at: datetime


@dataclass(frozen=True)
class PolicyAcknowledgement:
    id: str
    tenant_id: str
    person_id: str
    policy_id: str
    policy_version: str
    acknowledged_at: datetime


@dataclass(frozen=True)
class RetentionPolicy:
    id: str
    tenant_id: str
    data_type: str
    retain_days: int
    legal_hold: bool = False

    def is_expired(self, created_at: datetime, now: datetime) -> bool:
        if self.legal_hold:
            return False
        return created_at + timedelta(days=self.retain_days) <= now


@dataclass(frozen=True)
class DataExportJob:
    id: str
    tenant_id: str
    requested_by: str
    status: str
    requested_at: datetime
    subject_person_id: str | None = None
    completed_at: datetime | None = None
    artifact_uri: str = ""


@dataclass(frozen=True)
class DeletionRequest:
    id: str
    tenant_id: str
    person_id: str
    requested_by: str
    status: str
    requested_at: datetime
    legal_hold: bool = False
    completed_at: datetime | None = None
    completed_by: str = ""


class GovernanceStore:
    def __init__(self, audit_log: AuditLog | None = None) -> None:
        self.audit_log = audit_log
        self.consent_records: list[ConsentRecord] = []
        self.policy_acknowledgements: list[PolicyAcknowledgement] = []
        self.retention_policies: list[RetentionPolicy] = []
        self.export_jobs: list[DataExportJob] = []
        self.deletion_requests: list[DeletionRequest] = []

    def _audit(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        occurred_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_log is None:
            return
        self.audit_log.record(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at,
            metadata=metadata,
        )

    def record_consent(
        self,
        tenant_id: str,
        person_id: str,
        policy_version: str,
        consent_basis: str,
        captured_at: datetime,
    ) -> ConsentRecord:
        record = ConsentRecord(
            id=new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            policy_version=policy_version,
            consent_basis=consent_basis,
            captured_at=captured_at,
        )
        self.consent_records.append(record)
        return record

    def record_policy_acknowledgement(
        self,
        tenant_id: str,
        person_id: str,
        policy_id: str,
        policy_version: str,
        acknowledged_at: datetime,
    ) -> PolicyAcknowledgement:
        acknowledgement = PolicyAcknowledgement(
            id=new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            policy_id=policy_id,
            policy_version=policy_version,
            acknowledged_at=acknowledged_at,
        )
        self.policy_acknowledgements.append(acknowledgement)
        return acknowledgement

    def create_retention_policy(
        self,
        tenant_id: str,
        data_type: str,
        retain_days: int,
        legal_hold: bool = False,
    ) -> RetentionPolicy:
        if retain_days < 0:
            raise ValueError("retain_days must be non-negative")
        policy = RetentionPolicy(
            id=new_id(),
            tenant_id=tenant_id,
            data_type=data_type,
            retain_days=retain_days,
            legal_hold=legal_hold,
        )
        self.retention_policies.append(policy)
        return policy

    def request_data_export(
        self,
        tenant_id: str,
        requested_by: str,
        requested_at: datetime,
        subject_person_id: str | None = None,
    ) -> DataExportJob:
        job = DataExportJob(
            id=new_id(),
            tenant_id=tenant_id,
            requested_by=requested_by,
            status="queued",
            requested_at=requested_at,
            subject_person_id=subject_person_id,
        )
        self.export_jobs.append(job)
        self._audit(
            tenant_id=tenant_id,
            actor_id=requested_by,
            action="data_export.request",
            target_type="data_export",
            target_id=job.id,
            occurred_at=requested_at,
            metadata={"subject_person_id": subject_person_id},
        )
        return job

    def complete_data_export(
        self,
        tenant_id: str,
        job_id: str,
        completed_at: datetime,
        artifact_uri: str,
    ) -> DataExportJob:
        if not artifact_uri.startswith("private://"):
            raise ValueError("artifact_uri must point to private storage")
        for index, job in enumerate(self.export_jobs):
            if job.id != job_id:
                continue
            if job.tenant_id != tenant_id:
                raise PermissionError("Data export job is outside tenant scope")
            completed = replace(job, status="completed", completed_at=completed_at, artifact_uri=artifact_uri)
            self.export_jobs[index] = completed
            self._audit(
                tenant_id=tenant_id,
                actor_id="system",
                action="data_export.complete",
                target_type="data_export",
                target_id=job_id,
                occurred_at=completed_at,
                metadata={"artifact_uri": artifact_uri},
            )
            return completed
        raise KeyError(job_id)

    def request_deletion(
        self,
        tenant_id: str,
        person_id: str,
        requested_by: str,
        requested_at: datetime,
        legal_hold: bool = False,
    ) -> DeletionRequest:
        request = DeletionRequest(
            id=new_id(),
            tenant_id=tenant_id,
            person_id=person_id,
            requested_by=requested_by,
            status="blocked_legal_hold" if legal_hold else "pending",
            requested_at=requested_at,
            legal_hold=legal_hold,
        )
        self.deletion_requests.append(request)
        self._audit(
            tenant_id=tenant_id,
            actor_id=requested_by,
            action="deletion.request",
            target_type="person",
            target_id=person_id,
            occurred_at=requested_at,
            metadata={"request_id": request.id, "legal_hold": legal_hold},
        )
        return request

    def complete_deletion(
        self,
        tenant_id: str,
        request_id: str,
        completed_at: datetime,
        completed_by: str,
    ) -> DeletionRequest:
        for index, request in enumerate(self.deletion_requests):
            if request.id != request_id:
                continue
            if request.tenant_id != tenant_id:
                raise PermissionError("Deletion request is outside tenant scope")
            if request.legal_hold:
                raise PermissionError("Deletion request is blocked by legal hold")
            completed = replace(
                request,
                status="completed",
                completed_at=completed_at,
                completed_by=completed_by,
            )
            self.deletion_requests[index] = completed
            self._audit(
                tenant_id=tenant_id,
                actor_id=completed_by,
                action="deletion.complete",
                target_type="person",
                target_id=request.person_id,
                occurred_at=completed_at,
                metadata={"request_id": request_id},
            )
            return completed
        raise KeyError(request_id)
