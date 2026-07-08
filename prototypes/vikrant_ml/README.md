# Vikrant ML Prototype

This folder preserves Vikrant's uploaded ML/MySQL experiments for review.

Status: prototype/reference only. It is not wired into the AxonDesk production runtime.

Do not import this folder from `manage.py`, `employee_tracker/settings.py`, or production API paths.

Before any ML work can move toward production, it must be refactored into a module that:

- Consumes approved PostgreSQL-backed backend events through agreed contracts.
- Avoids direct database credentials and direct MySQL/PostgreSQL client access from analytics scripts.
- Emits descriptive analytics first, not `risk_score` or high-risk labels.
- Excludes file-system monitoring from the production path.
- Includes tests for feature extraction and documented model evaluation.
