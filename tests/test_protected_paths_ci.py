import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProtectedPathsCiTests(unittest.TestCase):
    def test_ci_diff_mode_accepts_empty_head_diff(self):
        script = ROOT / "scripts" / "check_protected_paths.py"
        result = subprocess.run(
            [sys.executable, str(script), "--base-ref", "HEAD", "--head-ref", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)

    def test_explicit_protected_path_still_fails(self):
        script = ROOT / "scripts" / "check_protected_paths.py"
        result = subprocess.run(
            [sys.executable, str(script), "--paths", "employee_tracker/settings.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("employee_tracker/settings.py", result.stderr)
