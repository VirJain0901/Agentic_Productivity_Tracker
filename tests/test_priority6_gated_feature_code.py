import unittest


class ContractValidationCodeTests(unittest.TestCase):
    def test_command_contract_validator_rejects_missing_legal_flag(self):
        from production_core.contracts import ContractValidationError, validate_contract_payload
        from production_core.identity import new_id

        payload = {
            "tenant_id": "tenant-1",
            "command_id": new_id(),
            "target_device_id": "device-1",
            "command_type": "lock_screen",
            "requested_by": "admin-1",
            "payload": {},
        }

        with self.assertRaises(ContractValidationError):
            validate_contract_payload("command", payload)

        payload["requires_legal_review"] = True
        validate_contract_payload("command", payload)

    def test_audit_contract_validator_requires_action_and_iso_timestamp(self):
        from production_core.contracts import ContractValidationError, validate_contract_payload
        from production_core.identity import utcnow

        payload = {
            "tenant_id": "tenant-1",
            "actor_id": "admin-1",
            "target_type": "device",
            "target_id": "device-1",
            "occurred_at": utcnow().isoformat(),
        }

        with self.assertRaises(ContractValidationError):
            validate_contract_payload("audit_log", payload)

        payload["action"] = "device.view"
        validate_contract_payload("audit_log", payload)


class GatedCommandCodeTests(unittest.TestCase):
    def test_command_creation_is_blocked_until_legal_review(self):
        from production_core.commands import CommandLedger, CommandType
        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature

        gate = FeatureGate()
        audit = AuditLog()
        ledger = CommandLedger(feature_gate=gate, audit_log=audit)

        with self.assertRaises(PermissionError):
            ledger.create_command(
                tenant_id="tenant-1",
                target_device_id="device-1",
                command_type=CommandType.LOCK_SCREEN,
                requested_by="admin-1",
                payload={"message": "Policy review"},
                requested_at=utcnow(),
            )

        gate.record_review(
            feature=GatedFeature.REMOTE_COMMANDS,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-REMOTE-1",
        )
        command = ledger.create_command(
            tenant_id="tenant-1",
            target_device_id="device-1",
            command_type=CommandType.LOCK_SCREEN,
            requested_by="admin-1",
            payload={"message": "Policy review"},
            requested_at=utcnow(),
        )

        self.assertEqual("queued", command.status)
        self.assertTrue(command.requires_legal_review)
        self.assertEqual("command.create", audit.entries[-1].action)

    def test_command_ack_is_tenant_and_device_scoped(self):
        from production_core.commands import CommandAckStatus, CommandLedger, CommandType
        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature

        gate = FeatureGate()
        gate.record_review(
            feature=GatedFeature.REMOTE_COMMANDS,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-REMOTE-1",
        )
        ledger = CommandLedger(feature_gate=gate, audit_log=AuditLog())
        command = ledger.create_command(
            tenant_id="tenant-1",
            target_device_id="device-1",
            command_type=CommandType.SEND_MESSAGE,
            requested_by="admin-1",
            payload={"message": "Please save work."},
            requested_at=utcnow(),
        )

        with self.assertRaises(PermissionError):
            ledger.acknowledge(
                tenant_id="tenant-2",
                device_id="device-1",
                command_id=command.command_id,
                status=CommandAckStatus.ACCEPTED,
                acknowledged_at=utcnow(),
            )
        with self.assertRaises(PermissionError):
            ledger.acknowledge(
                tenant_id="tenant-1",
                device_id="device-2",
                command_id=command.command_id,
                status=CommandAckStatus.ACCEPTED,
                acknowledged_at=utcnow(),
            )

        ack = ledger.acknowledge(
            tenant_id="tenant-1",
            device_id="device-1",
            command_id=command.command_id,
            status=CommandAckStatus.ACCEPTED,
            acknowledged_at=utcnow(),
        )

        self.assertEqual(command.command_id, ack.command_id)
        self.assertEqual("accepted", command.status)

    def test_legal_review_for_one_tenant_does_not_unlock_commands_for_another(self):
        from production_core.commands import CommandLedger, CommandType
        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature

        gate = FeatureGate()
        gate.record_review(
            feature=GatedFeature.REMOTE_COMMANDS,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-REMOTE-1",
        )
        ledger = CommandLedger(feature_gate=gate, audit_log=AuditLog())

        with self.assertRaises(PermissionError):
            ledger.create_command(
                tenant_id="tenant-2",
                target_device_id="device-2",
                command_type=CommandType.SEND_MESSAGE,
                requested_by="admin-2",
                payload={"message": "Hello"},
                requested_at=utcnow(),
            )


class GatedScreenshotCodeTests(unittest.TestCase):
    def test_screenshot_registration_and_access_are_blocked_until_legal_review(self):
        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature
        from production_core.screenshots import ScreenshotRegistry

        gate = FeatureGate()
        audit = AuditLog()
        registry = ScreenshotRegistry(feature_gate=gate, audit_log=audit)

        with self.assertRaises(PermissionError):
            registry.register_object(
                tenant_id="tenant-1",
                device_id="device-1",
                person_id="person-1",
                captured_at=utcnow(),
                content_sha256="a" * 64,
                byte_size=1024,
                retention_days=7,
            )

        gate.record_review(
            feature=GatedFeature.SCREENSHOT_STREAMING,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-SCREEN-1",
        )
        screenshot = registry.register_object(
            tenant_id="tenant-1",
            device_id="device-1",
            person_id="person-1",
            captured_at=utcnow(),
            content_sha256="a" * 64,
            byte_size=1024,
            retention_days=7,
        )
        access = registry.record_access(
            tenant_id="tenant-1",
            screenshot_id=screenshot.screenshot_id,
            actor_id="auditor-1",
            purpose="policy_review",
            accessed_at=utcnow(),
        )

        self.assertTrue(screenshot.storage_key.startswith("tenants/tenant-1/screenshots/"))
        self.assertEqual(screenshot.screenshot_id, access.screenshot_id)
        self.assertEqual("screenshot.access", audit.entries[-1].action)

    def test_screenshot_access_is_tenant_scoped_and_respects_retention(self):
        from datetime import timedelta

        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature
        from production_core.screenshots import ScreenshotRegistry

        gate = FeatureGate()
        gate.record_review(
            feature=GatedFeature.SCREENSHOT_STREAMING,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-SCREEN-1",
        )
        registry = ScreenshotRegistry(feature_gate=gate, audit_log=AuditLog())
        screenshot = registry.register_object(
            tenant_id="tenant-1",
            device_id="device-1",
            person_id="person-1",
            captured_at=utcnow() - timedelta(days=8),
            content_sha256="b" * 64,
            byte_size=2048,
            retention_days=7,
        )

        with self.assertRaises(PermissionError):
            registry.record_access(
                tenant_id="tenant-2",
                screenshot_id=screenshot.screenshot_id,
                actor_id="auditor-2",
                purpose="policy_review",
                accessed_at=utcnow(),
            )

        self.assertTrue(screenshot.is_expired(now=utcnow()))

    def test_legal_review_for_one_tenant_does_not_unlock_screenshots_for_another(self):
        from production_core.governance import AuditLog
        from production_core.identity import utcnow
        from production_core.legal_gate import FeatureGate, GatedFeature
        from production_core.screenshots import ScreenshotRegistry

        gate = FeatureGate()
        gate.record_review(
            feature=GatedFeature.SCREENSHOT_STREAMING,
            tenant_id="tenant-1",
            reviewer_id="legal-1",
            reviewed_at=utcnow(),
            reference="LEGAL-SCREEN-1",
        )
        registry = ScreenshotRegistry(feature_gate=gate, audit_log=AuditLog())

        with self.assertRaises(PermissionError):
            registry.register_object(
                tenant_id="tenant-2",
                device_id="device-2",
                person_id="person-2",
                captured_at=utcnow(),
                content_sha256="c" * 64,
                byte_size=512,
                retention_days=7,
            )
