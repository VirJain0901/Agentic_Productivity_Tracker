# Full Codebase Audit

Date: 2026-06-30

Scope: full repository read-only audit, including intern code, production platform scaffolding, investor demo, contracts, CI, dependency flow, docs, and tracked artifacts.

Constraint: no runtime code was changed during this audit.

## Executive Summary

AxonDesk has a strong product direction and useful prototype pieces, but it is not production-ready. The production platform layer is cleaner than the intern runtime, yet it is still mostly separate from the running Django app. The latest intern code introduced a real migration blocker in `monitoring`, and several sensitive paths remain public or ungated.

Highest-risk items:

1. `monitoring` migration graph conflict blocks monitoring tests and migration dry-run.
2. Heartbeat is unauthenticated.
3. Policy/blocklist endpoints are public.
4. Sync client still assumes direct PostgreSQL access and incompatible statuses.
5. Screenshot capture and ML risk/file monitoring remain outside the legal-gated production path.
6. Realtime uses one global WebSocket room.
7. Tracked screenshot PNGs and `watchdog.lock` remain in git.

## Verification Results

Passed:

- `manage.py check`
- `scripts/check_architecture_guardrails.py`
- `scripts/validate_contracts.py`
- `scripts/check_requirements_hygiene.py`
- `manage.py test tests --noinput`
- `scripts/ci_smoke.py`
- `investor_demo` TypeScript check with `tsc --noEmit`

Failed:

- `manage.py makemigrations --check --dry-run`
- `manage.py test monitoring --noinput`

Failure reason:

```text
Conflicting migrations detected; multiple leaf nodes in the migration graph:
0009_agentheartbeat
0010_alter_session_department_session
```

Environment note:

- Plain `python` is not on PATH.
- Backend verification used bundled Codex Python with dependencies installed in `C:\tmp\employee_tracker_audit_deps_clean`.

## Architecture State

The repo has three lanes:

- Intern runtime: `monitoring/`, `employee_tracker/`, `agent.py`, `watchdog_service.py`, `model.py`.
- Production layer: `production_core/`, `platform_core/`, `platform_api/`, `production_adapters/`, `contracts/`.
- Investor demo: `investor_demo/`.

The production lane contains better concepts: tenant, person, device, membership, enrollment, credential, audit, legal gate, local queue, contracts, dashboard operations, and health reporting. The intern runtime still owns the actual Django URLs and agent scripts, so production invariants are not yet enforced in the running path.

Target end-to-end path:

```text
enrolled endpoint agent
-> encrypted local queue
-> /api/v1/sync/events/
-> append-only backend events
-> projections
-> tenant-scoped realtime
-> dashboard and reports
```

## Security Findings

### P0: Unauthenticated heartbeat

`monitoring/views.py` allows heartbeat writes without auth. This lets any caller mark a hostname active.

Required fix:

- Require authenticated device credentials.
- Resolve hostname to tenant-scoped device identity.
- Reject unknown or revoked device credentials.

### P0: Public policy endpoints

`blocklist` and `monitoring_policies` are public.

Required fix:

- Require auth.
- Return policy scoped to tenant and device.
- Add audit records for policy fetches.

### P0: Sensitive features not enforced through legal gate

Screenshot capture, file monitoring, remote commands, and ML risk scoring exist in code or prototype docs. They must stay disabled in production until consent, retention, immutable audit, access logging, and legal review are complete.

### P1: Agent prints auth response text

`agent.py` prints backend auth responses. This can leak tokens or auth failures into logs and support screenshots.

Required fix:

- Log sanitized status only.
- Never print response bodies from auth endpoints.

## Data Plane Findings

### P0: Sync schema mismatch

The sync client and backend are not one consistent path:

- Client default sync URL is not `/api/v1/sync/events/`.
- Runtime Django exposes `/api/activity-sync/`.
- Platform API defines `/api/v1/sync/events/` but is not wired.
- Client DB code writes statuses that do not exist in `ClientEvent.Status`.
- `sync_queue` is referenced but not visible as a schema.

Required fix:

- Build local queue as client-only storage.
- Send one event envelope contract to v1 sync.
- Return one ACK contract.
- Keep legacy endpoint until the v1 path is proven by tests.

### P1: Direct database access from client

`monitoring/database_handler.py` creates PostgreSQL connections from sync code. This must not ship to endpoints.

Required fix:

- No backend DB credentials on the device.
- Client sync only through API.

## Backend And Realtime Findings

### P0: Migration conflict

`monitoring` must have one migration leaf before more model work.

Required fix:

- Migration-only merge PR.
- Re-run migration dry-run and monitoring tests.

### P0: Global WebSocket room

`company_tracking` is shared globally.

Required fix:

- Tenant/team/class scoped rooms.
- Tests proving cross-tenant denial.

### P1: Session semantics

`session_start` returns a department session id as `session_id`.

Required fix:

- Return `department_session_id` and `employee_session_id` separately, or return the true employee session id as `session_id`.

## Agent And Endpoint Findings

### P0: Agent capture uses Django ORM directly

The endpoint tracker imports Django models and writes directly.

Required fix:

- Capture should produce contract events.
- Queue and sync should handle persistence.

### P1: Screenshot retention path mismatch

Capture writes under `screenshots`; cleanup checks `media/screenshots`.

Required fix:

- One storage root.
- One retention process.
- No binary screenshot path until legal gate is complete.

### P1: Polling interval ignored

`POLLING_INTERVAL` is configured but the main loop sleeps for 5 seconds.

Required fix:

- Use env-configured interval with safe bounds.

## ML And Analytics Findings

`model.py` and quarantined `prototypes/vikrant_ml/` contain risk scoring, file monitoring, synthetic labels, local report writes, and MySQL assumptions. Keep these as prototype/reference only.

Required next step:

- Descriptive analytics over approved events only.
- No `risk_score`, `risk_level`, file monitoring, or DB credentials.
- Add model cards before any predictive claim.

## Investor Demo Findings

The TypeScript demo compiles. It clearly separates sample fallback from live health checks, which is good for investor demos. It still uses CDN dynamic imports for GSAP and Lenis in runtime, so demo reliability depends on internet access unless bundled.

Required next step:

- For tomorrow-style investor demos, run the built local Vite preview and have a fallback video/screenshots ready.
- For production dashboard, replace sample data with authenticated dashboard APIs.

## CI And Process Findings

CI currently runs on pull requests and manual dispatch only. Direct pushes are intentionally not blocked, which helps interns push but lets broken code land on `main`.

Required process:

- Keep direct push open only if a senior review/audit happens after every intern push.
- Re-enable push CI before investor-facing or production branches become stable.

## Immediate Priority Order

1. Fix `monitoring` migration conflict.
2. Require auth for heartbeat and policies.
3. Align Vaidehi/Sanskruti sync contract.
4. Keep screenshots/file monitoring/risk scoring gated.
5. Replace global realtime room.
6. Remove tracked runtime artifacts in a separate approved cleanup.
7. Wire platform v1 URLs in a protected reviewed integration PR.

