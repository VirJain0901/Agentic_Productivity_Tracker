# Sanskruti - Backend And Real-Time System

Updated: 2026-07-08

Module: Backend and Real-Time System

Primary function: process, store, and serve data with realtime tracking.

## Verdict

Backend progress is real: the v1 URL path is now wired, heartbeat is authenticated, WebSocket rooms are tenant-scoped, session start now returns the employee session ID, and migration dry-run is clean. The remaining problem is contract hardening: v1 sync, policy scoping, and durable event persistence are not production-safe yet.

## What Is Good

- Sensitive ingest endpoints mostly require JWT auth.
- `activity_sync` has idempotency behavior.
- App usage is upserted with a unique daily constraint.
- WebSocket auth is checked on connect and uses tenant-scoped room names.
- `AgentHeartbeat` gives a useful operational signal.
- `/api/v1/` is included in the project URLs.
- `python manage.py check` and migration dry-run passed in the latest audit.

## Strict Findings

### P0: v1 sync endpoint is not production-safe

Evidence:

- `employee_tracker/urls.py` includes `path('api/v1/', include('platform_api.urls'))`.
- `platform_api/views.py` exposes `activity_sync_view`.
- `activity_sync_view` is `@csrf_exempt`, has no auth check, and uses an in-memory `EventStore`.

Why it matters:

The v1 path exists but cannot be trusted for production ingest. Events can be submitted without identity checks, and duplicates only survive for the current process lifetime.

Expected direction:

Add a v1 serializer in `platform_api`, require authenticated device/tenant identity, and persist events through a durable tenant/device-scoped store.

### P0: Policy endpoint trusts caller-supplied tenant

Evidence:

- `monitoring_policies` reads `tenant_id` from query params.
- It returns that value in `scope`.
- It does not verify that the supplied `tenant_id` equals the authenticated employee tenant.
- `monitoring/tests.py` currently expects `tenant_id=t-100` to succeed even when the test employee belongs to a different generated tenant.

Why it matters:

Policy is a security control. A user should not be able to ask for another tenant's policy or make the response claim a false tenant scope.

Expected direction:

Reject tenant mismatch with 403 and update the test to assert mismatch rejection.

### P0: v1 serializer and ACK contract tests are missing

Evidence:

- `tests/test_platform_api_views.py` calls `activity_sync_view` directly.
- The tests do not prove the project URL `/api/v1/sync/events/` is protected.
- There is no DRF serializer enforcing the v1 request shape.

Why it matters:

Sanskruti owns the backend contract. Without serializer and URL-level tests, Vaidehi and Kiara cannot safely align the client.

Expected direction:

Put v1 serializers in `platform_api` and add ACK contract tests under root `tests/`.

### P1: Blocklist is authenticated but still global

Evidence:

- `BlockedSite` has no tenant field.
- `blocklist` and `monitoring_policies` return all `BlockedSite` rows.

Why it matters:

One school/company can receive another tenant's policy entries once real tenants are active.

Expected direction:

Keep global blocklist only if it is explicitly a platform default. Otherwise add tenant/policy assignment ownership in the platform policy layer.

### P1: Monitoring model tenancy is partial

Evidence:

- `Employee.tenant` is nullable.
- `Employee.email` and `Employee.system_username` remain globally unique.
- `DepartmentSession` uniqueness is only `dept` plus `session_date`.
- `ClientEvent.event_id` and `idempotency_key` are globally unique.

Why it matters:

The product must support many schools and companies. Global uniqueness and nullable tenancy will create collisions and unclear ownership.

Expected direction:

Plan a separate reviewed data migration for strict tenant ownership and composite uniqueness.

### P2: Test names and coverage are stale

Evidence:

- `test_platform_api_urlpatterns_exist_without_project_url_wiring` is now outdated because project URL wiring exists.
- v1 tests are function-level, not full client URL tests.

Why it matters:

Tests should describe current behavior and prevent regressions in actual routing/auth.

Expected direction:

Rename stale tests and add Django client tests for the real URL.

## Next Assignment

First PR:

- Fix `monitoring_policies` tenant mismatch.
- Add tests for missing tenant/device and mismatched tenant.

Second PR:

- Add v1 sync serializer in `platform_api`.
- Add root contract tests for valid event, invalid event, duplicate ACK, and rejected ACK `error`.
- Protect `/api/v1/sync/events/` with auth and tenant/device checks.

Acceptance:

- `python manage.py check` passes.
- `python manage.py makemigrations --check --dry-run` passes.
- Unauthenticated v1 sync is rejected.
- Cross-tenant policy and sync requests are denied.
- Rejected ACK item shape is `{event_id, error}`.
