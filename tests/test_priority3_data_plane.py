import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


class DataPlaneTests(unittest.TestCase):
    def test_envelope_requires_uuid_and_tenant_device_identity(self):
        from production_core.events import ClientEventEnvelope, validate_event_envelope
        from production_core.identity import utcnow

        envelope = ClientEventEnvelope(
            schema_version="1.0",
            tenant_id="tenant-1",
            device_id="device-1",
            event_id="not-a-uuid",
            idempotency_key="device-1:not-a-uuid",
            event_type="activity",
            occurred_at=utcnow(),
            captured_at=utcnow(),
            payload={"app_name": "code.exe", "duration_seconds": 30},
        )

        with self.assertRaises(ValueError):
            validate_event_envelope(envelope)

    def test_raw_client_event_payload_parses_through_contract_validation(self):
        from production_core.events import parse_client_event_payload
        from production_core.identity import new_id

        event_id = new_id()
        envelope = parse_client_event_payload(
            {
                "schema_version": "1.0",
                "tenant_id": "tenant-1",
                "device_id": "device-1",
                "event_id": event_id,
                "idempotency_key": f"device-1:{event_id}",
                "event_type": "activity",
                "occurred_at": "2026-06-20T10:00:00+00:00",
                "captured_at": "2026-06-20T10:00:01+00:00",
                "payload": {"app_name": "code.exe", "duration_seconds": 30},
            }
        )

        self.assertEqual(event_id, envelope.event_id)
        self.assertEqual("tenant-1", envelope.tenant_id)
        self.assertEqual("code.exe", envelope.payload["app_name"])

    def test_raw_client_event_payload_rejects_extra_fields_and_bad_times(self):
        from production_core.contracts import ContractValidationError
        from production_core.events import parse_client_event_payload
        from production_core.identity import new_id

        event_id = new_id()
        payload = {
            "schema_version": "1.0",
            "tenant_id": "tenant-1",
            "device_id": "device-1",
            "event_id": event_id,
            "idempotency_key": f"device-1:{event_id}",
            "event_type": "activity",
            "occurred_at": "2026-06-20T10:00:00+00:00",
            "captured_at": "2026-06-20T10:00:01+00:00",
            "payload": {},
            "unexpected": True,
        }

        with self.assertRaises(ContractValidationError):
            parse_client_event_payload(payload)

        payload.pop("unexpected")
        payload["captured_at"] = "2026-06-20T09:59:59+00:00"
        with self.assertRaises(ValueError):
            parse_client_event_payload(payload)

    def test_event_store_uses_composite_idempotency(self):
        from production_core.events import ClientEventEnvelope, EventStore, sync_events
        from production_core.identity import utcnow

        event_id = "11111111-1111-4111-8111-111111111111"
        store = EventStore()

        event_a = ClientEventEnvelope(
            schema_version="1.0",
            tenant_id="tenant-a",
            device_id="device-1",
            event_id=event_id,
            idempotency_key="device-1:11111111-1111-4111-8111-111111111111",
            event_type="activity",
            occurred_at=utcnow(),
            captured_at=utcnow(),
            payload={"app_name": "code.exe", "duration_seconds": 30},
        )
        event_b = ClientEventEnvelope(
            schema_version="1.0",
            tenant_id="tenant-b",
            device_id="device-1",
            event_id=event_id,
            idempotency_key="device-1:11111111-1111-4111-8111-111111111111",
            event_type="activity",
            occurred_at=utcnow(),
            captured_at=utcnow(),
            payload={"app_name": "code.exe", "duration_seconds": 30},
        )

        first = sync_events(store, [event_a])
        second = sync_events(store, [event_a])
        third = sync_events(store, [event_b])

        self.assertEqual([event_id], first.accepted)
        self.assertEqual([event_id], second.duplicates)
        self.assertEqual([event_id], third.accepted)
        self.assertEqual(2, len(store.events))

    def test_sync_rejection_has_dead_letter_details(self):
        from production_core.events import ClientEventEnvelope, EventStore, sync_events
        from production_core.identity import utcnow

        store = EventStore()
        rejected = ClientEventEnvelope(
            schema_version="1.0",
            tenant_id="tenant-a",
            device_id="device-1",
            event_id="22222222-2222-4222-8222-222222222222",
            idempotency_key="device-1:22222222-2222-4222-8222-222222222222",
            event_type="unknown",
            occurred_at=utcnow(),
            captured_at=utcnow(),
            payload={},
        )

        result = sync_events(store, [rejected])

        self.assertEqual([], result.accepted)
        self.assertEqual("22222222-2222-4222-8222-222222222222", result.rejected[0]["event_id"])
        self.assertIn("Unsupported event_type", result.rejected[0]["error"])
        self.assertEqual(1, len(store.dead_letters))

    def test_local_queue_marks_only_accepted_or_duplicate_events_synced(self):
        from production_core.events import SyncResult
        from production_core.local_queue import LocalEventQueue

        with tempfile.TemporaryDirectory() as tmp:
            queue = LocalEventQueue(Path(tmp) / "queue.sqlite3")
            queue.enqueue("accepted-event", {"event_id": "accepted-event"})
            queue.enqueue("duplicate-event", {"event_id": "duplicate-event"})
            queue.enqueue("rejected-event", {"event_id": "rejected-event"})

            queue.apply_sync_result(
                SyncResult(
                    accepted=["accepted-event"],
                    duplicates=["duplicate-event"],
                    rejected=[{"event_id": "rejected-event", "error": "bad payload"}],
                )
            )

            self.assertEqual("synced", queue.get("accepted-event").status)
            self.assertEqual("synced", queue.get("duplicate-event").status)
            self.assertEqual("dead_letter", queue.get("rejected-event").status)
            self.assertEqual("bad payload", queue.get("rejected-event").last_error)

    def test_local_queue_leases_pending_events_and_retries_with_backoff(self):
        from production_core.identity import utcnow
        from production_core.local_queue import LocalEventQueue

        with tempfile.TemporaryDirectory() as tmp:
            queue = LocalEventQueue(Path(tmp) / "queue.sqlite3")
            now = utcnow()
            queue.enqueue("event-1", {"event_id": "event-1"})
            queue.enqueue("event-2", {"event_id": "event-2"})

            first_lease = queue.lease_pending(limit=1, now=now, lease_seconds=30)
            second_lease = queue.lease_pending(limit=10, now=now, lease_seconds=30)

            self.assertEqual(["event-1"], [record.event_id for record in first_lease])
            self.assertEqual(["event-2"], [record.event_id for record in second_lease])
            self.assertEqual("in_progress", queue.get("event-1").status)

            queue.mark_retry("event-1", error="network timeout", now=now, base_delay_seconds=15)
            self.assertEqual("pending", queue.get("event-1").status)
            self.assertEqual(1, queue.get("event-1").retry_count)
            self.assertEqual([], queue.lease_pending(limit=10, now=now, lease_seconds=30))

            later = now + timedelta(seconds=15)
            retried = queue.lease_pending(limit=10, now=later, lease_seconds=30)
            self.assertEqual(["event-1"], [record.event_id for record in retried])

    def test_local_queue_dead_letters_after_retry_limit_and_reports_stats(self):
        from production_core.identity import utcnow
        from production_core.local_queue import LocalEventQueue

        with tempfile.TemporaryDirectory() as tmp:
            queue = LocalEventQueue(Path(tmp) / "queue.sqlite3")
            now = utcnow()
            queue.enqueue("event-1", {"event_id": "event-1"})
            queue.lease_pending(limit=1, now=now, lease_seconds=30)

            queue.mark_retry("event-1", error="bad payload", now=now, max_retries=1)

            self.assertEqual("dead_letter", queue.get("event-1").status)
            self.assertEqual({"dead_letter": 1}, queue.stats())

    def test_contract_schema_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        event_schema = root / "contracts" / "client_event.schema.json"
        sync_schema = root / "contracts" / "sync_ack.schema.json"

        self.assertTrue(event_schema.exists())
        self.assertTrue(sync_schema.exists())
        self.assertIn('"schema_version"', event_schema.read_text(encoding="utf-8"))
        self.assertIn('"accepted"', sync_schema.read_text(encoding="utf-8"))
