# Intern Next Actions

Updated: 2026-07-08

Purpose: strict next steps after the latest read-only audit. Each intern should stay inside their assigned module unless a separate integration task is opened and reviewed.

Rule for everyone: no broad rewrites, no changes to another intern's files, and every PR must include the exact command output for checks run locally.

## Shared Contract For Everyone

Target production path:

```text
agent capture -> device-side SQLite queue -> /api/v1/sync/events/ -> PostgreSQL source of truth -> tenant-scoped dashboard and reports
```

Shared requirements:

- Backend source of truth is PostgreSQL.
- SQLite is allowed only as a device-side offline queue.
- Events must include `schema_version`, `tenant_id`, `device_id`, UUID `event_id`, `idempotency_key`, `event_type`, `occurred_at`, `captured_at`, and `payload`.
- ACK response must be exactly `accepted`, `duplicates`, and `rejected`.
- Rejected ACK items must include `event_id` and `error`.
- Screenshot streaming, file-system surveillance, remote commands, and ML risk scoring stay out of production until legal review, consent, audit, and retention gates are active.

## Immediate Team Blocker

The migration conflict is no longer the lead blocker. The current blocker is v1 contract alignment:

- Backend v1 sync path exists at `/api/v1/sync/events/`, but it still needs a v1 serializer, auth, tenant/device verification, and durable storage.
- Agent and sync client still produce or request legacy shapes in several places.
- Policy fetch and heartbeat require tenant/device identity, but the current agent does not send those fields.
- CI smoke is currently not green because requirements hygiene reports duplicate `python-decouple`.

Acceptance for the next integration round:

- `python manage.py check` passes.
- `python manage.py makemigrations --check --dry-run` passes.
- Requirements hygiene passes.
- v1 sync contract tests cover valid events, invalid fields, duplicate ACKs, and rejected ACK error shape.
- Agent, queue, and backend agree on the same event fields.

## Bhumika: Agent And Activity Monitoring

Next task: make capture produce contract-valid event dictionaries instead of direct runtime side effects.

Deliverables:

- Event builder for activity, idle, session start/end, heartbeat, blocked attempt, and screenshot metadata.
- No direct Django ORM access in the capture core.
- Screenshot event generation must return nothing when screenshot policy is disabled.
- Screenshot path, retention path, and metadata hash strategy must be consistent.
- Hosts/browser policy changes must stay outside the capture module.

Acceptance:

- Idle duration cannot be negative.
- App usage duration cannot exceed the max event window.
- Events include tenant/device identity supplied by the agent configuration.
- Screenshot event is not produced when policy is off.
- Capture core can be unit-tested without Django startup.

Details: [Bhumika review](intern_reviews/bhumika_agent_activity.md)

## Vaidehi: Storage And Sync Client

Next task: align the SQLite queue and sync manager with the v1 event and ACK contract.

Deliverables:

- Local queue keeps `pending`, `in_progress`, `synced`, and `dead_letter`.
- Retry failure returns regular events to `pending` until the retry limit is reached.
- Sync payload uses `occurred_at`, not `created_at`.
- Sync default target is `/api/v1/sync/events/`.
- ACK parser uses `accepted`, `duplicates`, and rejected item `error`.
- Queue stores or injects tenant/device identity predictably.

Acceptance:

- Duplicate ACK marks row synced.
- Rejected ACK moves row to dead-letter with the backend `error`.
- Network failure increments retry count and preserves payload for retry.
- No desktop client direct PostgreSQL access.
- Queue stats work from local queue only.

Details: [Vaidehi review](intern_reviews/vaidehi_storage_sync.md)

## Sanskruti: Backend And Real-Time System

Next task: make the v1 API and policy endpoints tenant-safe and contract-stable.

Deliverables:

- Add v1 sync serializer in `platform_api`, not legacy `monitoring`.
- Add ACK contract tests under root `tests/`.
- Require auth and tenant/device verification for v1 sync.
- Replace the in-memory v1 event store with durable tenant/device-scoped persistence or an approved adapter.
- Fix `monitoring_policies` so supplied `tenant_id` must match the authenticated employee tenant.
- Keep legacy `/api/activity-sync/` stable until v1 is proven by tests.

Acceptance:

- Unauthenticated v1 sync is rejected.
- Cross-tenant sync and policy requests are denied.
- Duplicate event returns `duplicates`.
- Rejected event returns `{event_id, error}`.
- Project URL test proves `/api/v1/sync/events/` is wired.

Details: [Sanskruti review](intern_reviews/sanskruti_backend_realtime.md)

## Kiara: Security And System Persistence

Next task: align the agent service, policy fetch, heartbeat, and local enforcement with tenant/device identity.

Deliverables:

- Agent sends `tenant_id` and `device_id` for policy fetch and heartbeat.
- Token handling never prints auth response bodies.
- Main loop uses configured polling interval with safe bounds.
- Signed policy bundle format.
- Service install/update/uninstall design with rollback.
- Audit event for every local policy change.

Acceptance:

- Missing token prevents policy sync and heartbeat.
- Missing tenant/device identity prevents policy sync and heartbeat.
- Unsigned policy is rejected.
- Local policy rollback restores previous state.
- No tracked runtime artifacts are created.

Details: [Kiara review](intern_reviews/kiara_security_persistence.md)

## Vikrant: Machine Learning And Analytics

Next task: keep ML as descriptive analytics over approved event contracts only.

Deliverables:

- Feature schema using activity, idle, session, heartbeat, sync-health, and policy-hit events.
- Descriptive analytics: active time, idle distribution, app category summary, focus windows, device health, sync reliability.
- Model card template for future ML work.
- No file-system monitoring, no `risk_score`, and no `risk_level` in production path.
- No MySQL/PostgreSQL credentials inside ML scripts.

Acceptance:

- Feature extraction works on contract-valid event dictionaries.
- Unknown event types are ignored or rejected predictably.
- No file-system events are consumed.
- No risk label is emitted.
- Prototype files are not imported by production runtime.

Details: [Vikrant review](intern_reviews/vikrant_ml_analytics.md)

## Review Order

1. Sanskruti and Vaidehi finalize the v1 event and ACK contract.
2. Kiara updates agent identity/config so policy and heartbeat can pass backend validation.
3. Bhumika emits only queue-ready contract events.
4. Sanskruti protects v1 sync and policy endpoints with tenant/device checks.
5. Vikrant consumes only approved stored events after the data path is stable.
