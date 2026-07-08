# Intern Code And Architecture Audit

Updated: 2026-07-08

Scope: read-only audit of the intern runtime code and the surrounding integration contracts. No runtime code was changed in this pass.

## Executive Verdict

The codebase has moved forward since the June audit: the v1 URL path is wired, heartbeat is authenticated, WebSocket rooms are tenant-scoped, session start semantics improved, and the migration dry-run now passes. The product is still not production-ready because the intern modules are not yet aligned around one contract.

The current priority is v1 data-plane alignment: capture code must emit contract events, the local queue must retry and sync those events safely, the backend must validate/authenticate them, and analytics must consume only approved stored events.

Backend source of truth remains PostgreSQL. SQLite is allowed only as the device-side offline queue.

## Current Verification

Environment note:

- The audit used the bundled Codex Python runtime.
- Backend checks used `C:\tmp\employee_tracker_audit_deps`.

Checks:

- `manage.py check`: passed.
- `manage.py makemigrations --check --dry-run`: passed.
- `scripts/check_requirements_hygiene.py`: failed because `requirements/backend.txt` contains duplicate `python-decouple`.
- `scripts/ci_smoke.py`: failed because requirements hygiene fails and the local temp dependency target exposes an incomplete Django namespace during direct unittest discovery.

## Highest Priority Blockers

1. v1 sync is wired but not production-safe.
   Evidence: `platform_api.views.activity_sync_view` is `@csrf_exempt`, unauthenticated, and uses an in-memory `EventStore`.
   Impact: event ingest is not identity-bound, durable, or tenant-safe.
   Owner: Sanskruti.

2. Policy endpoint trusts caller-supplied tenant scope.
   Evidence: `monitoring_policies` reads `tenant_id` from query params and does not compare it to the authenticated employee tenant.
   Impact: policy responses can claim the wrong tenant and leak policy scope.
   Owner: Sanskruti with Kiara.

3. Agent does not send required tenant/device identity.
   Evidence: `agent.py` heartbeat payload lacks `tenant_id` and `device_id`, and policy fetch does not include those query parameters.
   Impact: the current agent cannot satisfy the newer backend contract.
   Owner: Kiara.

4. Local queue retry can strand events.
   Evidence: `fetch_and_lock_events` marks rows `in_progress`; `increment_retry` does not return regular failed rows to `pending`.
   Impact: events can stop retrying after a network failure.
   Owner: Vaidehi.

5. Sync manager does not emit the v1 event shape.
   Evidence: `build_batch` sends `created_at`, extra fields, and defaults to `/api/activity-sync/`; rejected ACK parsing reads `reason` instead of contract field `error`.
   Impact: v1 serializer enforcement would reject client events or lose dead-letter reasons.
   Owner: Vaidehi and Sanskruti.

6. Capture still bypasses the contract.
   Evidence: `monitoring/tracker.py` calls `django.setup()`, writes Django models directly, keeps a JSON offline queue, and starts screenshot capture.
   Impact: endpoint capture is not offline-safe, contract-safe, or legal-gated.
   Owner: Bhumika.

7. Screenshot capture, file-system monitoring, remote commands, and ML risk scoring remain legal-gated.
   Evidence: `monitoring/tracker.py` captures screenshots; `model.py` and `prototypes/vikrant_ml/` contain file monitoring and `risk_score` / `risk_level` logic.
   Impact: these features cannot enter production until consent, retention, audit, and human legal review exist.
   Owner: Bhumika, Kiara, and Vikrant.

8. Requirements hygiene is red.
   Evidence: duplicate `python-decouple` in `requirements/backend.txt`.
   Impact: CI smoke fails before it can provide reliable signal.
   Owner: project lead or the next packaging task owner.

## Separate Intern Reviews

- [Bhumika - Agent And Activity Monitoring](intern_reviews/bhumika_agent_activity.md)
- [Vaidehi - Storage And Sync Client](intern_reviews/vaidehi_storage_sync.md)
- [Sanskruti - Backend And Real-Time System](intern_reviews/sanskruti_backend_realtime.md)
- [Kiara - Security And System Persistence](intern_reviews/kiara_security_persistence.md)
- [Vikrant - Machine Learning And Analytics](intern_reviews/vikrant_ml_analytics.md)

## Architecture Notes

There are three lanes in the repository:

1. Intern runtime: `monitoring/`, `employee_tracker/`, `agent.py`, `watchdog_service.py`, `model.py`.
2. Production platform layer: `production_core/`, `platform_core/`, `platform_api/`, `production_adapters/`, `contracts/`.
3. Investor demo: `investor_demo/`.

Target data path:

```text
agent capture -> device-side SQLite queue -> /api/v1/sync/events/ -> PostgreSQL source of truth -> tenant-scoped dashboard and reports
```

## What Not To Do

- Do not delete intern code without an explicit cleanup task.
- Do not enable screenshot streaming, file monitoring, remote commands, or ML risk scoring in production until the legal gate is complete.
- Do not let the desktop agent connect directly to PostgreSQL.
- Do not treat investor demo sample data as production evidence.
- Do not build ML training work until contract-valid event data is stable.
