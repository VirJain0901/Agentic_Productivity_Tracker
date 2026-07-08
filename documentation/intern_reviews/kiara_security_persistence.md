# Kiara - Security And System Persistence

Updated: 2026-07-08

Module: Security and System Persistence

Primary function: keep the endpoint service running and enforce local policy safely.

## Verdict

The agent/security work has useful pieces: token use exists, marker-based hosts changes are safer, and heartbeat support gives operations visibility. The current agent is not aligned with the new backend identity requirements because it does not send tenant/device identity to policy fetch or heartbeat.

## What Is Good

- Watchdog checks for an agent process and restarts it.
- `subprocess.Popen(..., shell=False)` is used.
- `CREATE_NO_WINDOW` is used for hidden launch on Windows.
- Agent sends heartbeat and policy version.
- Hosts enforcement uses managed markers in `agent.py`.
- `watchdog.lock` is no longer tracked in git.

## Strict Findings

### P0: Agent does not send required tenant/device identity

Evidence:

- Backend `heartbeat` requires `tenant_id`, `device_id`, and `hostname`.
- Backend `monitoring_policies` requires `tenant_id` and `device_id` query parameters.
- `agent.py` heartbeat payload includes hostname, policy version, agent version, and status only.
- `agent.py` policy fetch calls `BACKEND_URL` without tenant/device query parameters.

Why it matters:

The current agent cannot satisfy the backend contract. Heartbeat will be rejected, and policy fetch will fail or be incorrectly scoped.

Expected direction:

Read tenant/device identity from enrollment/config and include it in policy fetch and heartbeat.

### P0: Policy tenant validation must be coordinated with Sanskruti

Evidence:

- Backend policy endpoint currently trusts caller-supplied `tenant_id`.
- Agent-side tenant/device identity is not meaningful until the backend verifies it against the authenticated user/device.

Why it matters:

Local policy enforcement is only safe if the policy came from the device's actual tenant scope.

Expected direction:

Coordinate with Sanskruti: backend rejects tenant mismatch, agent sends enrolled tenant/device identity.

### P1: Agent still prints sensitive auth responses

Evidence:

- `agent.py` prints token response status and response text.

Why it matters:

Auth errors and token payloads can leak into console logs, service logs, screen captures, or support transcripts.

Expected direction:

Log sanitized status codes only. Never print token bodies or auth response text.

### P1: Polling interval environment variable is still ignored

Evidence:

- `POLLING_INTERVAL` is read.
- Main loop sleeps with hardcoded `time.sleep(5)`.

Why it matters:

Operators cannot tune load or heartbeat frequency through config.

Expected direction:

Use the configured polling interval and enforce safe min/max bounds.

### P1: Not a real managed Windows service yet

Evidence:

- `watchdog_service.py` is a Python loop.
- PowerShell scripts create scheduled-task style startup behavior.

Why it matters:

Production needs clear install, update, uninstall, restart policy, permissions, logging, and rollback.

Expected direction:

Document and implement a service lifecycle with signed config and rollback.

### P1: Local system-control changes are still not audited

Evidence:

- Hosts and browser policy changes are not written to immutable audit records.

Why it matters:

Local enforcement changes affect user systems and must be explainable and reversible.

Expected direction:

Emit policy-change audit events through the approved local queue.

### P2: Policy implementation is duplicated

Evidence:

- `secure_hosts_policy.py`, `agent.py`, and `monitoring/tracker.py` all contain policy/hosts behavior.

Why it matters:

Duplicate local enforcement creates inconsistent markers, rollback, and validation rules.

Expected direction:

Own one local enforcement API and have other modules call that API.

## Next Assignment

Define managed policy agent behavior:

- Signed policy bundle format.
- Device credential requirements.
- Service install/update/uninstall plan.
- Local lock-file lifecycle.
- Rollback ledger.
- Audit event format for local changes.
- Tenant/device identity for heartbeat and policy fetch.

Acceptance:

- Missing token blocks policy sync and heartbeat.
- Missing tenant/device identity blocks policy sync and heartbeat.
- Unsigned policy is rejected.
- Rollback restores previous hosts/browser policy state.
- No tracked runtime lock files.
- No auth response bodies are printed.
