import unittest


class V1ApiAdapterTests(unittest.TestCase):
    def test_health_payload_serializes_operations_report_and_validates_contract(self):
        from production_adapters.api_v1 import build_health_payload
        from production_core.dashboard import DeviceHealth
        from production_core.identity import utcnow
        from production_core.operations import ServiceHealth, build_operations_health_report

        now = utcnow()
        report = build_operations_health_report(
            services=[
                ServiceHealth("database", "ok", checked_at=now),
                ServiceHealth("redis", "degraded", checked_at=now, message="slow"),
            ],
            devices=[
                DeviceHealth(
                    tenant_id="tenant-1",
                    person_id="person-1",
                    device_id="device-1",
                    hostname="lab-01",
                    last_seen_at=now,
                    pending_events=0,
                    dead_letter_events=0,
                    policy_version="2026.06.20",
                )
            ],
            now=now,
        )

        payload = build_health_payload(report=report, source="live", checked_at=now)

        self.assertEqual("1.0", payload["schema_version"])
        self.assertEqual("degraded", payload["overall_status"])
        self.assertEqual(["redis"], payload["degraded_services"])
        self.assertEqual([], payload["unhealthy_device_ids"])

    def test_health_payload_rejects_sample_claimed_as_live_without_report(self):
        from production_adapters.api_v1 import build_health_payload
        from production_core.identity import utcnow

        with self.assertRaises(ValueError):
            build_health_payload(report=None, source="live", checked_at=utcnow())

    def test_sync_ack_payload_validates_result_contract(self):
        from production_adapters.api_v1 import build_sync_ack_payload
        from production_core.events import SyncResult

        payload = build_sync_ack_payload(
            SyncResult(
                accepted=["event-1"],
                duplicates=["event-2"],
                rejected=[{"event_id": "event-3", "error": "bad payload"}],
            )
        )

        self.assertEqual(["event-1"], payload["accepted"])
        self.assertEqual(["event-2"], payload["duplicates"])
        self.assertEqual("bad payload", payload["rejected"][0]["error"])
