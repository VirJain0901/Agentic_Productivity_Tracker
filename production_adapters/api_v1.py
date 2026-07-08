"""Import-safe v1 API adapter payload builders.

This module is intentionally not wired into `employee_tracker.urls`. It lets
new production endpoints share contracts before a protected URL/settings diff
is reviewed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from production_core.contracts import validate_contract_payload
from production_core.events import SyncResult
from production_core.operations import OperationsHealthReport


HealthSource = Literal["live", "sample"]


def build_health_payload(
    report: OperationsHealthReport | None,
    source: HealthSource,
    checked_at: datetime,
) -> dict:
    if source == "live" and report is None:
        raise ValueError("live health payloads require an operations report")

    if report is None:
        payload = {
            "schema_version": "1.0",
            "source": source,
            "checked_at": checked_at.isoformat(),
            "overall_status": "degraded",
            "service_status_counts": {"ok": 0, "degraded": 1, "down": 0},
            "device_status_counts": {"healthy": 0, "stale": 0, "offline": 0},
            "down_services": [],
            "degraded_services": ["sample_data"],
            "unhealthy_device_ids": [],
        }
    else:
        payload = {
            "schema_version": "1.0",
            "source": source,
            "checked_at": checked_at.isoformat(),
            "overall_status": report.overall_status,
            "service_status_counts": dict(report.service_status_counts),
            "device_status_counts": dict(report.device_status_counts),
            "down_services": list(report.down_services),
            "degraded_services": list(report.degraded_services),
            "unhealthy_device_ids": list(report.unhealthy_device_ids),
        }

    validate_contract_payload("health", payload)
    return payload


def build_sync_ack_payload(result: SyncResult) -> dict:
    payload = {
        "accepted": list(result.accepted),
        "duplicates": list(result.duplicates),
        "rejected": [dict(rejection) for rejection in result.rejected],
    }
    validate_contract_payload("sync_ack", payload)
    return payload
