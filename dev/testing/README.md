# Development Testing

The maintained automated test suite lives in `dev/testing/tests`. The other
files under `dev/testing/testing codes` are older manual utilities and
experiments; they are not collected by the automated runner.

Run the complete suite from any working directory:

```bash
python dev/testing/run_tests.py
```

You can also use standard-library discovery from the repository root:

```bash
python -m unittest discover -s dev/testing/tests -p "test_*.py" -v
```

## Adding Testing Points

Add or extend an automated test whenever production behavior is introduced,
changed, or fixed. Keep all maintained tests in `dev/testing/tests` and name
test modules `test_<feature>.py` so both commands above discover them.

- Put focused behavior tests in the module matching the production feature.
- Add a regression test for every reproducible bug fix.
- Use temporary directories and mocks instead of writing into application data.
- Set GUI tests to use the offscreen Qt platform and clean up created widgets.
- Keep network, serial-port, database, and update-server tests deterministic by
  replacing external access with test doubles.
- Run the full suite before committing or building a release.

Tests may add the repository's `src` directory to `sys.path` using:

```python
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
```
