"""Check dependency split hygiene for the repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements"
WINDOWS_ONLY = {"pywin32"}
ROOT_INCLUDES = {
    "-r requirements/backend.txt",
    "-r requirements/agent-windows.txt",
    "-r requirements/ml.txt",
}
RUNTIME_FILES = [
    ROOT / "requirements.txt",
    REQUIREMENTS / "backend.txt",
    REQUIREMENTS / "agent-windows.txt",
    REQUIREMENTS / "ml.txt",
    REQUIREMENTS / "dev.txt",
]


def _logical_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _package_name(line: str) -> str | None:
    if line.startswith("-r "):
        return None
    name = re.split(r"\s*(?:==|>=|<=|~=|!=|>|<|;|\[)", line, maxsplit=1)[0]
    return name.strip().lower().replace("_", "-")


def _check_duplicates(path: Path) -> list[str]:
    seen: dict[str, str] = {}
    errors: list[str] = []
    for line in _logical_lines(path):
        name = _package_name(line)
        if name is None:
            continue
        if name in seen:
            errors.append(f"{path}: duplicate dependency {name!r}: {seen[name]!r} and {line!r}")
        seen[name] = line
    return errors


def _check_root_delegates() -> list[str]:
    path = ROOT / "requirements.txt"
    lines = set(_logical_lines(path))
    errors: list[str] = []
    if lines != ROOT_INCLUDES:
        errors.append(f"{path}: root requirements must only include {sorted(ROOT_INCLUDES)}")
    return errors


def _check_windows_markers() -> list[str]:
    errors: list[str] = []
    for path in RUNTIME_FILES:
        for line in _logical_lines(path):
            name = _package_name(line)
            if name in WINDOWS_ONLY and 'sys_platform == "win32"' not in line:
                errors.append(f"{path}: Windows-only dependency {name!r} must have a win32 marker")
            if path.name == "backend.txt" and name in WINDOWS_ONLY:
                errors.append(f"{path}: Windows-only dependency {name!r} must not be in backend requirements")
    return errors


def _check_required_backend_runtime() -> list[str]:
    backend_names = {_package_name(line) for line in _logical_lines(REQUIREMENTS / "backend.txt")}
    required = {"django", "daphne", "channels", "channels-redis", "djangorestframework", "python-decouple"}
    missing = sorted(required - backend_names)
    if missing:
        return [f"{REQUIREMENTS / 'backend.txt'}: missing backend runtime dependency {missing}"]
    return []


def _check_required_agent_runtime() -> list[str]:
    agent_names = {_package_name(line) for line in _logical_lines(REQUIREMENTS / "agent-windows.txt")}
    required = {"aiofiles", "aiohttp", "psutil", "python-decouple", "requests"}
    missing = sorted(required - agent_names)
    if missing:
        return [f"{REQUIREMENTS / 'agent-windows.txt'}: missing agent runtime dependency {missing}"]
    return []


def main() -> int:
    errors: list[str] = []
    for path in RUNTIME_FILES:
        if not path.exists():
            errors.append(f"{path}: missing requirements file")
            continue
        errors.extend(_check_duplicates(path))
    errors.extend(_check_root_delegates())
    errors.extend(_check_windows_markers())
    errors.extend(_check_required_backend_runtime())
    errors.extend(_check_required_agent_runtime())

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Requirements hygiene checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
