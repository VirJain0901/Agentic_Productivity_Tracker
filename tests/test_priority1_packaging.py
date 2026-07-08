import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class PriorityOnePackagingTests(unittest.TestCase):
    def test_split_requirements_exist_and_are_scoped(self):
        backend = ROOT / "requirements" / "backend.txt"
        agent = ROOT / "requirements" / "agent-windows.txt"
        ml = ROOT / "requirements" / "ml.txt"
        dev = ROOT / "requirements" / "dev.txt"

        for path in (backend, agent, ml, dev):
            self.assertTrue(path.exists(), f"missing split requirements file: {path}")

        backend_text = backend.read_text(encoding="utf-8")
        self.assertIn("Django==5.2.5", backend_text)
        self.assertIn("daphne==", backend_text)
        self.assertIn("channels==4.3.1", backend_text)
        self.assertIn("djangorestframework-simplejwt==5.5.1", backend_text)
        self.assertIn("python-decouple==3.8", backend_text)

        agent_text = agent.read_text(encoding="utf-8")
        self.assertIn("aiofiles==24.1.0", agent_text)
        self.assertIn("pywin32==311", agent_text)
        self.assertIn("python-decouple==3.8", agent_text)
        self.assertIn("PyWinCtl==0.4.1", agent_text)
        self.assertIn("idle-time==0.1.0", agent_text)

        ml_text = ml.read_text(encoding="utf-8")
        self.assertIn("scikit-learn", ml_text)
        self.assertIn("joblib", ml_text)
        self.assertIn("watchdog", ml_text)
        self.assertIn("openpyxl", ml_text)

        root_text = read_text("requirements.txt")
        self.assertIn("-r requirements/backend.txt", root_text)
        self.assertIn("-r requirements/agent-windows.txt", root_text)
        self.assertIn("-r requirements/ml.txt", root_text)

    def test_prototype_adapter_import_is_safe(self):
        sys.modules.pop("model", None)
        sys.modules.pop("monitoring.dash_app", None)

        adapter = importlib.import_module("production_adapters.prototypes")

        self.assertNotIn("model", sys.modules)
        self.assertNotIn("monitoring.dash_app", sys.modules)

        status = adapter.prototype_status()
        self.assertFalse(status["model"]["production_enabled"])
        self.assertFalse(status["dash_app"]["production_enabled"])

        with self.assertRaises(RuntimeError):
            adapter.load_model_prototype()
        with self.assertRaises(RuntimeError):
            adapter.load_dash_prototype()

    def test_ci_smoke_runner_fails_on_zero_tests(self):
        smoke = ROOT / "scripts" / "ci_smoke.py"
        self.assertTrue(smoke.exists(), "missing CI smoke runner")
        smoke_text = smoke.read_text(encoding="utf-8")
        self.assertIn("testsRun", smoke_text)
        self.assertIn("== 0", smoke_text)
        self.assertIn("unittest", smoke_text)

        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow.exists(), "missing CI workflow")
        workflow_text = workflow.read_text(encoding="utf-8")
        self.assertIn("scripts/ci_smoke.py", workflow_text)
        self.assertIn("manage.py test tests --noinput", workflow_text)
        self.assertIn("makemigrations --check --dry-run", workflow_text)
        self.assertIn("manage.py check", workflow_text)
        self.assertIn("scripts/validate_contracts.py", workflow_text)
        self.assertIn("scripts/check_requirements_hygiene.py", workflow_text)

    def test_requirements_hygiene_script_passes(self):
        import subprocess

        script = ROOT / "scripts" / "check_requirements_hygiene.py"
        self.assertTrue(script.exists(), "missing requirements hygiene script")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)

    def test_protected_path_guard_flags_intern_owned_files(self):
        from scripts.check_protected_paths import is_protected_path

        self.assertTrue(is_protected_path("monitoring/views.py"))
        self.assertTrue(is_protected_path("employee_tracker/settings.py"))
        self.assertTrue(is_protected_path("agent.py"))
        self.assertTrue(is_protected_path("watchdog_service.py"))
        self.assertTrue(is_protected_path("model.py"))
        self.assertTrue(is_protected_path("manage.py"))

        self.assertFalse(is_protected_path("production_core/events.py"))
        self.assertFalse(is_protected_path("contracts/client_event.schema.json"))
        self.assertFalse(is_protected_path("tests/test_priority1_packaging.py"))

    def test_protected_path_guard_cli_accepts_safe_paths(self):
        import subprocess

        script = ROOT / "scripts" / "check_protected_paths.py"
        self.assertTrue(script.exists(), "missing protected path guard")
        result = subprocess.run(
            [sys.executable, str(script), "--paths", "production_core/events.py", "contracts/client_event.schema.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)

    def test_root_quickstart_documents_bootstrap_commands(self):
        quickstart = ROOT / "README.md"
        self.assertTrue(quickstart.exists(), "missing root quickstart")
        text = quickstart.read_text(encoding="utf-8")
        self.assertIn("requirements/backend.txt", text)
        self.assertIn("manage.py check", text)
        self.assertIn("makemigrations --check --dry-run", text)
        self.assertIn("scripts/ci_smoke.py", text)
        self.assertIn("daphne", text.lower())
