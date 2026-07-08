# Employee Tracker

This repository is currently a prototype bundle moving toward a production
student/employee monitoring platform. Start with the production audit before
shipping anything:

```text
documentation/production_audit.md
```

Latest implementation status:

```text
documentation/current_status.md
```

Current architecture review and intern handoff:

```text
documentation/architecture_review.md
documentation/intern_next_actions.md
```

## Fresh Clone Bootstrap

Use Python 3.12.

### Backend API

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/backend.txt
copy .env.example .env
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
daphne employee_tracker.asgi:application
```

### CI Smoke

```powershell
python scripts/ci_smoke.py
python scripts/check_architecture_guardrails.py
```

The smoke runner fails if zero tests are discovered.

### Optional Windows Agent Prototype

```powershell
python -m pip install -r requirements/agent-windows.txt
```

This installs Windows-only desktop capture/policy dependencies. Do not install
it on the backend server image.

### Optional ML Prototype

```powershell
python -m pip install -r requirements/ml.txt
```

The ML prototype is legal-gated and not part of the production path. Do not
enable file-system surveillance, screenshot streaming, ML risk scoring, or
remote commands until privacy, consent, audit, retention, and legal review are
complete.

## Requirement Files

- `requirements/backend.txt` - Django API, realtime server, and backend runtime.
- `requirements/agent-windows.txt` - Windows-only desktop agent dependencies.
- `requirements/ml.txt` - prototype ML dependencies.
- `requirements/dev.txt` - CI/development backend baseline.
- `requirements.txt` - legacy all-in-one install path kept for compatibility.

## Local Queue

The sync subsystem uses a local SQLite-backed queue (`sync_queue.db`) to support offline event collection and reliable delivery.

### Features

- Atomic event leasing via `fetch_and_lock_events()`
- Retry handling with configurable retry limits
- Dead-letter queue support
- ACK processing (`accepted`, `duplicate`, `rejected`)
- Event status tracking (`pending`, `in_progress`, `synced`, `dead_letter`)

### Running Tests

```bash
python -m pytest monitoring/test_local_queue.py -v
```

## Sync Manager

The sync manager is responsible for delivering queued events from the local SQLite queue to the backend API.

### Features

- Batch-based event synchronization
- Contract-compliant event envelopes
- Backend ACK handling
- Duplicate event detection support
- Retry handling for network and server failures
- JWT-based authentication and token refresh
- Queue status updates (`pending`, `in_progress`, `synced`, `dead_letter`)
- Automatic sync interval processing

### Configuration

The sync manager uses environment variables for configuration:

- `BACKEND_SYNC_URL`
- `TENANT_ID`
- `DEVICE_ID`
- `CLIENT_VERSION`
- `SCHEMA_VERSION`
- `JWT_TOKEN`
- `JWT_REFRESH_TOKEN`

### Running the Sync Manager

```bash
python sync_manager.py
```