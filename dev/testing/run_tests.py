"""Run the maintained automated test suite from any working directory."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


TESTING_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTING_DIR.parents[1]
TEST_SUITE_DIR = TESTING_DIR / "tests"


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(REPO_ROOT / "src"))

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TEST_SUITE_DIR),
        pattern="test_*.py",
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
