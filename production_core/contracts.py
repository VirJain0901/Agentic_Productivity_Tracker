"""Small JSON-contract validator for production-core payloads."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILES = {
    "client_event": ROOT / "contracts" / "client_event.schema.json",
    "sync_ack": ROOT / "contracts" / "sync_ack.schema.json",
    "health": ROOT / "contracts" / "health.schema.json",
    "command": ROOT / "contracts" / "command.schema.json",
    "audit_log": ROOT / "contracts" / "audit_log.schema.json",
}


class ContractValidationError(ValueError):
    pass


def load_contract_schema(name: str) -> dict[str, Any]:
    try:
        path = CONTRACT_FILES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown contract: {name}") from exc
    return json.loads(path.read_text(encoding="utf-8"))


def _is_type(value: Any, schema_type: str) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return True


def _validate_format(field: str, value: Any, expected_format: str) -> None:
    if expected_format == "uuid":
        try:
            uuid.UUID(str(value))
        except ValueError as exc:
            raise ContractValidationError(f"{field} must be a UUID") from exc
    if expected_format == "date-time":
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractValidationError(f"{field} must be an ISO date-time") from exc


def _validate_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if "const" in schema and value != schema["const"]:
        raise ContractValidationError(f"{path} must equal {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        raise ContractValidationError(f"{path} must be one of: {allowed}")

    schema_type = schema.get("type")
    if schema_type and not _is_type(value, schema_type):
        raise ContractValidationError(f"{path} must be {schema_type}")

    if schema_type == "string":
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            raise ContractValidationError(f"{path} must have length >= {min_length}")
        expected_format = schema.get("format")
        if expected_format:
            _validate_format(path, value, expected_format)

    if schema_type == "object":
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        for field in required:
            if field not in value:
                raise ContractValidationError(f"{path}.{field} is required")

        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                extras = ", ".join(sorted(extra))
                raise ContractValidationError(f"{path} has unexpected field(s): {extras}")

        for field, field_schema in properties.items():
            if field in value:
                _validate_schema(field_schema, value[field], f"{path}.{field}")

    if schema_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                _validate_schema(item_schema, item, f"{path}[{index}]")


def validate_contract_payload(name: str, payload: dict[str, Any]) -> None:
    schema = load_contract_schema(name)
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in payload:
            raise ContractValidationError(f"{field} is required")

    if schema.get("additionalProperties") is False:
        extra = set(payload) - set(properties)
        if extra:
            extras = ", ".join(sorted(extra))
            raise ContractValidationError(f"Unexpected field(s): {extras}")

    for field, field_schema in properties.items():
        if field not in payload:
            continue
        _validate_schema(field_schema, payload[field], field)
