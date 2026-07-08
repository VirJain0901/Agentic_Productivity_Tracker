# Vikrant - Machine Learning And Analytics

Updated: 2026-07-08

Module: Machine Learning and Analytics

Primary function: generate insights and productivity intelligence.

## Verdict

The ML work is still exploration, not production analytics. The repository has root `model.py` and quarantined files under `prototypes/vikrant_ml/`. Both contain useful ideas, but both include legal-gated file monitoring and risk scoring that must not enter production. Vikrant should wait for stable contract-valid events before training anything.

## What Is Good

- The prototype compares several model families.
- It generates reports and manager summaries.
- It explores anomaly detection and feature importance.
- The quarantined files are no longer wired into Django startup.
- `prototypes/vikrant_ml/README.md` correctly states that production analytics should avoid DB credentials, direct DB access, file monitoring, and risk labels.

## Strict Findings

### P0: Root `model.py` still contains legal-gated file monitoring

Evidence:

- `model.py` imports `FileSystemEventHandler`.
- It monitors Desktop, Documents, and Downloads style paths.

Why it matters:

File-system surveillance is legally sensitive and explicitly gated out of production.

Expected direction:

Keep file monitoring out of production analytics. Use approved backend events only.

### P0: Root `model.py` still emits risk labels

Evidence:

- `model.py` calculates `risk_score` and `risk_level`.

Why it matters:

Risk scoring can affect students or employees and requires legal review, bias review, explainability, and consent.

Expected direction:

Start with descriptive analytics only.

### P0: Quarantined prototype still contains MySQL and hardcoded credentials

Evidence:

- `prototypes/vikrant_ml/m3.py` includes MySQL access and default credentials.
- `prototypes/vikrant_ml/employee_monitor.py` contains MySQL Django settings and default password text.

Why it matters:

The project backend source of truth is PostgreSQL. ML should not own DB credentials or connect directly to backend databases.

Expected direction:

Consume approved event exports or API/query outputs owned by the backend. PostgreSQL is the backend source of truth; ML code must not own DB credentials.

### P0: Data input is not stable enough for training yet

Evidence:

- Vaidehi's sync manager is not aligned with `/api/v1/sync/events/`.
- Bhumika's capture code does not yet emit v1 contract events.
- Sanskruti's v1 endpoint still needs auth, serializer validation, and durable persistence.

Why it matters:

Training on unstable or synthetic shapes will create throwaway models and misleading metrics.

Expected direction:

Work on feature definitions and model-card templates now. Start model training only after approved events are stored consistently.

### P1: Training labels are synthetic

Evidence:

- `model.py` generates random feature distributions and labels from its own formulas.

Why it matters:

Accuracy on synthetic labels proves code execution, not real model quality.

Expected direction:

Create a model card that clearly marks synthetic results as non-production.

### P1: Model artifacts are written to local working directory

Evidence:

- The prototype writes `.pkl`, `.json`, `.csv`, and report outputs beside the script.

Why it matters:

Production needs artifact versioning, access control, reproducibility, and cleanup.

Expected direction:

Use a controlled artifact directory and model registry plan later. For now, document outputs only.

### P2: Student and employee contexts need separate interpretation

Evidence:

- Current labels focus on employee productivity/risk.

Why it matters:

AxonDesk supports students and employees. The same metric cannot mean the same thing in class, training, and workplace contexts.

Expected direction:

Use neutral analytics terms: focus window, active time, idle distribution, app category, device health, policy hit count.

## Next Assignment

Build a feature extraction spec from approved events only:

- `activity`
- `idle`
- `session.start`
- `session.end`
- `heartbeat`
- `policy`
- `sync_error`

Allowed outputs:

- Active time.
- Idle distribution.
- App category summary.
- Focus windows.
- Device health.
- Sync reliability.
- Policy hit counts.

Blocked outputs:

- `risk_score`
- `risk_level`
- file-system surveillance indicators
- disciplinary recommendations

Acceptance:

- Feature extraction runs on contract-valid event dictionaries.
- Unknown event types are ignored or rejected predictably.
- No DB credentials exist in new ML code.
- No production path imports `prototypes/vikrant_ml`.
- Model card states whether data is synthetic, sampled, or production-reviewed.
- No model training PR is opened until the v1 event pipeline is stable.
