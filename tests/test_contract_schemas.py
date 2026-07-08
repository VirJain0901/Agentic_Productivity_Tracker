import unittest
from pathlib import Path


class ContractSchemaTests(unittest.TestCase):
    def test_client_event_enum_is_enforced(self):
        from production_core.contracts import ContractValidationError, validate_contract_payload
        from production_core.identity import new_id, utcnow

        payload = {
            "schema_version": "1.0",
            "tenant_id": "tenant-1",
            "device_id": "device-1",
            "event_id": new_id(),
            "idempotency_key": "device-1:event-1",
            "event_type": "screen_stream",
            "occurred_at": utcnow().isoformat(),
            "captured_at": utcnow().isoformat(),
            "payload": {},
        }

        with self.assertRaises(ContractValidationError):
            validate_contract_payload("client_event", payload)

    def test_sync_ack_array_items_and_nested_extra_fields_are_enforced(self):
        from production_core.contracts import ContractValidationError, validate_contract_payload

        invalid_item_type = {
            "accepted": [123],
            "duplicates": [],
            "rejected": [],
        }
        nested_extra = {
            "accepted": [],
            "duplicates": [],
            "rejected": [{"event_id": "event-1", "error": "bad payload", "code": "E_BAD"}],
        }

        with self.assertRaises(ContractValidationError):
            validate_contract_payload("sync_ack", invalid_item_type)
        with self.assertRaises(ContractValidationError):
            validate_contract_payload("sync_ack", nested_extra)

    def test_command_schema_enum_matches_command_types_and_is_enforced(self):
        from production_core.commands import CommandType
        from production_core.contracts import ContractValidationError, load_contract_schema, validate_contract_payload
        from production_core.identity import new_id

        schema_enum = set(load_contract_schema("command")["properties"]["command_type"]["enum"])
        self.assertEqual({command_type.value for command_type in CommandType}, schema_enum)

        payload = {
            "tenant_id": "tenant-1",
            "command_id": new_id(),
            "target_device_id": "device-1",
            "command_type": "reboot_machine",
            "requires_legal_review": True,
            "requested_by": "admin-1",
            "payload": {},
        }

        with self.assertRaises(ContractValidationError):
            validate_contract_payload("command", payload)

    def test_contract_files_are_json_objects_with_schema_ids(self):
        import json

        root = Path(__file__).resolve().parents[1] / "contracts"
        for path in root.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("object", schema["type"])
            self.assertTrue(schema["$id"].startswith("https://"))

    def test_contract_validation_script_accepts_checked_in_examples(self):
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "validate_contracts.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
