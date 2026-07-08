import unittest
from datetime import timedelta


class PrivacyAuditTests(unittest.TestCase):
    def test_audit_log_is_append_only(self):
        from production_core.governance import AuditLog
        from production_core.identity import utcnow

        audit = AuditLog()
        entry = audit.record(
            tenant_id="tenant-1",
            actor_id="admin-1",
            action="policy.view",
            target_type="policy",
            target_id="policy-1",
            occurred_at=utcnow(),
            metadata={"ip": "127.0.0.1"},
        )

        with self.assertRaises(PermissionError):
            audit.update(entry.id, metadata={"ip": "10.0.0.1"})
        with self.assertRaises(PermissionError):
            audit.delete(entry.id)

        self.assertEqual(1, len(audit.entries))
        self.assertEqual("127.0.0.1", audit.entries[0].metadata["ip"])

    def test_policy_ack_and_consent_are_versioned(self):
        from production_core.governance import GovernanceStore
        from production_core.identity import utcnow

        store = GovernanceStore()
        consent = store.record_consent(
            tenant_id="tenant-1",
            person_id="person-1",
            policy_version="2026.06.20",
            consent_basis="school_authorized_use",
            captured_at=utcnow(),
        )
        ack = store.record_policy_acknowledgement(
            tenant_id="tenant-1",
            person_id="person-1",
            policy_id="policy-1",
            policy_version="2026.06.20",
            acknowledged_at=utcnow(),
        )

        self.assertEqual("2026.06.20", consent.policy_version)
        self.assertEqual("2026.06.20", ack.policy_version)

    def test_policy_versions_must_be_published_before_assignment_and_are_tenant_scoped(self):
        from production_core.identity import utcnow
        from production_core.policies import PolicyService

        service = PolicyService()
        draft = service.create_policy(
            tenant_id="tenant-1",
            title="Classroom monitoring",
            version="2026.06.20",
            rules={"screenshots": False, "blocked_sites": ["games.example"]},
            created_by="admin-1",
            created_at=utcnow(),
        )

        with self.assertRaises(PermissionError):
            service.assign_policy(
                tenant_id="tenant-1",
                policy_id=draft.policy_id,
                version=draft.version,
                scope_kind="class",
                scope_id="class-a",
                assigned_by="admin-1",
                assigned_at=utcnow(),
            )

        published = service.publish_policy(
            tenant_id="tenant-1",
            policy_id=draft.policy_id,
            version=draft.version,
            published_by="admin-1",
            published_at=utcnow(),
        )
        assignment = service.assign_policy(
            tenant_id="tenant-1",
            policy_id=published.policy_id,
            version=published.version,
            scope_kind="class",
            scope_id="class-a",
            assigned_by="admin-1",
            assigned_at=utcnow(),
        )

        self.assertEqual("published", published.status)
        self.assertEqual("class-a", assignment.scope_id)
        self.assertEqual(published, service.current_policy_for_scope("tenant-1", "class", "class-a"))
        self.assertIsNone(service.current_policy_for_scope("tenant-2", "class", "class-a"))

    def test_retention_policy_identifies_expired_objects(self):
        from production_core.governance import GovernanceStore
        from production_core.identity import utcnow

        store = GovernanceStore()
        policy = store.create_retention_policy(
            tenant_id="tenant-1",
            data_type="screenshot",
            retain_days=7,
            legal_hold=False,
        )

        old_time = utcnow() - timedelta(days=8)
        new_time = utcnow() - timedelta(days=1)

        self.assertTrue(policy.is_expired(old_time, now=utcnow()))
        self.assertFalse(policy.is_expired(new_time, now=utcnow()))

        legal_hold = store.create_retention_policy(
            tenant_id="tenant-1",
            data_type="screenshot",
            retain_days=1,
            legal_hold=True,
        )
        self.assertFalse(legal_hold.is_expired(old_time, now=utcnow()))

    def test_data_export_job_lifecycle_is_audited_and_tenant_scoped(self):
        from production_core.governance import AuditLog, GovernanceStore
        from production_core.identity import utcnow

        audit = AuditLog()
        store = GovernanceStore(audit_log=audit)
        job = store.request_data_export(
            tenant_id="tenant-1",
            requested_by="auditor-1",
            requested_at=utcnow(),
            subject_person_id="person-1",
        )

        self.assertEqual("queued", job.status)
        self.assertEqual("person-1", job.subject_person_id)

        completed = store.complete_data_export(
            tenant_id="tenant-1",
            job_id=job.id,
            completed_at=utcnow(),
            artifact_uri="private://exports/tenant-1/export-1.json",
        )

        self.assertEqual("completed", completed.status)
        self.assertEqual("private://exports/tenant-1/export-1.json", completed.artifact_uri)
        self.assertEqual(["data_export.request", "data_export.complete"], [entry.action for entry in audit.entries])

        with self.assertRaises(PermissionError):
            store.complete_data_export(
                tenant_id="tenant-2",
                job_id=job.id,
                completed_at=utcnow(),
                artifact_uri="private://exports/tenant-2/export-1.json",
            )

    def test_deletion_request_respects_legal_hold_and_is_audited(self):
        from production_core.governance import AuditLog, GovernanceStore
        from production_core.identity import utcnow

        audit = AuditLog()
        store = GovernanceStore(audit_log=audit)
        blocked = store.request_deletion(
            tenant_id="tenant-1",
            person_id="person-1",
            requested_by="auditor-1",
            requested_at=utcnow(),
            legal_hold=True,
        )

        self.assertEqual("blocked_legal_hold", blocked.status)
        with self.assertRaises(PermissionError):
            store.complete_deletion(
                tenant_id="tenant-1",
                request_id=blocked.id,
                completed_at=utcnow(),
                completed_by="ops-1",
            )

        pending = store.request_deletion(
            tenant_id="tenant-1",
            person_id="person-2",
            requested_by="auditor-1",
            requested_at=utcnow(),
            legal_hold=False,
        )
        completed = store.complete_deletion(
            tenant_id="tenant-1",
            request_id=pending.id,
            completed_at=utcnow(),
            completed_by="ops-1",
        )

        self.assertEqual("completed", completed.status)
        self.assertIn("deletion.complete", [entry.action for entry in audit.entries])

    def test_legal_gate_blocks_gated_features_until_review(self):
        from production_core.legal_gate import FeatureGate, GatedFeature
        from production_core.identity import utcnow

        gate = FeatureGate()
        tenant_id = "tenant-1"

        for feature in GatedFeature:
            self.assertFalse(gate.is_allowed(feature, tenant_id=tenant_id))
            with self.assertRaises(PermissionError):
                gate.require_allowed(feature, tenant_id=tenant_id)

        gate.record_review(
            feature=GatedFeature.SCREENSHOT_STREAMING,
            tenant_id=tenant_id,
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-123",
        )

        self.assertTrue(gate.is_allowed(GatedFeature.SCREENSHOT_STREAMING, tenant_id=tenant_id))
        gate.require_allowed(GatedFeature.SCREENSHOT_STREAMING, tenant_id=tenant_id)
        self.assertFalse(gate.is_allowed(GatedFeature.SCREENSHOT_STREAMING, tenant_id="tenant-2"))
        self.assertFalse(gate.is_allowed(GatedFeature.REMOTE_COMMANDS, tenant_id=tenant_id))

    def test_gated_contract_schema_files_exist(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        command_schema = root / "contracts" / "command.schema.json"
        audit_schema = root / "contracts" / "audit_log.schema.json"

        self.assertTrue(command_schema.exists())
        self.assertTrue(audit_schema.exists())
        self.assertIn('"requires_legal_review"', command_schema.read_text(encoding="utf-8"))
        self.assertIn('"action"', audit_schema.read_text(encoding="utf-8"))
