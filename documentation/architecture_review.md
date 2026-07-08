# Architecture Review

Updated: 2026-06-30

Scope: full repository architecture, including intern runtime, production platform layer, contracts, investor demo, docs, CI, dependencies, and privacy posture.

Constraint followed: no intern-owned runtime code changes.

## Executive Summary

AxonDesk is correctly moving toward a LanSchool-style platform for both education and workforce monitoring, but the codebase still has three separate realities: intern runtime modules, the production platform layer, and the investor demo.

The safest next architecture move is to keep intern code stable while adding guardrails and contracts around it. Runtime integration should happen through reviewed adapters, not by silently editing intern modules.

As of the 2026-06-30 audit, the immediate runtime blocker is migration hygiene: `monitoring` has conflicting leaf migrations `0009_agentheartbeat` and `0010_alter_session_department_session`.

## Current Architecture Map

```text
Windows endpoint prototypes
  agent.py / watchdog_service.py / monitoring/tracker.py / monitoring/sync_manager.py
  -> current legacy APIs and direct DB/ORM paths

Django intern backend
  employee_tracker/ + monitoring/
  -> current API, admin, models, tests, WebSocket consumer

Production platform layer
  production_core/ + platform_core/ + platform_api/ + production_adapters/
  -> contract-first tenancy, sync, governance, legal gate, health, dashboard projection logic

Investor demo
  investor_demo/
  -> TypeScript UI shell with sample/live status separation
```

## Architecture Decision

Keep `production_core/` as the policy and contract authority. Keep `monitoring/` and root intern files read-only until each intern submits focused changes. Platform code should wrap, validate, or document gaps rather than modifying intern runtime code directly.

## Implemented In This Pass

- Added [Intern next actions](intern_next_actions.md) with concrete tasks, deliverables, and acceptance tests for all interns.
- Added this architecture review as the current full-system audit.
- Added `scripts/check_architecture_guardrails.py` to prevent stale architecture docs and missing contract handoffs.
- Added tests for the architecture guardrail.
- Added the architecture guardrail to CI.
- Updated `.gitignore` so new top-level `screenshots/` captures are ignored.
- Quarantined Vikrant's root-level ML/MySQL upload under `prototypes/vikrant_ml/` and restored Django boot to `employee_tracker.settings`.
- Added separate intern review files under `documentation/intern_reviews/`.

## Findings

### P0: Runtime Still Lacks One Data Plane

The target path is:

```text
enrolled agent -> encrypted local queue -> /api/v1/sync/events/ -> canonical backend events -> projections -> tenant-scoped realtime -> dashboard
```

Current reality:

- The tracker still has direct ORM behavior.
- The sync client still has raw database assumptions.
- The intern backend exposes legacy endpoints.
- The platform v1 API exists but is not wired into `employee_tracker/urls.py` because that file is intern-owned.

Decision:

Do not force-wire this from the platform side. Create the reviewed v1 integration as a separate protected diff.

### P0: Monitoring Migration Graph Is Split

Current reality:

- `manage.py makemigrations --check --dry-run` fails.
- `manage.py test monitoring --noinput` fails before running tests.
- Django reports multiple leaf nodes: `0009_agentheartbeat` and `0010_alter_session_department_session`.

Decision:

Fix this with a migration-only PR before any further monitoring model changes. Do not include feature work in that PR.

### P0: Tenant Isolation Must Become Runtime Behavior

Production models and tests already express tenant/person/device concepts. Intern runtime still uses global employee records, string department/role fields, and a global WebSocket room.

Decision:

Every runtime endpoint and realtime channel must eventually carry tenant scope. No dashboard or API should be accepted without an isolation test.

### P0: Privacy-Gated Features Are Present As Prototype Code

Screenshots, file monitoring, remote/system control, and ML risk scoring exist in prototype form.

Decision:

Keep those features gated. The production path must require consent, policy acknowledgement, immutable audit, retention, access logging, and human legal confirmation.

### P1: CI Needs Architecture Guardrails

Tests and contracts are present, but there was no single check ensuring the docs and guardrails stay aligned.

Decision:

Run architecture guardrails in CI/manual audit and keep stale intern review docs, alternate root Django apps, and bad `manage.py` settings out of the repo.

### P1: Privacy Artifacts Are Tracked

There are tracked PNG files under `screenshots/`.

Decision:

Do not delete them without explicit approval because deleting files is destructive. Ignore new screenshot captures now and plan a separate approved cleanup to remove existing tracked artifacts.

## End-To-End Solution

1. Enroll device with a one-time tenant-scoped enrollment token.
2. Store a device credential locally.
3. Agent captures approved signals only.
4. Agent writes event envelopes to encrypted local queue.
5. Sync client sends batches to `/api/v1/sync/events/`.
6. Backend validates schema, tenant, device credential, idempotency, and role.
7. Backend stores append-only events and returns ACK.
8. Projection layer updates dashboard-ready operational views.
9. Realtime sends tenant/team/class scoped status only.
10. Dashboard shows device health, policy status, sync failures, and reports.
11. Every sensitive read/write produces immutable audit.
12. Retention jobs purge or hold data according to policy.

## What To Build Next

1. Reviewed v1 URL wiring diff.
2. Device enrollment endpoint and credential lifecycle.
3. Local encrypted queue adapter.
4. Event projection service.
5. Tenant-scoped realtime adapter.
6. Dashboard API powered by projections.
7. Privacy/audit/retention enforcement in runtime path.

## What Not To Build Yet

- Screenshot streaming.
- File-system surveillance.
- Remote commands.
- ML risk scoring.
- Cross-tenant dashboards.

Those stay behind the legal gate.
