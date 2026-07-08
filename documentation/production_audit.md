# Production Readiness Audit

Generated: 2026-06-20
Scope: every tracked project file, generated artifact visible in the workspace, runtime configuration, product idea, and end-to-end architecture.
Method: local static audit, runtime smoke checks, dependency resolution checks, and four parallel sub-agent reviews covering backend/API, client/sync/ML, docs/demo/setup, and product architecture.

Current note, 2026-06-26: this is the baseline production audit. Some packaging and test gaps listed below have since been fixed. For current status, read `documentation/current_status.md` and `documentation/intern_code_audit.md`.

## Verdict

Status: **P0 No-Go**.

This repository is a useful prototype bundle, but it is not a production-ready student/employee monitoring product yet. The biggest risk is not one isolated bug. The biggest risk is that the product is split across multiple incompatible execution paths:

```text
tracker.py direct Django ORM writes
sync_manager.py + database_handler.py raw Postgres legacy tables
Django API + ClientEvent partial event ingestion
dash_app.py import-time dashboard queries
model.py local CSV/synthetic ML prototype
investor_demo static product shell
```

Production must converge on one path:

```text
enrolled agent -> encrypted local queue -> authenticated sync API -> Django canonical database -> projections -> tenant-scoped realtime -> dashboard -> audit/export/analytics
```

Do not pitch or ship this as a live monitoring platform until the P0 items below are closed.

## Validation Results

| Check | Result | Notes |
| --- | --- | --- |
| Python syntax compile | Pass | `compileall` completed for Django app, monitoring app, agent, watchdog, and ML file. |
| Dependency resolution | Partial pass | `requirements.txt` resolves with network, but Django runtime failed because `daphne` is configured and missing. |
| Temporary dependency install | Pass with manual `daphne` | Installed into `C:\tmp\employee_tracker_audit_deps`; did not modify repo dependencies. |
| `manage.py check` | Pass only after temp `daphne` install | Original requirements are still incomplete. |
| `manage.py check --deploy` | Fail warnings | 6 deploy warnings: HSTS, SSL redirect, weak fallback secret, insecure session cookie, insecure CSRF cookie, debug true. |
| `makemigrations --check --dry-run` | Pass | No migration drift detected after current code changes. |
| `manage.py test --noinput` | Fail by absence | Ran 0 tests. This is a release blocker. |
| `manage.py showmigrations` | Local DB not initialized | Existing `db.sqlite3` has all migrations unapplied. |
| `import model` | Fail | `sklearn` is missing from declared requirements. |
| `import monitoring.dash_app` | Fail | Queries database at import time and crashes on missing tables. |
| `import agent, watchdog_service, monitoring.sync_manager, monitoring.tracker` | Fail | `pywintypes` missing through target install; Windows agent packaging is not reliable. |

## P0 Release Blockers

### 1. No Coherent End-to-End Data Plane

Refs:
- `monitoring/tracker.py`
- `monitoring/sync_manager.py`
- `monitoring/database_handler.py`
- `monitoring/views.py`
- `contracts/events.md`

Problem:
- `tracker.py` writes directly to Django models from the device.
- `sync_manager.py` reads a separate `activity_records` table.
- `database_handler.py` assumes separate unmanaged `users`, `sessions`, `activity_records`, and analytics tables.
- `views.py` has a partial `ClientEvent` ingestion API.
- The contract document and code do not use the same field names or event types.

Why it matters:
- Offline sync, deduplication, analytics, dashboards, and audit logs will disagree.
- A customer can lose events, duplicate records, or show different numbers in different screens.

Fix:
- Make Django-owned events the canonical source of truth.
- Replace unmanaged raw Postgres helpers with a documented local queue schema.
- Make every agent write to local queue first, then sync through `POST /api/activity-sync/`.
- Add contract tests that submit the exact `contracts/events.md` envelope.

### 2. Sync Can Lose Rejected Records

Refs:
- `monitoring/sync_manager.py`
- `monitoring/views.py`

Problem:
- `sync_manager.py` treats HTTP `207` as success and marks local records synced without inspecting `accepted`, `duplicates`, and `rejected`.
- `views.py` returns `207` specifically when some events were rejected.

Why it matters:
- Invalid or malformed local events can be permanently dropped while the client believes they synced.

Fix:
- Parse the response body.
- Mark local records synced only if the event is in `accepted` or confirmed duplicate.
- Store `rejected` rows in a dead-letter state with error reason, retry count, and operator visibility.

### 3. Event IDs and Idempotency Are Globally Unsafe

Refs:
- `monitoring/sync_manager.py`
- `monitoring/models.py`
- `monitoring/views.py`

Problem:
- `sync_manager.py` uses local `record_id` as global `event_id`.
- `ClientEvent.event_id` and `ClientEvent.idempotency_key` are globally unique.
- Two devices can both submit `record_id = 1`.

Why it matters:
- One device can accidentally or maliciously cause another device event to be treated as a duplicate.

Fix:
- Generate UUID/ULID event IDs on the device.
- Use composite uniqueness such as `(tenant, device, event_id)` and `(tenant, idempotency_key)`.
- Reject non-UUID IDs after a migration grace period.

### 4. Tenant Isolation Does Not Exist

Refs:
- `monitoring/models.py`
- `monitoring/consumers.py`
- `monitoring/views.py`

Problem:
- There is no `Tenant`, `Organization`, `School`, `Classroom`, `Department`, `Membership`, or role-scoped relationship model.
- Every authenticated WebSocket joins the same `company_tracking` room.
- APIs resolve employees globally by username/email or staff-submitted IDs.

Why it matters:
- A monitoring product without tenant isolation can leak live activity and screenshots across customers, schools, departments, or classrooms.

Fix:
- Add tenant and membership models before adding more features.
- Put every employee/person/device/policy/event/command under a tenant.
- Replace `company_tracking` with tenant/class/team scoped channels.
- Add object-level permission tests.

### 5. Authorization Model Is Too Coarse

Refs:
- `monitoring/views.py`
- `monitoring/consumers.py`
- `employee_tracker/urls.py`

Problem:
- Authenticated users are not differentiated as teacher, manager, tenant admin, compliance auditor, employee, student, or device agent.
- Staff users can submit events for arbitrary employees.
- Admin and realtime access do not prove least privilege.

Why it matters:
- Monitoring data is sensitive. "Authenticated" is not enough.

Fix:
- Add `UserMembership` and scoped roles.
- Add device service accounts separate from human users.
- Add audited impersonation or service-account flows.
- Deny access by default at object level.

### 6. Device Identity Is Not Trustworthy

Refs:
- `monitoring/views.py`
- `monitoring/models.py`
- `agent.py`
- `.env.example`

Problem:
- `device_id` is client-submitted text.
- `AGENT_AUTH_TOKEN` is a static environment token with no enrollment, rotation, revocation, or device binding.
- There is no device credential lifecycle.

Why it matters:
- A fake client can impersonate another device and submit activity or policy acknowledgements.

Fix:
- Add device enrollment tokens, generated credentials, rotation, revocation, and compromised-device quarantine.
- Bind event acceptance to a known device and tenant.
- Use short-lived device JWTs or mTLS-backed credentials.

### 7. Privacy and Compliance Foundation Is Missing

Refs:
- `monitoring/models.py`
- `monitoring/views.py`
- `documentation/implementation_plan.md`
- `model.py`

Problem:
- No consent or policy acknowledgement records.
- No retention policies or deletion jobs.
- No screenshot access logs.
- No immutable admin audit model.
- No legal hold/export/deletion workflow.
- `model.py` includes file-system monitoring and risk labels that are not governed.

Why it matters:
- This product category handles student data, employee monitoring data, screenshots, browsing/activity data, and inferred productivity data.
- FTC COPPA guidance allows school consent only in an educational context and for no other commercial purpose.
- U.S. Department of Education FERPA guidance expects direct school/district control, authorized purposes, and no redisclosure for providers under the school official exception.
- California CPPA FAQ says CCPA rights include employees and job applicants, and personal information includes browsing history, geolocation, and inferences.
- GDPR text calls out large-scale regular and systematic monitoring as a scenario requiring stronger data protection governance such as a DPO.

Fix:
- Implement privacy as product infrastructure: consent, purpose limits, retention, access review, export, deletion, audit, and policy versioning.
- Do legal review before shipping screenshots, file monitoring, or productivity scoring.

Sources:
- FTC COPPA FAQ: https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions
- U.S. DOE student privacy guidance: https://studentprivacy.ed.gov/sites/default/files/resource_document/file/Student%20Privacy%20and%20Online%20Educational%20Services%20%28February%202014%29_0.pdf
- CPPA FAQ: https://cppa.ca.gov/faq.html
- GDPR text: https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng

### 8. Screenshots and Commands Are Not Production-Safe

Refs:
- `monitoring/views.py`
- `monitoring/serializers.py`
- `monitoring/admin.py`
- `investor_demo/index.html`
- `contracts/events.md`

Problem:
- Screenshot endpoint stores metadata only; there is no binary upload, object storage, encryption, redaction, retention job, legal hold, or access audit.
- Demo commands exist visually, but no command API, command ledger, permission model, acknowledgement protocol, rollback, or audit schema exists.

Why it matters:
- Screenshot and remote-control commands are the highest-risk features in a LanSchool-style product.

Fix:
- Define `Command`, `CommandAck`, `ScreenshotObject`, and `ScreenshotAccessLog`.
- Use server-generated storage keys, private object storage, encryption, retention, and scoped access.
- Require explicit policy and role checks for every command.

### 9. Tests Are Absent

Refs:
- `monitoring/tests.py`

Problem:
- Test suite ran 0 tests.

Why it matters:
- No regression protection exists for sync idempotency, authorization, WebSockets, migration safety, privacy behavior, or dashboard loading.

Fix:
- Add API, model, sync, websocket, contract, and dashboard smoke tests before further feature work.
- Make "0 tests" fail CI.

### 10. Dependency and Packaging Setup Is Not Production-Installable

Refs:
- `requirements.txt`
- `employee_tracker/settings.py`
- `model.py`

Problem:
- `daphne` is configured but missing from requirements.
- `model.py` imports `sklearn` and `joblib`, but requirements do not include `scikit-learn` or `joblib`.
- Windows desktop dependencies are mixed into server requirements.
- `pywin32` target install did not provide a working `pywintypes` import path in the temp validation.

Why it matters:
- A fresh clone cannot reliably run backend, dashboard, ML, and agent from one requirements file.

Fix:
- Split requirements:
  - `requirements/backend.txt`
  - `requirements/agent-windows.txt`
  - `requirements/ml.txt`
  - `requirements/dev.txt`
- Add platform markers for Windows-only packages.
- Add install smoke checks to CI.

## P1 High Priority Findings

### Backend and API

1. Production defaults remain unsafe.
   - `DJANGO_DEBUG` defaults true.
   - fallback `SECRET_KEY` is dev-only but still bootable.
   - `check --deploy` reports HSTS, SSL redirect, secret, secure cookie, CSRF cookie, and debug warnings.
   - Fix: fail startup in prod without real secret and explicit `DJANGO_DEBUG=false`; add prod env template.

2. WebSocket origin protection is missing.
   - `AuthMiddlewareStack` is used without `AllowedHostsOriginValidator` or `OriginValidator`.
   - Fix: validate origins and use explicit token/device auth for agent sockets.

3. WebSocket data is globally broadcast.
   - Every authenticated user receives all status events.
   - Fix: tenant/team/person scoped groups and filtered payloads.

4. Ingestion is unthrottled.
   - No DRF throttle classes, token endpoint throttling, batch size limit, request body cap, or per-device quota.
   - Fix: add throttles, max `events` length, and queue-backed ingestion.

5. `activity_sync` lacks a central serializer/schema.
   - Manual parsing allows contract drift and inconsistent validation.
   - Fix: create `ClientEventEnvelopeSerializer` and JSON Schema/OpenAPI docs.

6. Session invariants are not enforced in the database.
   - Concurrent starts can create multiple active sessions.
   - Fix: add partial unique constraint for one open session per employee and check constraints for end time.

7. Redis URL parsing drops auth/TLS/db.
   - settings only use hostname and port from `REDIS_URL`.
   - Fix: pass full Redis URL or config dict with password, DB, and TLS.

8. Admin surface is not production-hardened.
   - Default `/admin/` exposes sensitive data.
   - Fix: add SSO/2FA, IP allowlist/VPN, admin audit logs, and least-privilege admin groups.

### Agent, Sync, and Local Storage

1. Local queue semantics are weak.
   - No lease, retry counter, exponential backoff, ordering, queue size cap, or dead-letter table.
   - Fix: implement durable encrypted queue with `pending`, `in_progress`, `synced`, `dead_letter`.

2. Policy enforcement is duplicated.
   - `agent.py` and `tracker.py --mode policy` both edit hosts file with different marker formats.
   - Fix: keep one policy agent and delete the other path.

3. Hosts-file writes are not atomic.
   - No file lock, temp file replace, rollback, or integrity check.
   - Fix: use locked atomic replace and backup/restore.

4. Watchdog is not a real service.
   - It is a polling loop, uses relative `agent.py`, and detects processes by command text.
   - Fix: use Windows Service/systemd/launchd with signed installer, absolute paths, health checks, and uninstall.

5. Tracker still mixes capture and storage.
   - It imports Django and writes ORM records directly.
   - Fix: tracker should produce event envelopes and enqueue locally.

6. Idle accounting can overcount.
   - Idle time before threshold can be counted as app usage, then later recorded as idle.
   - Fix: track idle transitions and subtract/reclassify the idle window.

7. `database_handler.py` masks database failures.
   - It catches exceptions and returns `None`.
   - Fix: raise typed errors and wrap multi-statement activity writes in one transaction.

### Dashboard, Demo, and UX

1. `monitoring/dash_app.py` is broken as a production dashboard.
   - Hardcoded `employee_id = 2`.
   - DB queries run at import time.
   - Crashes when tables are not migrated.
   - Runs `debug=True`.
   - Fix: replace with authenticated Django views or callbacks with empty states.

2. Investor demo overstates readiness.
   - It shows "Backend OK", "Realtime OK", "Audit On", live grid, and commands without live integrations.
   - Fix: label sample/demo state clearly or wire indicators to real API/WebSocket health.

3. Demo accessibility is incomplete.
   - Search input has no handler.
   - Modal lacks dialog semantics, focus trap, and Escape behavior.
   - Toast lacks `aria-live`.
   - Fix: implement or remove incomplete controls.

### Documentation and Contracts

1. Docs are stale.
   - `project_review.md` still lists issues that have since been partially fixed.
   - Fix: regenerate docs after each review and classify every item as fixed, remaining, or superseded.

2. Contract is not enforceable.
   - `contracts/events.md` is prose and examples, not JSON Schema or OpenAPI.
   - Fix: add versioned JSON Schema and server/client contract tests.

3. Command and acknowledgement contracts are missing.
   - Demo commands have no backend contract.
   - Fix: define command, ack, policy publish, and audit schemas.

4. Setup docs are not executable.
   - Docs say the setup "must eventually support" basic actions.
   - Fix: write a root quickstart with exact commands and expected output.

## P2 Cleanup and Maintainability

1. Generated artifacts are tracked or present.
   - `tmp/wireframes_render/*.png` is tracked.
   - `__pycache__`, `db.sqlite3`, and logs are present as ignored files.
   - Fix: remove generated artifacts from version control or move real assets into `documentation/assets/`; keep `tmp/` ignored.

2. Migration hygiene needs cleanup before first production deploy.
   - There is an empty migration.
   - One migration says generated by Django 6.0.4 while requirements pin Django 5.2.5.
   - Duplicate merge migration could lock large tables.
   - Fix: squash or regenerate before first production data exists; batch data migrations for real data.

3. `model.py` mixes many concerns.
   - File monitoring, synthetic training, report writing, manager dashboard, CSV export, and interactive modes live in one root file.
   - Fix: move to `prototypes/ml_demo/` or split into production packages after governance.

4. Root naming is unclear.
   - "Employee-Tracker" conflicts with dual education/workforce positioning.
   - Fix: rename product/project language around neutral endpoint monitoring, or explicitly separate editions.

## Dead Code or Code To Remove From Production Path

Remove or quarantine before production packaging:

- `model.py`: prototype only; synthetic ML and local CSV reports.
- `monitoring/dash_app.py`: standalone debug dashboard; replace with real authenticated product UI.
- `monitoring/database_handler.py`: unmanaged raw SQL schema unless it becomes the official local queue layer.
- `monitoring/sync_manager.py`: keep only after queue schema, ack parsing, and UUID event IDs are fixed.
- `monitoring/tracker.py --mode policy`: duplicate of `agent.py` policy enforcement.
- `tmp/wireframes_render/*`: generated wireframe renders, not product code.
- stale review docs that contradict current code.

## Features To Cut or Defer

Cut from the first production release:

- ML productivity/risk scoring.
- File-system surveillance.
- "High-risk employee" labels.
- Screenshot streaming.
- Focus lock and launch-app commands.
- Arbitrary website push/control.
- Broad education plus workforce packaging in one undifferentiated workflow.

Keep for first production release:

- Tenant-scoped auth.
- Device enrollment.
- Policy fetch.
- Heartbeat.
- App/site activity event sync.
- Offline encrypted queue.
- Admin-visible device health.
- Policy acknowledgement.
- Immutable audit log.
- Retention deletion job.
- One dashboard backed by real data.

## Required Production Architecture

Target sequence:

```text
signed enrolled agent
-> encrypted local event queue
-> mTLS or device JWT sync
-> ingestion API
-> append-only event table
-> projection workers
-> tenant-scoped operational tables
-> tenant/team realtime rooms
-> dashboard/API
-> immutable audit/export/retention jobs
```

Core models to add before expanding features:

- `Tenant`
- `UserMembership`
- `Role`
- `Person`
- `Device`
- `DeviceCredential`
- `EnrollmentToken`
- `Policy`
- `PolicyAssignment`
- `PolicyAcknowledgement`
- `Command`
- `CommandAck`
- `AuditLog`
- `RetentionPolicy`
- `ConsentRecord`
- `Heartbeat`
- `ScreenshotObject`
- `ScreenshotAccessLog`
- `DataExportJob`
- `DeletionRequest`

## Minimum Test Gate

No release candidate should pass with fewer than these tests:

1. Dependency install smoke test for backend requirements.
2. `manage.py check` and `manage.py check --deploy` under production-like env.
3. Migration test on a fresh database.
4. API auth denial tests.
5. Tenant isolation tests.
6. Device enrollment and token expiry tests.
7. Sync idempotency tests.
8. Sync rejection/dead-letter tests.
9. WebSocket scope tests.
10. Screenshot upload/access/retention tests.
11. Policy version and acknowledgement tests.
12. Agent offline queue recovery test.
13. Dashboard empty-state smoke test.
14. Audit log immutability test.

## Suggested 30-Day Production Plan

### Week 1: Stabilize The Core

- Split requirements by backend, agent, ML, and dev.
- Add `daphne` to backend requirements.
- Remove prototype files from production packaging.
- Add root setup docs and CI smoke commands.
- Add tenant, membership, person, device, and device credential models.
- Convert event contract to JSON Schema/OpenAPI.

### Week 2: Build The Real Data Plane

- Replace direct ORM agent writes with local queue writes.
- Implement durable queue schema with retry/dead-letter.
- Fix event IDs and idempotency.
- Implement heartbeat endpoint/model.
- Add sync ack parsing and tests.

### Week 3: Privacy, Policy, And Audit

- Add consent/policy acknowledgement.
- Add immutable audit log.
- Add screenshot object model and access log.
- Add retention policy and deletion job.
- Add admin action audit.

### Week 4: Product Surface

- Replace Dash with authenticated dashboard views.
- Add device health, last seen, sync failures, and policy status.
- Add tenant-scoped realtime.
- Add reports only after real data path is stable.
- Run security review and pilot readiness review.

## Final Release Gate

The product can be called production-ready only when:

- Fresh clone installs cleanly from documented commands.
- Migrations run on a fresh database.
- Tests run and cover the data plane.
- Production deploy check has no critical warnings.
- Agent can enroll, queue, sync, retry, and report heartbeat.
- No monitoring data crosses tenant boundaries.
- Screenshots and commands have policy, authorization, audit, and retention controls.
- Demo UI labels accurately reflect real vs sample data.
- Privacy/legal controls exist in code, not only documents.
