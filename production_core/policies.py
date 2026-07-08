"""Versioned monitoring policies and scoped assignments."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from .identity import ALLOWED_CHANNEL_SCOPES, new_id


ALLOWED_POLICY_SCOPES = ALLOWED_CHANNEL_SCOPES - {"device"}


@dataclass(frozen=True)
class MonitoringPolicy:
    tenant_id: str
    policy_id: str
    title: str
    version: str
    rules: dict[str, Any]
    status: str
    created_by: str
    created_at: datetime
    published_by: str = ""
    published_at: datetime | None = None


@dataclass(frozen=True)
class PolicyAssignment:
    tenant_id: str
    policy_id: str
    version: str
    scope_kind: str
    scope_id: str
    assigned_by: str
    assigned_at: datetime


class PolicyService:
    def __init__(self) -> None:
        self.policies: dict[tuple[str, str, str], MonitoringPolicy] = {}
        self.assignments: list[PolicyAssignment] = []

    @staticmethod
    def _policy_key(tenant_id: str, policy_id: str, version: str) -> tuple[str, str, str]:
        return tenant_id, policy_id, version

    @staticmethod
    def _validate_scope(scope_kind: str, scope_id: str) -> None:
        if scope_kind not in ALLOWED_POLICY_SCOPES:
            raise ValueError(f"Unsupported policy scope: {scope_kind}")
        if scope_kind != "tenant" and not scope_id.strip():
            raise ValueError("scope_id is required for non-tenant policy assignments")

    def create_policy(
        self,
        tenant_id: str,
        title: str,
        version: str,
        rules: dict[str, Any],
        created_by: str,
        created_at: datetime,
    ) -> MonitoringPolicy:
        if not title.strip():
            raise ValueError("title is required")
        if not version.strip():
            raise ValueError("version is required")
        if not isinstance(rules, dict):
            raise ValueError("rules must be an object")

        policy = MonitoringPolicy(
            tenant_id=tenant_id,
            policy_id=new_id(),
            title=title,
            version=version,
            rules=dict(rules),
            status="draft",
            created_by=created_by,
            created_at=created_at,
        )
        self.policies[self._policy_key(tenant_id, policy.policy_id, version)] = policy
        return policy

    def publish_policy(
        self,
        tenant_id: str,
        policy_id: str,
        version: str,
        published_by: str,
        published_at: datetime,
    ) -> MonitoringPolicy:
        key = self._policy_key(tenant_id, policy_id, version)
        policy = self.policies[key]
        published = replace(
            policy,
            status="published",
            published_by=published_by,
            published_at=published_at,
        )
        self.policies[key] = published
        return published

    def assign_policy(
        self,
        tenant_id: str,
        policy_id: str,
        version: str,
        scope_kind: str,
        scope_id: str,
        assigned_by: str,
        assigned_at: datetime,
    ) -> PolicyAssignment:
        self._validate_scope(scope_kind, scope_id)
        policy = self.policies[self._policy_key(tenant_id, policy_id, version)]
        if policy.status != "published":
            raise PermissionError("Only published policy versions can be assigned")

        assignment = PolicyAssignment(
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=version,
            scope_kind=scope_kind,
            scope_id=scope_id,
            assigned_by=assigned_by,
            assigned_at=assigned_at,
        )
        self.assignments.append(assignment)
        return assignment

    def current_policy_for_scope(
        self,
        tenant_id: str,
        scope_kind: str,
        scope_id: str,
    ) -> MonitoringPolicy | None:
        self._validate_scope(scope_kind, scope_id)
        for assignment in reversed(self.assignments):
            if (
                assignment.tenant_id == tenant_id
                and assignment.scope_kind == scope_kind
                and assignment.scope_id == scope_id
            ):
                return self.policies[self._policy_key(tenant_id, assignment.policy_id, assignment.version)]
        return None
