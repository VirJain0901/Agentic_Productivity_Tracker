"""Validate contract schemas and checked-in example payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from production_core.contracts import CONTRACT_FILES, ContractValidationError, validate_contract_payload  # noqa: E402


EXAMPLES_DIR = ROOT / "contracts" / "examples"


def _validate_schema_file(name: str, path: Path) -> list[str]:
    errors: list[str] = []
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]

    if schema.get("type") != "object":
        errors.append(f"{path}: top-level schema type must be object")
    if not str(schema.get("$id", "")).startswith("https://"):
        errors.append(f"{path}: $id must be an https URL")
    if not schema.get("properties"):
        errors.append(f"{path}: properties must not be empty")
    if schema.get("additionalProperties") is not False:
        errors.append(f"{path}: additionalProperties must be false")
    if name not in path.name:
        errors.append(f"{path}: filename should include contract name {name}")
    return errors


def _validate_examples() -> list[str]:
    errors: list[str] = []
    expected_examples = set(CONTRACT_FILES)
    seen_examples: set[str] = set()

    for path in sorted(EXAMPLES_DIR.glob("*.valid.json")):
        name = path.name.removesuffix(".valid.json")
        seen_examples.add(name)
        if name not in CONTRACT_FILES:
            errors.append(f"{path}: no matching contract named {name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate_contract_payload(name, payload)
        except (json.JSONDecodeError, ContractValidationError) as exc:
            errors.append(f"{path}: {exc}")

    missing = expected_examples - seen_examples
    for name in sorted(missing):
        errors.append(f"{EXAMPLES_DIR}: missing {name}.valid.json")
    return errors


def main() -> int:
    errors: list[str] = []
    for name, path in CONTRACT_FILES.items():
        errors.extend(_validate_schema_file(name, path))
    errors.extend(_validate_examples())

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Validated {len(CONTRACT_FILES)} contract schemas and examples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
