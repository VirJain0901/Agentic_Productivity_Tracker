import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_architecture_guardrails import check_repository


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureGuardrailTests(unittest.TestCase):
    def test_architecture_guardrail_script_passes_for_current_repo(self):
        script = ROOT / "scripts" / "check_architecture_guardrails.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("Architecture guardrails passed.", result.stdout)

    def test_architecture_guardrails_detect_stale_intern_review_doc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "documentation").mkdir()
            (root / "contracts").mkdir()
            (root / ".github" / "workflows").mkdir(parents=True)

            for relative_path in (
                "documentation/current_status.md",
                "documentation/project_review.md",
                "documentation/intern_next_actions.md",
                "documentation/architecture_review.md",
            ):
                (root / relative_path).write_text("ok\n", encoding="utf-8")
            (root / "manage.py").write_text(
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_tracker.settings')\n",
                encoding="utf-8",
            )
            (root / "documentation" / "intern_code_audit.md").write_text(
                "screenshot\nfile monitoring\nremote commands\nML risk\nlegal gate\n",
                encoding="utf-8",
            )
            (root / "documentation" / "intern_reviews.md").write_text("old\n", encoding="utf-8")

            for relative_path in (
                "contracts/client_event.schema.json",
                "contracts/sync_ack.schema.json",
                "contracts/health.schema.json",
                "contracts/audit_log.schema.json",
                "contracts/command.schema.json",
            ):
                (root / relative_path).write_text("{}", encoding="utf-8")

            (root / ".gitignore").write_text(
                "screenshots/\nmedia/\nmedia/screenshots/*.png\n",
                encoding="utf-8",
            )
            (root / ".github" / "workflows" / "ci.yml").write_text(
                "\n".join(
                    [
                        "scripts/check_protected_paths.py",
                        "scripts/check_architecture_guardrails.py",
                        "scripts/check_requirements_hygiene.py",
                        "scripts/validate_contracts.py",
                        "manage.py check",
                        "makemigrations --check --dry-run",
                    ]
                ),
                encoding="utf-8",
            )

            errors, warnings = check_repository(root)

        self.assertIn(
            "stale architecture document must stay removed: documentation/intern_reviews.md",
            errors,
        )
        self.assertEqual([], warnings)

    def test_architecture_guardrails_reject_root_uploaded_django_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "documentation").mkdir()
            (root / "contracts").mkdir()
            (root / ".github" / "workflows").mkdir(parents=True)

            for relative_path in (
                "documentation/current_status.md",
                "documentation/project_review.md",
                "documentation/intern_next_actions.md",
                "documentation/architecture_review.md",
            ):
                (root / relative_path).write_text("ok\n", encoding="utf-8")
            (root / "documentation" / "intern_code_audit.md").write_text(
                "screenshot\nfile monitoring\nremote commands\nML risk\nlegal gate\n",
                encoding="utf-8",
            )
            for relative_path in (
                "contracts/client_event.schema.json",
                "contracts/sync_ack.schema.json",
                "contracts/health.schema.json",
                "contracts/audit_log.schema.json",
                "contracts/command.schema.json",
            ):
                (root / relative_path).write_text("{}", encoding="utf-8")
            (root / ".gitignore").write_text(
                "screenshots/\nmedia/\nmedia/screenshots/*.png\n",
                encoding="utf-8",
            )
            (root / ".github" / "workflows" / "ci.yml").write_text(
                "\n".join(
                    [
                        "scripts/check_protected_paths.py",
                        "scripts/check_architecture_guardrails.py",
                        "scripts/check_requirements_hygiene.py",
                        "scripts/validate_contracts.py",
                        "manage.py check",
                        "makemigrations --check --dry-run",
                    ]
                ),
                encoding="utf-8",
            )
            (root / "manage.py").write_text(
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'employee_monitor')\n",
                encoding="utf-8",
            )
            (root / "employee_monitor.py").write_text("SECRET_KEY = 'bad'\n", encoding="utf-8")

            errors, warnings = check_repository(root)

        self.assertIn("root-level prototype/runtime file must be quarantined: employee_monitor.py", errors)
        self.assertIn("manage.py must use employee_tracker.settings", errors)
        self.assertIn("manage.py must not point to employee_monitor", errors)
        self.assertEqual([], warnings)

    def test_strict_privacy_mode_flags_tracked_screenshots(self):
        errors, warnings = check_repository(ROOT, strict_privacy_artifacts=True)

        self.assertTrue(
            any("tracked screenshot artifact" in error for error in errors),
            "strict privacy mode should flag currently tracked screenshot artifacts",
        )
        self.assertEqual([], warnings)
