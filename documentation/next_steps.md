# Next Steps

This folder is intentionally small. Use these files as the source of truth:

1. [Current status](current_status.md) - what is on `main`, what is wired, and what remains gated.
2. [Project review](project_review.md) - current acceptance verdict and blockers.
3. [Intern code audit](intern_code_audit.md) - strict read-only review of the new intern code.
4. [Intern next actions](intern_next_actions.md) - what each intern should do next.
5. [Architecture review](architecture_review.md) - current full-system architecture audit.
6. [Implementation plan](implementation_plan.md) - cross-cutting platform work outside intern assignments.

Shared event format:

- [Event contracts](../contracts/events.md)

Immediate priority:

1. Keep intern runtime files unchanged until each owner submits their own reviewed diff.
2. Make `/api/v1/sync/events/` the single event ingestion contract.
3. Wire tenant, person, membership, and device identity into the runtime path.
4. Move endpoint collection to a local encrypted queue and API sync path.
5. Keep screenshots, file monitoring, remote commands, and ML risk scoring gated.
6. Keep architecture guardrails green in CI.
7. Add CI checks for backend, contracts, protected paths, and intern API tests.
