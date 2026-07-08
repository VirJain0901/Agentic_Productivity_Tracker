"""Lazy, legal-gated access to prototype-only modules.

These adapters intentionally avoid importing prototype modules at module import
time. The production path can import this file safely without loading Dash,
synthetic ML, file-system surveillance, or local report generation code.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
from dataclasses import dataclass


ALLOW_ENV = "ALLOW_PROTOTYPE_IMPORTS"


@dataclass(frozen=True)
class PrototypeModule:
    key: str
    module: str
    reason: str


PROTOTYPES = {
    "model": PrototypeModule(
        key="model",
        module="model",
        reason="Contains synthetic ML, file-system monitoring, and local CSV reporting.",
    ),
    "dash_app": PrototypeModule(
        key="dash_app",
        module="monitoring.dash_app",
        reason="Standalone debug dashboard that queries the database at import time.",
    ),
}


def _prototype_imports_allowed() -> bool:
    return os.getenv(ALLOW_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _require_human_gate(module: PrototypeModule) -> None:
    if _prototype_imports_allowed():
        return
    raise RuntimeError(
        f"{module.module} is prototype-only and is blocked from the production path. "
        f"Reason: {module.reason} Set {ALLOW_ENV}=true only for explicit local prototype review."
    )


def prototype_status() -> dict[str, dict[str, object]]:
    status = {}
    for key, module in PROTOTYPES.items():
        status[key] = {
            "module": module.module,
            "importable": importlib.util.find_spec(module.module) is not None,
            "production_enabled": False,
            "reason": module.reason,
        }
    return status


def load_model_prototype():
    module = PROTOTYPES["model"]
    _require_human_gate(module)
    return importlib.import_module(module.module)


def load_dash_prototype():
    module = PROTOTYPES["dash_app"]
    _require_human_gate(module)
    return importlib.import_module(module.module)
