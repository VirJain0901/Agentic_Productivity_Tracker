"""Guardrail for intern-owned/runtime paths.

Use this in reviews before merging platform work:

    python scripts/check_protected_paths.py --paths production_core/events.py

The script deliberately does not auto-approve exceptions. If a protected file
must change, that belongs in a separate human-reviewed diff.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath


PROTECTED_PREFIXES = (
    "monitoring/",
    "employee_tracker/",
)

PROTECTED_FILES = {
    "agent.py",
    "watchdog_service.py",
    "model.py",
    "manage.py",
    "documentation/intern_functionality_brief.docx",
    "documentation/updated_intern_module_brief_typescript_web3.docx",
}


def normalize_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")


def is_protected_path(path: str) -> bool:
    normalized = normalize_path(path)
    return normalized in PROTECTED_FILES or any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _git_changed_paths(base_ref: str | None = None, head_ref: str | None = None) -> list[str]:
    if base_ref and head_ref:
        command = ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            command = ["git", "diff", "--name-only", base_ref, head_ref]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Unable to read git changed paths")
        return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())

    commands = [
        ["git", "diff", "--name-only", "--cached"],
        ["git", "diff", "--name-only"],
    ]
    changed: set[str] = set()
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            continue
        changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(changed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail if protected intern/runtime paths are changed.")
    parser.add_argument("--paths", nargs="*", help="Explicit paths to check. Defaults to git changed paths.")
    parser.add_argument("--base-ref", help="Base git ref for CI diff checks.")
    parser.add_argument("--head-ref", help="Head git ref for CI diff checks.")
    args = parser.parse_args()

    try:
        paths = args.paths if args.paths is not None else _git_changed_paths(args.base_ref, args.head_ref)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    protected = [path for path in paths if is_protected_path(path)]

    if protected:
        print("Protected intern/runtime paths require a separate human-reviewed diff:", file=sys.stderr)
        for path in protected:
            print(f"  - {normalize_path(path)}", file=sys.stderr)
        return 2

    print(f"Protected path check passed for {len(paths)} path(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
