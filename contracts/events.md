# Event Contracts

All client-originated events should use one envelope.

## Envelope

```json
{
  "event_id": "evt-001",
  "event_type": "activity",
  "schema_version": "1.0",
  "occurred_at": "2026-06-19T09:00:00+05:30",
  "captured_at": "2026-06-19T09:00:02+05:30",
  "device_id": "device-001",
  "employee_ref": {
    "system_username": "employee.username"
  },
  "idempotency_key": "device-001:evt-001",
  "payload": {}
}
```

Required rules:

- `event_id` is client-generated and unique.
- `idempotency_key` is stable across retries.
- Backend resolves employee identity server-side.
- Backend rejects invalid durations and impossible timestamps.

## Event Types

### activity

```json
{
  "app_name": "code.exe",
  "window_title": null,
  "duration_seconds": 120,
  "classification": "productive",
  "idle_excluded": true,
  "policy_version": "2026-06-19.1"
}
```

### idle

```json
{
  "idle_start": "2026-06-19T09:10:00+05:30",
  "idle_end": "2026-06-19T09:20:00+05:30",
  "total_idle_seconds": 600,
  "threshold_seconds": 600
}
```

### session

```json
{
  "session_id": "session-001",
  "action": "start",
  "started_at": "2026-06-19T09:00:00+05:30",
  "ended_at": null,
  "duration_seconds": null
}
```

### screenshot

```json
{
  "screenshot_id": "shot-001",
  "active_app": "code.exe",
  "capture_policy": {
    "enabled": true,
    "policy_version": "2026-06-19.1",
    "interval_seconds": 300
  },
  "file": {
    "local_path": "client-local-only",
    "mime_type": "image/png",
    "sha256": "64-character-hash"
  }
}
```

Important: backend must not trust or read arbitrary client `local_path`.

### policy

```json
{
  "policy_version": "2026-06-19.1",
  "action": "applied",
  "blocked_domains_count": 4
}
```

### heartbeat

```json
{
  "agent_version": "0.1.0",
  "status": "healthy",
  "uptime_seconds": 3600,
  "queue_depth": 0,
  "last_sync_at": "2026-06-19T09:04:55+05:30"
}
```

### sync_error

```json
{
  "failed_event_id": "evt-001",
  "endpoint": "/api/activity-sync/",
  "attempt_count": 3,
  "http_status": 500,
  "error_type": "server",
  "will_retry": true
}
```
