"""Operations and deployment-readiness helpers.

These helpers are intentionally framework-neutral so production checks can be
tested without importing Django settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlparse

from .dashboard import DeviceHealth


@dataclass(frozen=True)
class ReadinessIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class RedisConnectionSettings:
    scheme: str
    host: str
    port: int
    password: str | None
    db: int
    tls: bool


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    status: str
    checked_at: datetime
    message: str = ""


@dataclass(frozen=True)
class OperationsHealthReport:
    overall_status: str
    service_status_counts: dict[str, int]
    device_status_counts: dict[str, int]
    down_services: list[str]
    degraded_services: list[str]
    unhealthy_device_ids: list[str]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _issue(code: str, message: str, severity: str = "critical") -> ReadinessIssue:
    return ReadinessIssue(code=code, severity=severity, message=message)


def _secret_is_weak(secret: str | None) -> bool:
    if not secret:
        return True
    if secret.startswith("django-insecure-"):
        return True
    if len(secret) < 50:
        return True
    return len(set(secret)) < 5


def validate_production_settings(settings: dict[str, Any]) -> list[ReadinessIssue]:
    """Return critical production hardening issues.

    The expected keys mirror Django's deploy check names, with support for the
    `DJANGO_*` env-style names used in `.env.example`.
    """

    secret = settings.get("SECRET_KEY", settings.get("DJANGO_SECRET_KEY"))
    debug = settings.get("DJANGO_DEBUG", settings.get("DEBUG", False))
    allowed_hosts = settings.get("ALLOWED_HOSTS", settings.get("DJANGO_ALLOWED_HOSTS", []))
    if isinstance(allowed_hosts, str):
        allowed_hosts = [host.strip() for host in allowed_hosts.split(",") if host.strip()]

    issues: list[ReadinessIssue] = []

    if _as_bool(debug):
        issues.append(_issue("debug_enabled", "DJANGO_DEBUG/DEBUG must be false in production."))
    if _secret_is_weak(secret):
        issues.append(_issue("weak_secret_key", "SECRET_KEY must be long, random, and non-default."))
    if int(settings.get("SECURE_HSTS_SECONDS", 0) or 0) <= 0:
        issues.append(_issue("hsts_disabled", "SECURE_HSTS_SECONDS must be set after HTTPS is confirmed."))
    if not _as_bool(settings.get("SECURE_SSL_REDIRECT", False)):
        issues.append(_issue("ssl_redirect_disabled", "SECURE_SSL_REDIRECT must be true behind HTTPS."))
    if not _as_bool(settings.get("SESSION_COOKIE_SECURE", False)):
        issues.append(_issue("session_cookie_insecure", "SESSION_COOKIE_SECURE must be true."))
    if not _as_bool(settings.get("CSRF_COOKIE_SECURE", False)):
        issues.append(_issue("csrf_cookie_insecure", "CSRF_COOKIE_SECURE must be true."))
    if not allowed_hosts or "*" in allowed_hosts:
        issues.append(_issue("allowed_hosts_empty", "ALLOWED_HOSTS must name explicit production hosts."))

    return issues


def parse_redis_url(url: str) -> RedisConnectionSettings:
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss"}:
        raise ValueError("Redis URL must use redis:// or rediss://")
    if not parsed.hostname:
        raise ValueError("Redis URL must include a host")

    db = 0
    if parsed.path and parsed.path != "/":
        db = int(parsed.path.lstrip("/"))

    return RedisConnectionSettings(
        scheme=parsed.scheme,
        host=parsed.hostname,
        port=parsed.port or 6379,
        password=unquote(parsed.password) if parsed.password else None,
        db=db,
        tls=parsed.scheme == "rediss",
    )


def build_operations_health_report(
    services: list[ServiceHealth],
    devices: list[DeviceHealth],
    now: datetime,
) -> OperationsHealthReport:
    service_counts = {"ok": 0, "degraded": 0, "down": 0}
    for service in services:
        if service.status not in service_counts:
            raise ValueError(f"Unsupported service status: {service.status}")
        service_counts[service.status] += 1

    device_counts = {"healthy": 0, "stale": 0, "offline": 0}
    unhealthy_device_ids: list[str] = []
    for device in devices:
        status = device.status(now)
        device_counts[status] += 1
        if status != "healthy" or device.has_sync_failure:
            unhealthy_device_ids.append(device.device_id)

    down_services = [service.name for service in services if service.status == "down"]
    degraded_services = [service.name for service in services if service.status == "degraded"]

    if down_services:
        overall = "down"
    elif degraded_services or unhealthy_device_ids:
        overall = "degraded"
    else:
        overall = "ok"

    return OperationsHealthReport(
        overall_status=overall,
        service_status_counts=service_counts,
        device_status_counts=device_counts,
        down_services=down_services,
        degraded_services=degraded_services,
        unhealthy_device_ids=unhealthy_device_ids,
    )
