import os
import unittest
from datetime import timedelta


def _django_ready():
    try:
        import django
    except ImportError:
        raise unittest.SkipTest("Django is not installed")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "employee_tracker.settings")

    django.setup()


class PlatformCoreModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _django_ready()

    def test_core_models_have_tenant_owned_constraints(self):
        from platform_core import models

        self.assertEqual("platform_core", models.Tenant._meta.app_label)
        self.assertEqual("tenant", models.Person._meta.get_field("tenant").remote_field.model._meta.model_name)
        self.assertEqual("person", models.Device._meta.get_field("person").remote_field.model._meta.model_name)

        person_unique = {tuple(constraint.fields) for constraint in models.Person._meta.constraints}
        device_unique = {tuple(constraint.fields) for constraint in models.Device._meta.constraints}
        membership_unique = {tuple(constraint.fields) for constraint in models.Membership._meta.constraints}

        self.assertIn(("tenant", "external_ref"), person_unique)
        self.assertIn(("tenant", "device_key"), device_unique)
        self.assertIn(("tenant", "user_id", "role", "scope_kind", "scope_id"), membership_unique)

    def test_enrollment_service_issues_one_time_credentials(self):
        from django.db import connection
        from django.utils import timezone
        from platform_core import models
        from platform_core.services import DeviceEnrollmentService

        created_models = [
            models.Tenant,
            models.Person,
            models.Device,
            models.EnrollmentToken,
            models.DeviceCredential,
        ]
        with connection.schema_editor() as schema:
            for model in created_models:
                schema.create_model(model)

        try:
            tenant = models.Tenant.objects.create(name="North School", edition=models.Tenant.Edition.EDUCATION)
            person = models.Person.objects.create(
                tenant=tenant,
                display_name="Asha Rao",
                external_ref="student-1",
                person_kind=models.Person.Kind.STUDENT,
            )
            device = models.Device.objects.create(
                tenant=tenant,
                person=person,
                hostname="lab-01",
                device_key="lab-01",
            )
            service = DeviceEnrollmentService()
            issued = service.issue_token(
                tenant=tenant,
                person=person,
                device=device,
                expires_at=timezone.now() + timedelta(minutes=10),
                issued_by="admin-1",
            )

            credential = service.enroll(secret=issued.secret)

            self.assertEqual(tenant.id, credential.record.tenant_id)
            self.assertEqual(device.id, credential.record.device_id)
            self.assertTrue(credential.secret)
            self.assertIsNotNone(models.EnrollmentToken.objects.get(id=issued.record.id).used_at)

            with self.assertRaises(PermissionError):
                service.enroll(secret=issued.secret)

            self.assertEqual(
                credential.record.id,
                service.authenticate(tenant_id=str(tenant.id), device_id=str(device.id), secret=credential.secret).id,
            )
        finally:
            with connection.schema_editor() as schema:
                for model in reversed(created_models):
                    schema.delete_model(model)

    def test_audit_log_service_is_append_only(self):
        from django.db import connection
        from django.utils import timezone
        from platform_core import models
        from platform_core.services import AuditLogService

        created_models = [models.Tenant, models.AuditLog]
        with connection.schema_editor() as schema:
            for model in created_models:
                schema.create_model(model)

        try:
            tenant = models.Tenant.objects.create(name="Acme", edition=models.Tenant.Edition.WORKFORCE)
            service = AuditLogService()
            entry = service.record(
                tenant=tenant,
                actor_id="admin-1",
                action="device.view",
                target_type="device",
                target_id="device-1",
                occurred_at=timezone.now(),
                metadata={"reason": "support"},
            )

            with self.assertRaises(PermissionError):
                service.update(entry.id, action="changed")
            with self.assertRaises(PermissionError):
                service.delete(entry.id)
        finally:
            with connection.schema_editor() as schema:
                for model in reversed(created_models):
                    schema.delete_model(model)
