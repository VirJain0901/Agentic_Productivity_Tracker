"""Repository architecture guardrails.

This script checks lightweight project-level rules that should remain true
while intern-owned runtime code is being integrated through reviewed adapters.
It intentionally avoids importing Django or intern modules.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REQUIRED_DOCS = {
    "documentation/current_status.md",
    "documentation/project_review.md",
    "documentation/intern_code_audit.md",
    "documentation/intern_next_actions.md",
    "documentation/architecture_review.md",
}

STALE_DOCS = {
    "documentation/intern_reviews.md",
}

REQUIRED_CONTRACTS = {
    "contracts/client_event.schema.json",
    "contracts/sync_ack.schema.json",
    "contracts/health.schema.json",
    "contracts/audit_log.schema.json",
    "contracts/command.schema.json",
}

REQUIRED_GITIGNORE_PATTERNS = {
    "screenshots/",
    "media/",
    "media/screenshots/*.png",
}

FORBIDDEN_ROOT_RUNTIME_FILES = {
    "admin.py",
    "apps.py",
    "ci_smoke.py",
    "employee_admin.py",
    "employee_apps.py",
    "employee_models.py",
    "employee_monitor.py",
    "m3.py",
    "models.py",
    "urls.py",
}

REQUIRED_CI_COMMANDS = {
    "scripts/check_protected_paths.py",
    "scripts/check_architecture_guardrails.py",
    "scripts/check_requirements_hygiene.py",
    "scripts/validate_contracts.py",
    "manage.py check",
    "makemigrations --check --dry-run",
}

GATED_FEATURE_TERMS = {
    "screenshot",
    "file monitoring",
    "remote commands",
    "ML risk",
    "legal gate",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _git_ls_files(root: Path, pathspec: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", pathspec],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_repository(root: Path, strict_privacy_artifacts: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for relative_path in sorted(REQUIRED_DOCS):
        if not (root / relative_path).exists():
            errors.append(f"missing required architecture document: {relative_path}")

    for relative_path in sorted(STALE_DOCS):
        if (root / relative_path).exists():
            errors.append(f"stale architecture document must stay removed: {relative_path}")

    for relative_path in sorted(REQUIRED_CONTRACTS):
        if not (root / relative_path).exists():
            errors.append(f"missing required contract schema: {relative_path}")

    for relative_path in sorted(FORBIDDEN_ROOT_RUNTIME_FILES):
        if (root / relative_path).exists():
            errors.append(f"root-level prototype/runtime file must be quarantined: {relative_path}")

    manage_py = root / "manage.py"
    if manage_py.exists():
        manage_text = _read_text(manage_py)
        if "employee_tracker.settings" not in manage_text:
            errors.append("manage.py must use employee_tracker.settings")
        if "employee_monitor" in manage_text:
            errors.append("manage.py must not point to employee_monitor")
    else:
        errors.append("missing manage.py")

    documentation_files = list((root / "documentation").glob("*.md"))
    for path in documentation_files:
        text = _read_text(path)
        if "](intern_reviews.md)" in text or "(intern_reviews.md)" in text:
            errors.append(f"{_relative(path, root)} still links to deleted intern_reviews.md")

    intern_audit = root / "documentation" / "intern_code_audit.md"
    if intern_audit.exists():
        audit_text = _read_text(intern_audit).lower()
        for term in GATED_FEATURE_TERMS:
            if term.lower() not in audit_text:
                errors.append(f"intern_code_audit.md must mention gated feature term: {term}")

    gitignore = root / ".gitignore"
    if gitignore.exists():
        ignore_lines = {
            line.strip()
            for line in _read_text(gitignore).splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        missing_patterns = sorted(REQUIRED_GITIGNORE_PATTERNS - ignore_lines)
        if missing_patterns:
            errors.append(f".gitignore is missing privacy/generated artifact ignores: {missing_patterns}")
    else:
        errors.append("missing .gitignore")

    tracked_screenshots = _git_ls_files(root, "screenshots")
    if tracked_screenshots:
        message = (
            f"{len(tracked_screenshots)} tracked screenshot artifact(s) remain; "
            "remove them only in a separate approved cleanup."
        )
        if strict_privacy_artifacts:
            errors.append(message)
        else:
            warnings.append(message)

    workflow = root / ".github" / "workflows" / "ci.yml"
    if workflow.exists():
        workflow_text = _read_text(workflow)
        for command in sorted(REQUIRED_CI_COMMANDS):
            if command not in workflow_text:
                errors.append(f"CI workflow missing architecture command: {command}")
    else:
        warnings.append("CI workflow is missing; local guardrails still run.")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check architecture documentation and guardrails.")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--strict-privacy-artifacts",
        action="store_true",
        help="Fail if tracked privacy artifacts such as screenshots are present.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors, warnings = check_repository(root, strict_privacy_artifacts=args.strict_privacy_artifacts)

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Architecture guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
