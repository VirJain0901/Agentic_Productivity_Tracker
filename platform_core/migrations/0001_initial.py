from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("edition", models.CharField(choices=[("education", "Education"), ("workforce", "Workforce")], max_length=20)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("display_name", models.CharField(max_length=200)),
                ("external_ref", models.CharField(max_length=160)),
                ("person_kind", models.CharField(choices=[("student", "Student"), ("employee", "Employee"), ("other", "Other")], default="other", max_length=20)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="persons", to="platform_core.tenant")),
            ],
            options={"ordering": ["display_name"]},
        ),
        migrations.CreateModel(
            name="Device",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("hostname", models.CharField(max_length=255)),
                ("device_key", models.CharField(max_length=160)),
                ("status", models.CharField(choices=[("active", "Active"), ("quarantined", "Quarantined"), ("retired", "Retired")], default="active", max_length=20)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to="platform_core.person")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to="platform_core.tenant")),
            ],
            options={"ordering": ["hostname"]},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.CharField(max_length=160)),
                ("role", models.CharField(choices=[("tenant_admin", "Tenant admin"), ("manager", "Manager"), ("teacher", "Teacher"), ("compliance_auditor", "Compliance auditor"), ("monitored_person", "Monitored person"), ("device_service_account", "Device service account")], max_length=40)),
                ("scope_kind", models.CharField(blank=True, default="", max_length=40)),
                ("scope_id", models.CharField(blank=True, default="", max_length=160)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="platform_core.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="Policy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("version", models.CharField(max_length=80)),
                ("rules", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published"), ("retired", "Retired")], default="draft", max_length=20)),
                ("created_by", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("published_by", models.CharField(blank=True, default="", max_length=160)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="policies", to="platform_core.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("actor_id", models.CharField(max_length=160)),
                ("action", models.CharField(max_length=160)),
                ("target_type", models.CharField(max_length=80)),
                ("target_id", models.CharField(max_length=160)),
                ("occurred_at", models.DateTimeField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_entries", to="platform_core.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="EnrollmentToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("issued_by", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollment_tokens", to="platform_core.device")),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollment_tokens", to="platform_core.person")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enrollment_tokens", to="platform_core.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="DeviceCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("secret_hash", models.CharField(max_length=64, unique=True)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credentials", to="platform_core.device")),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="device_credentials", to="platform_core.person")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="device_credentials", to="platform_core.tenant")),
            ],
        ),
        migrations.CreateModel(
            name="PolicyAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_kind", models.CharField(max_length=40)),
                ("scope_id", models.CharField(max_length=160)),
                ("assigned_by", models.CharField(max_length=160)),
                ("assigned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("policy", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="platform_core.policy")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="policy_assignments", to="platform_core.tenant")),
            ],
        ),
        migrations.AddConstraint(model_name="person", constraint=models.UniqueConstraint(fields=("tenant", "external_ref"), name="platform_person_tenant_external_ref_uniq")),
        migrations.AddConstraint(model_name="device", constraint=models.UniqueConstraint(fields=("tenant", "device_key"), name="platform_device_tenant_key_uniq")),
        migrations.AddIndex(model_name="device", index=models.Index(fields=["tenant", "last_seen_at"], name="platform_device_last_seen_idx")),
        migrations.AddConstraint(model_name="membership", constraint=models.UniqueConstraint(fields=("tenant", "user_id", "role", "scope_kind", "scope_id"), name="platform_membership_scope_uniq")),
        migrations.AddConstraint(model_name="policy", constraint=models.UniqueConstraint(fields=("tenant", "title", "version"), name="platform_policy_version_uniq")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["tenant", "occurred_at"], name="platform_audit_time_idx")),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["tenant", "target_type", "target_id"], name="platform_audit_target_idx")),
        migrations.AddIndex(model_name="enrollmenttoken", index=models.Index(fields=["tenant", "device", "expires_at"], name="platform_enroll_lookup_idx")),
        migrations.AddIndex(model_name="devicecredential", index=models.Index(fields=["tenant", "device", "revoked_at"], name="platform_cred_lookup_idx")),
        migrations.AddConstraint(model_name="policyassignment", constraint=models.UniqueConstraint(fields=("tenant", "scope_kind", "scope_id"), name="platform_policy_scope_uniq")),
    ]
