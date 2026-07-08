import sys
import unittest
from datetime import timedelta


class DashboardSurfaceTests(unittest.TestCase):
    def test_dashboard_denies_by_default_and_audits_sensitive_access(self):
        from production_core.dashboard import DashboardProjection, DashboardService, DeviceHealth
        from production_core.governance import AuditLog
        from production_core.identity import IdentityStore, Role, utcnow

        identity = IdentityStore()
        tenant = identity.create_tenant("Acme School", "education")
        person = identity.create_person(tenant.id, "Avery", "student-1")
        device = identity.create_device(tenant.id, person.id, "lab-01")
        admin = identity.create_membership(tenant.id, "admin-1", Role.TENANT_ADMIN)
        monitored_person = identity.create_membership(tenant.id, "student-user-1", Role.MONITORED_PERSON)
        audit = AuditLog()
        service = DashboardService(audit_log=audit)
        projection = DashboardProjection(
            tenant_id=tenant.id,
            source="live",
            devices=[
                DeviceHealth(
                    tenant_id=tenant.id,
                    person_id=person.id,
                    device_id=device.id,
                    hostname=device.hostname,
                    last_seen_at=utcnow(),
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                )
            ],
        )

        with self.assertRaises(PermissionError):
            service.overview(monitored_person, projection, now=utcnow())

        detail = service.person_detail(admin, projection, person.id, now=utcnow())

        self.assertEqual(person.id, detail.person_id)
        self.assertEqual(1, len(audit.entries))
        self.assertEqual("dashboard.person_detail.view", audit.entries[0].action)
        self.assertEqual(person.id, audit.entries[0].target_id)

    def test_dashboard_labels_sample_data_and_surfaces_device_health(self):
        from production_core.dashboard import DashboardProjection, DashboardService, DeviceHealth
        from production_core.governance import AuditLog
        from production_core.identity import UserMembership, Role, utcnow

        now = utcnow()
        projection = DashboardProjection(
            tenant_id="tenant-1",
            source="sample",
            devices=[
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-1",
                    device_id="device-1",
                    hostname="fresh",
                    last_seen_at=now - timedelta(minutes=2),
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                ),
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-2",
                    device_id="device-2",
                    hostname="stale",
                    last_seen_at=now - timedelta(minutes=45),
                    pending_events=3,
                    dead_letter_events=1,
                    policy_version="2026.06.20",
                ),
            ],
        )
        membership = UserMembership(
            id="membership-1",
            tenant_id="tenant-1",
            user_id="manager-1",
            role=Role.MANAGER,
        )

        overview = DashboardService(AuditLog()).overview(membership, projection, now=now)

        self.assertEqual("Sample data", overview.source_label)
        self.assertEqual(1, overview.device_status_counts["healthy"])
        self.assertEqual(1, overview.device_status_counts["offline"])
        self.assertEqual(1, overview.sync_failure_count)

    def test_scoped_dashboard_access_filters_overview_and_denies_other_person_details(self):
        from production_core.dashboard import DashboardProjection, DashboardService, DeviceHealth, PolicyStatus
        from production_core.governance import AuditLog
        from production_core.identity import UserMembership, Role, utcnow

        now = utcnow()
        projection = DashboardProjection(
            tenant_id="tenant-1",
            source="live",
            devices=[
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-a",
                    device_id="device-a",
                    hostname="class-a-device",
                    last_seen_at=now,
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                    scope_id="class-a",
                ),
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-b",
                    device_id="device-b",
                    hostname="class-b-device",
                    last_seen_at=now,
                    pending_events=7,
                    dead_letter_events=1,
                    policy_version="2026.06.20",
                    scope_id="class-b",
                ),
            ],
            policy_statuses=[
                PolicyStatus("tenant-1", "person-a", "2026.06.20", True, scope_id="class-a"),
                PolicyStatus("tenant-1", "person-b", "2026.06.20", True, scope_id="class-b"),
            ],
        )
        scoped_teacher = UserMembership(
            id="membership-1",
            tenant_id="tenant-1",
            user_id="teacher-1",
            role=Role.TEACHER,
            scope_id="class-a",
        )
        service = DashboardService(AuditLog())

        overview = service.overview(scoped_teacher, projection, now=now)

        self.assertEqual(1, overview.total_devices)
        self.assertEqual(1, overview.device_status_counts["healthy"])
        self.assertEqual(0, overview.sync_failure_count)
        self.assertEqual(1, overview.policy_acknowledged_count)

        with self.assertRaises(PermissionError):
            service.person_detail(scoped_teacher, projection, "person-b", now=now)


class OperationsReadinessTests(unittest.TestCase):
    def test_operations_module_does_not_import_django_settings(self):
        sys.modules.pop("employee_tracker.settings", None)

        import production_core.operations  # noqa: F401

        self.assertNotIn("employee_tracker.settings", sys.modules)

    def test_production_settings_validator_reports_deploy_blockers(self):
        from production_core.operations import validate_production_settings

        issues = validate_production_settings(
            {
                "DJANGO_DEBUG": True,
                "SECRET_KEY": "django-insecure-short",
                "SECURE_HSTS_SECONDS": 0,
                "SECURE_SSL_REDIRECT": False,
                "SESSION_COOKIE_SECURE": False,
                "CSRF_COOKIE_SECURE": False,
                "ALLOWED_HOSTS": [],
            }
        )
        codes = {issue.code for issue in issues}

        self.assertIn("debug_enabled", codes)
        self.assertIn("weak_secret_key", codes)
        self.assertIn("hsts_disabled", codes)
        self.assertIn("ssl_redirect_disabled", codes)
        self.assertIn("session_cookie_insecure", codes)
        self.assertIn("csrf_cookie_insecure", codes)
        self.assertIn("allowed_hosts_empty", codes)

        clean = validate_production_settings(
            {
                "DJANGO_DEBUG": False,
                "SECRET_KEY": "not-insecure-" + ("x" * 60),
                "SECURE_HSTS_SECONDS": 31536000,
                "SECURE_SSL_REDIRECT": True,
                "SESSION_COOKIE_SECURE": True,
                "CSRF_COOKIE_SECURE": True,
                "ALLOWED_HOSTS": ["app.example.com"],
            }
        )

        self.assertEqual([], clean)

    def test_redis_url_parser_preserves_auth_tls_and_db(self):
        from production_core.operations import parse_redis_url

        parsed = parse_redis_url("rediss://:secret@redis.example.com:6380/2")

        self.assertEqual("rediss", parsed.scheme)
        self.assertEqual("redis.example.com", parsed.host)
        self.assertEqual(6380, parsed.port)
        self.assertEqual("secret", parsed.password)
        self.assertEqual(2, parsed.db)
        self.assertTrue(parsed.tls)

    def test_operations_health_report_marks_down_services_as_down(self):
        from production_core.dashboard import DeviceHealth
        from production_core.identity import utcnow
        from production_core.operations import ServiceHealth, build_operations_health_report

        now = utcnow()
        report = build_operations_health_report(
            services=[
                ServiceHealth("database", "ok", checked_at=now),
                ServiceHealth("redis", "down", checked_at=now, message="connection refused"),
            ],
            devices=[
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-1",
                    device_id="device-healthy",
                    hostname="healthy",
                    last_seen_at=now,
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                )
            ],
            now=now,
        )

        self.assertEqual("down", report.overall_status)
        self.assertEqual(["redis"], report.down_services)
        self.assertEqual([], report.unhealthy_device_ids)

    def test_operations_health_report_surfaces_stale_and_sync_failed_devices(self):
        from datetime import timedelta

        from production_core.dashboard import DeviceHealth
        from production_core.identity import utcnow
        from production_core.operations import ServiceHealth, build_operations_health_report

        now = utcnow()
        report = build_operations_health_report(
            services=[ServiceHealth("database", "ok", checked_at=now)],
            devices=[
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-1",
                    device_id="device-stale",
                    hostname="stale",
                    last_seen_at=now - timedelta(minutes=20),
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                ),
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-2",
                    device_id="device-sync-failed",
                    hostname="sync-failed",
                    last_seen_at=now,
                    pending_events=0,
                    dead_letter_events=2,
                    policy_version="2026.06.20",
                ),
            ],
            now=now,
        )

        self.assertEqual("degraded", report.overall_status)
        self.assertEqual(["device-stale", "device-sync-failed"], report.unhealthy_device_ids)
        self.assertEqual({"healthy": 1, "stale": 1, "offline": 0}, report.device_status_counts)
