# Implementation Plan

This is project-level work outside the current intern module assignments.

**Intern boundary:** intern-owned source files are not modified by this plan. Where a fix touches behavior that lives in an intern file, implement it in a new adapter/wrapper module and raise the direct intern-code change for human review. Do not edit intern files in place.

## 0. Scope And Positioning

This is one **endpoint monitoring platform** with two editions that share a single core and differ only in policy and labeling:

- **Education edition** - school/district tenant, classroom scope, teacher/admin roles.
- **Workforce edition** - organization tenant, team/department scope, manager/admin roles.

To avoid dual-positioning confusion, shared code should use neutral terms:

- A **Tenant** owns **Persons** and **Devices**.
- Humans act through **Roles**.
- The monitored subject is a **monitored person**, not "employee" or "student" in shared code.
- Edition-specific language belongs only in the UI layer.

## 1. Integration Architecture

Target flow, tenant-scoped at every hop:

```text
enrolled client agent
  -> encrypted local queue
  -> authenticated sync API (device JWT / mTLS)
  -> backend canonical database (append-only events)
  -> projection workers
  -> tenant operational tables
  -> tenant/team/class realtime channel
  -> dashboard / API
  -> audit + export + retention jobs
```

Rules:

- Django-managed backend data is the **single source of truth**.
- Client storage is only a temporary offline queue, never authoritative.
- Every client event uses the shared contract in `contracts/events.md`, promoted from prose to a **versioned JSON Schema / OpenAPI** spec.
- Every person, device, policy, event, and command is **owned by a tenant**.
- No query, channel, or view may return data across tenant boundaries.

### Idempotency

- Event IDs are **UUID/ULID generated on the device**, never derived from a local row ID.
- Uniqueness is **composite**: `(tenant, device, event_id)` and `(tenant, idempotency_key)`.
- After a migration grace period, the backend rejects non-UUID IDs.
- Retries dedupe against these keys; a duplicate is a success, not an error.

### Sync Acknowledgement And Dead Letter

- The sync API returns `{ accepted, duplicates, rejected }`.
- A `207` response is **not** blanket success.
- The client marks a local row `synced` only if its event is in `accepted` or a confirmed `duplicate`.
- Rejected rows move to a **dead-letter** state with error reason, retry count, and operator visibility. They are never silently dropped.

### Endpoints

Core first release:

- `POST /api/enroll/` - exchange an enrollment token for a device credential.
- `POST /api/activity-sync/` - batched event ingestion, envelope-validated and throttled.
- `GET /api/monitoring/policies/` - tenant + device scoped policy fetch.
- `POST /api/heartbeat/` - liveness, agent health, and sync stats.
- `GET /api/health/` - service health only; no tenant data.

Gated behind legal/privacy review:

- `POST /api/screenshots/` - binary upload to private object storage.
- `POST /api/commands/`
- `POST /api/commands/{id}/ack/`

## 2. Core Data Model

Add these before building more features:

- Tenancy and identity: `Tenant`, `UserMembership`, `Role`, `Person`, `Device`, `DeviceCredential`, `EnrollmentToken`.
- Events and policy: append-only event table, `Heartbeat`, `Policy`, `PolicyAssignment`, `PolicyAcknowledgement`.
- Governance: `AuditLog`, `RetentionPolicy`, `ConsentRecord`, `DataExportJob`, `DeletionRequest`.
- Gated features: `Command`, `CommandAck`, `ScreenshotObject`, `ScreenshotAccessLog`.

Database invariants:

- Partial unique constraint: at most one open session per person.
- Check constraints on session end time.
- All foreign keys carry tenant ownership so isolation is enforceable at the query layer.
- Object-level permissions deny by default.

## 3. Setup And Developer Experience

Keep:

- `.env.example`
- `docker-compose.infrastructure.yml`

Split dependencies:

```text
requirements/backend.txt        # Django, channels, daphne, DRF, psycopg, redis
requirements/agent-windows.txt  # pywin32 etc., with platform markers
requirements/ml.txt             # scikit-learn, joblib; prototype only
requirements/dev.txt            # test and lint tooling
```

Executable quickstart:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/backend.txt -r requirements/dev.txt
cp .env.example .env
docker compose -f docker-compose.infrastructure.yml up -d
python manage.py check
python manage.py migrate
daphne employee_tracker.asgi:application
```

Windows activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

Expected result:

- `manage.py check` passes with `daphne` installed.
- Migrations apply on a fresh database.
- Server boots.

## 4. Contracts And API Hardening

- Promote `contracts/events.md` to a versioned JSON Schema + OpenAPI contract.
- Add a `ClientEventEnvelopeSerializer` so ingestion uses one validation path.
- Add contract tests that submit the exact documented envelope from server and client sides.
- Define and version command, acknowledgement, policy-publish, and audit schemas.
- Add DRF throttles, max events per batch, request body caps, and per-device quota.
- Validate WebSocket origins with `AllowedHostsOriginValidator` / `OriginValidator`.
- Authenticate agent sockets with device credentials.

## 5. Testing And QA

CI fails if **0 tests run**.

Minimum coverage:

- API tests: activity, idle, session, policy, heartbeat, sync, screenshot gated path.
- Auth tests: unauthenticated denial and least-privilege checks.
- Tenant isolation: no cross-tenant reads via API or WebSocket.
- Device enrollment: token issue, credential exchange, expiry, rotation, revocation.
- Sync idempotency: duplicate prevention via UUID + composite keys.
- Sync rejection/dead-letter: rejected rows quarantined, not dropped.
- Offline queue recovery: agent restart resumes pending sync.
- WebSocket scope test for the right tenant/team/class only.
- Migration test on a fresh database.
- Audit log immutability test.
- Dashboard empty-state smoke test.
- Analytics feature-extraction test for prototype path only.
- Agent manual QA checklist for OS-level behavior.

## 6. Dashboard And Admin UX

Required tenant-scoped, role-gated, audited views:

- Overview.
- Person detail.
- Live status.
- Sync-failure and unhealthy-device view.
- Reports/export.

Screenshot review and command surfaces are gated.

Hardening:

- Replace the standalone Dash app with authenticated Django views/callbacks that have real empty states.
- Roles are explicit: tenant admin, manager/teacher, compliance auditor, monitored person, device service account.
- Every sensitive view checks role, tenant, and object permission.
- Every sensitive access writes an audit record.
- Harden `/admin/` with SSO/2FA, IP allowlist, least-privilege groups, and admin-action audit.

## 7. Privacy, Compliance And Audit

Privacy is product infrastructure, not documentation.

Implement:

- Monitoring policy acknowledgement and consent records.
- Policy version tracking.
- Screenshot retention rules, access logs, and server-generated storage keys on encrypted private storage.
- Immutable admin-action audit logs.
- Data export and deletion workflows, including legal hold.

Legal gate:

- Screenshot streaming.
- File-system monitoring.
- ML productivity/risk scoring.
- Remote commands.

These features do **not** ship until governance exists in code and a human confirms legal review.

## 8. Deployment And Operations

- Backend deployment checklist.
- Fail startup in production without a real `SECRET_KEY` and explicit `DJANGO_DEBUG=false`.
- Clear `check --deploy` warnings: HSTS, SSL redirect, secret, session cookie, CSRF cookie, debug.
- Full Redis URL handling, including password, DB index, and TLS.
- Agent install/uninstall via signed installer.
- Real OS service: Windows Service, systemd, or launchd.
- Start-on-boot behavior.
- Heartbeat reporting.
- Device last-seen status.
- Sync-failure visibility.
- Operations runbook.
- Migration-hygiene pass before production data.

## Phased Delivery

Each phase has an acceptance bar; the next phase does not start until the current phase is green.

1. **Stabilize** - split requirements, add `daphne`, make prototype files import-safe, executable quickstart, CI smoke, fail-on-0-tests.
   Acceptance: fresh clone installs and `manage.py check` passes.
2. **Tenancy and identity** - core models, tenant-scoped channels, device enrollment, deny-by-default permissions.
   Acceptance: isolation and enrollment tests pass.
3. **One end-to-end event path** - device encrypted queue -> sync API -> canonical events -> projection -> dashboard tile, with UUID idempotency and dead-letter.
   Acceptance: offline-recovery and idempotency tests pass.
4. **Tests for that path** - contract, sync, websocket, migration, audit immutability.
   Acceptance: data-plane suite is green in CI.
5. **Dashboard visibility** - authenticated views, device health, sync failures, policy status.
   Acceptance: empty-state and role tests pass.
6. **Privacy and audit** - consent, audit log, retention/deletion; screenshot/command models behind the gate.
   Acceptance: policy acknowledgement, retention, and audit tests pass.
7. **Deployment packaging** - installers, service, runbook, production settings.
   Acceptance: deploy check has no critical warnings and the agent enrolls, queues, syncs, and heartbeats on a clean machine.

## Definition Of Done

The product is production-ready only when:

- A fresh clone installs from documented commands.
- Migrations run on a fresh database.
- Tests cover the data plane.
- Deploy check has no critical warnings.
- The agent can enroll, queue, sync, retry, and report heartbeat.
- No monitoring data crosses tenant boundaries.
- Screenshots and commands have policy, authorization, audit, and retention controls.
- The demo UI labels real vs sample data.
- Privacy/legal controls exist in code, not only documents.

## Investor Demo

A standalone product demo shell exists at:

```text
investor_demo/index.html
```

It covers the intended end-to-end product experience without changing intern-owned source files. Its readiness indicators and live grid/commands are **sample state** until wired to real `/api/health/` and WebSocket health.

## Product Accountability Map

| Area | Accounted By | Demo Status | Real Integration Status | Legal Gate |
| --- | --- | --- | --- | --- |
| Tenant isolation | Plan / backend | Implied | Needs tenancy + membership models | No |
| Device identity and enrollment | Plan / agent | Implied | Needs enrollment tokens + credential lifecycle | No |
| Authorization and roles | Plan / backend | Implied | Needs roles + object-level permissions | No |
| Live class/team dashboard | Project shell | Shown | Needs tenant-scoped backend data | No |
| Offline sync | Contract | Represented | Needs encrypted queue + sync API + dead-letter | No |
| Audit trail | Project shell | Shown | Needs immutable backend audit model | No |
| Reports | Project shell | Shown | Needs real stored records | No |
| Device operations | Project shell | Shown | Needs heartbeat + health endpoints | No |
| Web/app policy | Project shell + security later | Shown | Needs policy endpoint + agent enforcement | No |
| Student/employee screen preview | Project shell + agent later | Sample screens | Needs agent snapshot/stream + object storage | Yes |
| Teacher/manager commands | Project shell + realtime later | Sample acks | Needs command API + ack ledger | Yes |
| Analytics / risk signals | Project shell + ML later | Sample signals | Needs governed feature extraction | Yes |
| Deployment | Plan | Accounted | Needs packaging/installers | No |
