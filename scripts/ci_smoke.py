"""Run repository smoke tests and fail if discovery finds zero tests."""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CI smoke tests.")
    parser.add_argument("--start-directory", default="tests")
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    start_directory = ROOT / args.start_directory
    suite = unittest.defaultTestLoader.discover(str(start_directory))
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if result.testsRun == 0:
        print("CI smoke failed: 0 tests were discovered.", file=sys.stderr)
        return 5
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
