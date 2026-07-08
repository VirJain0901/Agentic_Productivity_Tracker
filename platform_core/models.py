from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class Tenant(models.Model):
    class Edition(models.TextChoices):
        EDUCATION = "education", "Education"
        WORKFORCE = "workforce", "Workforce"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    edition = models.CharField(max_length=20, choices=Edition.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Person(models.Model):
    class Kind(models.TextChoices):
        STUDENT = "student", "Student"
        EMPLOYEE = "employee", "Employee"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="persons")
    display_name = models.CharField(max_length=200)
    external_ref = models.CharField(max_length=160)
    person_kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.OTHER)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "external_ref"], name="platform_person_tenant_external_ref_uniq"),
        ]
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name


class Device(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        QUARANTINED = "quarantined", "Quarantined"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="devices")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="devices")
    hostname = models.CharField(max_length=255)
    device_key = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "device_key"], name="platform_device_tenant_key_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "last_seen_at"], name="platform_device_last_seen_idx"),
        ]
        ordering = ["hostname"]

    def __str__(self) -> str:
        return self.hostname


class Membership(models.Model):
    class Role(models.TextChoices):
        TENANT_ADMIN = "tenant_admin", "Tenant admin"
        MANAGER = "manager", "Manager"
        TEACHER = "teacher", "Teacher"
        COMPLIANCE_AUDITOR = "compliance_auditor", "Compliance auditor"
        MONITORED_PERSON = "monitored_person", "Monitored person"
        DEVICE_SERVICE_ACCOUNT = "device_service_account", "Device service account"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user_id = models.CharField(max_length=160)
    role = models.CharField(max_length=40, choices=Role.choices)
    scope_kind = models.CharField(max_length=40, blank=True, default="")
    scope_id = models.CharField(max_length=160, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user_id", "role", "scope_kind", "scope_id"],
                name="platform_membership_scope_uniq",
            ),
        ]


class EnrollmentToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="enrollment_tokens")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="enrollment_tokens")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="enrollment_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.CharField(max_length=160)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        indexes = [
            models.Index(fields=["tenant", "device", "expires_at"], name="platform_enroll_lookup_idx"),
        ]


class DeviceCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="device_credentials")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="device_credentials")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="credentials")
    secret_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "platform_core"
        indexes = [
            models.Index(fields=["tenant", "device", "revoked_at"], name="platform_cred_lookup_idx"),
        ]

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_entries")
    actor_id = models.CharField(max_length=160)
    action = models.CharField(max_length=160)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=160)
    occurred_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        indexes = [
            models.Index(fields=["tenant", "occurred_at"], name="platform_audit_time_idx"),
            models.Index(fields=["tenant", "target_type", "target_id"], name="platform_audit_target_idx"),
        ]


class Policy(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="policies")
    title = models.CharField(max_length=200)
    version = models.CharField(max_length=80)
    rules = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.CharField(max_length=160)
    created_at = models.DateTimeField(default=timezone.now)
    published_by = models.CharField(max_length=160, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "platform_core"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "title", "version"], name="platform_policy_version_uniq"),
        ]


class PolicyAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="policy_assignments")
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="assignments")
    scope_kind = models.CharField(max_length=40)
    scope_id = models.CharField(max_length=160)
    assigned_by = models.CharField(max_length=160)
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "platform_core"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "scope_kind", "scope_id"], name="platform_policy_scope_uniq"),
        ]
