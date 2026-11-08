#!/usr/bin/env python3
"""The Sense regression gate (KOS-SENSE-010, AC-1001 and AC-1006). Standard library only.

    python3 scripts/regression_gate.py [--root DIR]      (`make test-regression` runs this)

Runs the regression tests under tests/regression and decides pass or fail with the rules of scripts/gate_common.py:
tests/regression/REGRESSION_INVENTORY.md lists every mandatory regression case (a table row whose first cell is
`REG-nn`), every test names its case with a `REGRESSION = "REG-nn"` class attribute, and the gate fails on a missing,
skipped or failing case, zero tests, an incomplete run, a test outside every case and any expected failure.

It prints one evidence line naming the cases that ran. Exit 0 pass, 1 fail, 2 usage error; never 3 (NOT_IMPLEMENTED).
The golden data under tests/regression/golden are never written by this gate: they change only through
`scripts/regenerate_regression_golden.py` (tests/regression/README.md).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common as C  # noqa: E402

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "regression"
ROW = re.compile(r"^\|\s*(REG-\d{2})\s*\|")
SPEC = C.Spec("REGRESSION", ROW, "REGRESSION", "REGRESSION_INVENTORY.md", "case", "cases", DEFAULT_ROOT,
              "directory of the regression tests")


def listed_cases(root):
    """The mandatory regression case ids in REGRESSION_INVENTORY.md, in file order."""
    return C.listed_ids(SPEC, root)


def run_gate(root, out=sys.stdout, err=sys.stderr):
    """Run the gate for the tests in `root`. Returns (exit_code, evidence_line, problems)."""
    return C.run_gate(SPEC, root, out, err)


def main(argv=None):
    return C.main(SPEC, "regression_gate.py", argv)


if __name__ == "__main__":
    sys.exit(main())
