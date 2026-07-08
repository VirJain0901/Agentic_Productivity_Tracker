# Bhumika - Agent And Activity Monitoring

Updated: 2026-07-08

Module: Agent and Activity Monitoring

Primary function: capture user activity, idle time, active app/window, blocked attempts, and screenshot metadata from the endpoint.

## Verdict

Useful capture work exists, but the runtime is still too tightly coupled to Django ORM, local system controls, and screenshot capture. For production, the capture layer should produce contract-valid events and hand them to Vaidehi's local queue. It should not directly write Django models, edit hosts/browser policy, or start screenshot capture without legal-gated policy approval.

## What Is Good

- Activity, idle, session, blocked-attempt, and screenshot concepts are represented.
- Buffers and bulk inserts reduce database write frequency.
- Idle and app usage validation exists on the backend side.
- Screenshot metadata is stored separately from the binary file path.

## Strict Findings

### P0: Capture path still writes directly through Django ORM

Evidence:

- `monitoring/tracker.py` calls `django.setup()`.
- It imports `Employee`, `IdleTime`, `ProductiveAppUsage`, `Session`, `ActivityLog`, `BlockedWebsiteAttempt`, and `ScreenshotLog`.
- It directly creates or updates those models during endpoint tracking.

Why it matters:

An installed desktop agent should not need direct Django ORM access. That couples the endpoint to backend internals, breaks offline operation, and makes tenant/device identity difficult to enforce.

Expected direction:

Create event dictionaries, enqueue locally, and let the sync client send them to `/api/v1/sync/events/`.

### P0: Screenshot capture is still in the default runtime path

Evidence:

- `monitoring/tracker.py` starts `capture_screenshots(employee)` inside the main `asyncio.gather`.
- `capture_screenshots` calls `pyautogui.screenshot()` and saves local files.

Why it matters:

Screenshot capture is legal-gated. It must require consent, tenant policy, retention, access audit, and legal review before production use.

Expected direction:

Screenshot capture defaults off. The capture function must read an approved policy state and return no event when disabled. Do not add streaming or binary upload paths.

### P1: Screenshot storage and cleanup paths still disagree

Evidence:

- Capture writes under `BASE_DIR/screenshots`.
- Cleanup checks `BASE_DIR/media/screenshots`.

Why it matters:

Retention will not delete what capture writes, so sensitive data can remain unmanaged.

Expected direction:

Use one storage root, one relative object key strategy, and one retention job after legal gating is approved.

### P1: MD5 is used for screenshot metadata names

Evidence:

- `monitoring/tracker.py` uses `hashlib.md5` for screenshot metadata naming.

Why it matters:

MD5 is not acceptable for integrity-oriented identifiers. It also communicates the wrong security posture.

Expected direction:

Use UUIDs for names and SHA-256 for file integrity.

### P1: Offline queue is still a JSON file in tracker

Evidence:

- `OFFLINE_QUEUE_FILE = "offline_queue.json"`.
- Queue writes use plain `open` and `json.dump`.

Why it matters:

The queue is not encrypted, locked, transactional, or robust against concurrent writes and partial file corruption.

Expected direction:

Send events to Vaidehi's SQLite local queue abstraction instead of writing JSON directly.

### P1: Events do not yet carry the shared v1 identity fields

Evidence:

- Tracker creates model rows and local JSON records, not v1 event envelopes.
- The v1 contract requires `schema_version`, `tenant_id`, `device_id`, UUID `event_id`, `idempotency_key`, `event_type`, `occurred_at`, `captured_at`, and `payload`.

Why it matters:

Vaidehi and Sanskruti cannot sync or validate events unless Bhumika emits the same contract shape.

Expected direction:

Build a pure event-builder layer that receives tenant/device identity from agent configuration and outputs contract dictionaries only.

### P2: System policy logic is mixed into capture

Evidence:

- `monitoring/tracker.py` disables private browsing and updates hosts.

Why it matters:

This overlaps with Kiara's security/persistence module and creates duplicate rollback behavior.

Expected direction:

Capture module reports activity. Kiara's module owns local enforcement.

## Next Assignment

Build a pure event-builder layer for:

- `activity`
- `idle`
- `session.start`
- `session.end`
- `heartbeat`
- `policy`
- `sync_error`
- screenshot metadata only when policy is enabled and legal gates are active

Acceptance:

- Event builder works without Django ORM.
- Event IDs are UUIDs.
- Negative durations are rejected.
- Required v1 identity fields are present.
- Screenshot event is not produced when screenshot policy is disabled.
- Hosts/browser policy changes are not part of the capture core.
