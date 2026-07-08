# Current Status

Updated: 2026-07-08

## What Is On Main

- `production_core/` contains tested framework-neutral invariants for identity, events, queueing, dashboard scope, governance, operations, policies, commands, screenshots, and legal gates.
- `platform_core/` contains a new database-backed Django model/service layer for tenant, person, device, membership, enrollment, credential, audit, policy, and policy assignment records.
- `platform_api/` contains wired Django v1 view functions for health and event sync under `/api/v1/`.
- `production_adapters/api_v1.py` contains import-safe v1 payload builders for health and sync acknowledgements.
- `contracts/` contains enforceable JSON contracts and checked-in valid examples, including the v1 health payload.
- `scripts/check_protected_paths.py` blocks accidental edits to intern-owned/protected runtime paths.
- `investor_demo/` is a TypeScript demo with optional live health detection at `/api/v1/health/` and sample fallback.
- `documentation/intern_code_audit.md` is the current read-only audit for the new intern code.
- `documentation/intern_next_actions.md` gives each intern concrete next assignments and acceptance tests.
- `documentation/intern_reviews/` contains separate strict review files for each intern.
- `documentation/architecture_review.md` is the current full-system architecture audit.
- Backend and agent requirements are split, but requirements hygiene is currently red because `requirements/backend.txt` duplicates `python-decouple`.
- Vikrant's uploaded standalone ML/MySQL files are quarantined under `prototypes/vikrant_ml/` and are not part of the production runtime.

## Wired But Not Production-Safe Yet

- `platform_core` is in `INSTALLED_APPS`.
- `/api/v1/health/` and `/api/v1/sync/events/` are included in the Django URL tree.
- Legacy endpoints still exist and should remain until v1 is contract-tested end to end.
- `platform_api.views.activity_sync_view` still needs auth, tenant/device verification, a serializer, and durable persistence.

## Current Blocker

The current blocker is contract alignment across intern modules:

- Backend v1 sync is wired but unauthenticated and in-memory.
- Policy fetch trusts caller-supplied `tenant_id`.
- Agent heartbeat/policy fetch do not send required tenant/device identity.
- Local queue retry can strand events in `in_progress`.
- Sync manager defaults to legacy `/api/activity-sync/` and does not emit the v1 event shape.
- Requirements hygiene fails on duplicate `python-decouple`.

## Legal Gates

The following remain blocked from production execution until consent, audit, retention, policy acknowledgement, and human legal review are complete:

- Screenshot streaming or binary upload.
- Remote commands.
- File-system surveillance.
- ML risk scoring.

## Verification

Current green checks from the 2026-07-08 audit:

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`

Current red checks:

- `python scripts/check_requirements_hygiene.py`
- `python scripts/ci_smoke.py`

`check_requirements_hygiene.py` fails because of duplicate `python-decouple` in `requirements/backend.txt`.

Known dev-environment warnings:

- Plain `python` is not on PATH in this shell; the audit used the bundled Codex Python runtime plus a temp dependency target.
- `python manage.py check --deploy` reports expected deployment warnings under local defaults: HSTS, SSL redirect, fallback secret, secure cookies, CSRF cookie, and `DEBUG=True`.
- Previous monitoring test runs logged Redis connection failures from realtime broadcast attempts when Redis was not running.
- Existing screenshot PNGs are still tracked under `screenshots/`; new captures are ignored, and removal should be a separate approved privacy cleanup.
