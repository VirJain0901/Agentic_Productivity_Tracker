import json
import os
import unittest


def _django_ready():
    try:
        import django
    except ImportError:
        raise unittest.SkipTest("Django is not installed")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "employee_tracker.settings")
    django.setup()


class PlatformApiViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _django_ready()

    def test_health_view_returns_contract_payload(self):
        from django.test import RequestFactory
        from platform_api.views import health_view

        response = health_view(RequestFactory().get("/api/v1/health/"))
        payload = json.loads(response.content.decode("utf-8"))

        self.assertEqual(200, response.status_code)
        self.assertEqual("1.0", payload["schema_version"])
        self.assertEqual("sample", payload["source"])
        self.assertEqual("degraded", payload["overall_status"])

    def test_activity_sync_view_accepts_valid_events_and_rejects_invalid_events(self):
        from django.test import RequestFactory
        from platform_api.views import activity_sync_view
        from production_core.identity import new_id

        event_id = new_id()
        body = {
            "events": [
                {
                    "schema_version": "1.0",
                    "tenant_id": "tenant-1",
                    "device_id": "device-1",
                    "event_id": event_id,
                    "idempotency_key": f"device-1:{event_id}",
                    "event_type": "activity",
                    "occurred_at": "2026-06-20T10:00:00+00:00",
                    "captured_at": "2026-06-20T10:00:01+00:00",
                    "payload": {"app_name": "code.exe"},
                },
                {
                    "schema_version": "1.0",
                    "tenant_id": "tenant-1",
                    "device_id": "device-1",
                    "event_id": new_id(),
                    "idempotency_key": "device-1:bad",
                    "event_type": "unknown",
                    "occurred_at": "2026-06-20T10:00:00+00:00",
                    "captured_at": "2026-06-20T10:00:01+00:00",
                    "payload": {},
                },
            ]
        }

        response = activity_sync_view(
            RequestFactory().post(
                "/api/v1/sync/events/",
                data=json.dumps(body),
                content_type="application/json",
            )
        )
        payload = json.loads(response.content.decode("utf-8"))

        self.assertEqual(207, response.status_code)
        self.assertEqual([event_id], payload["accepted"])
        self.assertEqual(1, len(payload["rejected"]))

    def test_platform_api_urlpatterns_exist_without_project_url_wiring(self):
        from platform_api.urls import urlpatterns

        patterns = {pattern.name for pattern in urlpatterns}

        self.assertIn("platform-v1-health", patterns)
        self.assertIn("platform-v1-sync-events", patterns)
