# Project Review

Reviewed on: 2026-06-26
Branch: `main`

## Verdict

Status: not production-ready yet.

The repository is healthier than the previous review: split requirements exist, Django boots after the dependency fix, platform contracts have tests, intern API tests exist, and the investor demo is separated from the production core.

The remaining issue is architecture integration. Intern runtime code, production platform contracts, and the investor demo still do not run through one fully wired end-to-end path.

## Current Acceptance Status

Accepted as useful prototype work:

- Django API endpoints for health, policy fetch, activity, idle, session, screenshot metadata, and activity sync.
- Platform-neutral production contracts and invariants.
- TypeScript investor demo.
- Intern prototypes for agent activity tracking, sync, security persistence, and analytics.

Not accepted for production:

- Direct Django ORM access from endpoint tracker code.
- Direct Postgres access from sync client code.
- Global WebSocket room for all authenticated users.
- Screenshot capture, file monitoring, remote/system controls, and ML risk scoring in production paths.
- Multi-tenant customer use before tenant, membership, device, and object-permission wiring.

## Current Blockers

1. One end-to-end data path is not wired.
2. Intern sync code and backend APIs do not share one enforced v1 contract.
3. Tenant and role scoping are not wired into intern runtime endpoints.
4. Privacy, consent, audit, and retention gates are not enforced by intern runtime.
5. Deployment settings still need production environment values; `manage.py check --deploy` reports expected warnings under dev defaults.
6. Redis is required for realtime but intern API tests currently pass while logging Redis connection failures from broadcast attempts.
7. ML analytics remain prototype-only because the data contract and legal gate are not complete.

## Immediate Acceptance Criteria

Do not call the backend production-ready until:

- Fresh clone install passes from documented requirements.
- `manage.py check`, migration dry-run, platform tests, and intern tests pass in CI.
- One path works end to end: device enrollment, local encrypted queue, sync API, event storage, projection, tenant-scoped realtime, dashboard display.
- Every event is tenant, device, and person scoped.
- Every sensitive admin view/action is audited.
- Screenshot and ML risk features remain disabled until legal review is confirmed.

## Current References

- [Current status](current_status.md)
- [Intern code audit](intern_code_audit.md)
- [Implementation plan](implementation_plan.md)
- [Production audit](production_audit.md)
