# Vaidehi - Storage And Sync Client

Updated: 2026-07-08

Module: Storage and Sync Client

Primary function: persist endpoint events locally and reliably transmit them to the backend.

## Verdict

The storage direction improved: a local SQLite queue now exists and the sync manager has ACK/retry structure. It is still not aligned with the v1 contract, and the retry path can strand events in `in_progress`.

## What Is Good

- Local SQLite queue exists in `monitoring/local_queue.py`.
- ACK handling distinguishes accepted, duplicate, and rejected outcomes.
- Retry and token refresh flows are represented.
- Queue stats are local.
- There is no need for endpoint direct PostgreSQL access in the new queue path.

## Strict Findings

### P0: Retry can strand events in `in_progress`

Evidence:

- `fetch_and_lock_events` changes rows from `pending` to `in_progress`.
- `send_events` calls `increment_retry` when HTTP/network/ACK parsing fails.
- `increment_retry` updates retry metadata but does not set regular failed rows back to `pending`.

Why it matters:

After a network failure, rows can remain locked forever and never retry.

Expected direction:

Until max retries, `increment_retry` should set `status='pending'` and a future `next_retry_time`. At max retries, move to `dead_letter`.

### P0: Sync payload does not match v1 contract

Evidence:

- `BACKEND_SYNC_URL` defaults to `/api/activity-sync/`.
- `build_batch` sends `created_at` instead of required `occurred_at`.
- Event items include extra fields such as `user_id`, `source_module`, and `created_at`.
- v1 contract allows only the agreed event fields.

Why it matters:

The backend v1 serializer should reject these events once contract validation is enforced.

Expected direction:

Emit only v1 event fields: `schema_version`, `tenant_id`, `device_id`, `event_id`, `idempotency_key`, `event_type`, `occurred_at`, `captured_at`, and `payload`.

### P0: ACK rejected reason uses the wrong field

Evidence:

- `contracts/sync_ack.schema.json` requires rejected items to contain `event_id` and `error`.
- `handle_ack` reads `item.get("reason", "rejected")`.

Why it matters:

The sync client loses the actual backend rejection reason and records a generic error.

Expected direction:

Read `error` from rejected ACK items and store it as the dead-letter reason.

### P1: Tenant/device identity is not first-class in the queue

Evidence:

- `monitoring/local_queue.py` table has no `tenant_id` or `device_id` columns.
- `queue_row_to_event` injects `TENANT_ID` and `DEVICE_ID` from environment.

Why it matters:

If configuration is missing or changes between enqueue and sync, queued events can be sent with wrong or empty identity.

Expected direction:

Store tenant/device with the queued event or enforce that the queue is bound to one enrolled device identity.

### P1: Queue payload is not encrypted

Evidence:

- `payload` is stored as plain JSON text in SQLite.

Why it matters:

Endpoint data can contain sensitive activity metadata. Local storage needs an encryption plan or explicit legal/security exception.

Expected direction:

Add an encryption hook or document the OS-protected storage boundary before production use.

### P2: Agent/sync imports are not covered by backend smoke

Evidence:

- `requirements/dev.txt` includes backend requirements only.
- `aiofiles` and `aiohttp` live in `requirements/agent-windows.txt`.
- Backend smoke does not prove the sync manager imports under the agent dependency set.

Why it matters:

Client breakage can pass CI unless there is a separate agent smoke path.

Expected direction:

Add an agent smoke check that installs `requirements/agent-windows.txt` and imports `monitoring.sync_manager` and `monitoring.local_queue`.

## Next Assignment

Fix and align the existing local queue adapter:

- Return failed in-progress events to `pending` until retry limit.
- Default sync URL to `/api/v1/sync/events/`.
- Emit v1 event fields only.
- Use rejected ACK `error`.
- Store or strictly bind tenant/device identity.
- Add encrypted payload hook or documented storage boundary.

Acceptance:

- Duplicate ACK marks local row synced.
- Rejected ACK moves local row to dead-letter with backend `error`.
- Network failure increments retry count and preserves payload.
- Queue stats do not connect to PostgreSQL.
- Agent smoke imports pass under agent requirements.
