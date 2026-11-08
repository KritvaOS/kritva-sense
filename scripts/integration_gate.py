#!/usr/bin/env python3
"""The Sense integration gate (KOS-SENSE-009, AC-901 and AC-906). Standard library only.

    python3 scripts/integration_gate.py [--root DIR]      (`make test-integration` runs this)

Runs the integration tests under tests/integration and decides pass or fail. The gate passes only when all of this holds:

  * SCENARIOS.md lists at least one mandatory scenario (a table row whose first cell is `INT-nn`);
  * every test belongs to a listed scenario (its class has `SCENARIO = "INT-nn"`), and no test is outside one;
  * at least one test ran, the run was complete, and no test failed, errored, was skipped, was expected to fail or
    unexpectedly passed;
  * every listed scenario ran at least one test and all of its tests passed.

It prints one evidence line naming the scenarios that ran. A missing or skipped mandatory scenario, zero tests, an
incomplete run and any failure give exit 1; a usage error gives exit 2. The gate never exits 3 (NOT_IMPLEMENTED) and
never reports a pass for work that did not run.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_common as C  # noqa: E402  (the engine shared with scripts/regression_gate.py, KOS-SENSE-010)

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "integration"
ROW = re.compile(r"^\|\s*(INT-\d{2})\s*\|")
SPEC = C.Spec("INTEGRATION", ROW, "SCENARIO", "SCENARIOS.md", "scenario", "scenarios", DEFAULT_ROOT,
              "directory of the integration tests")

flatten = C.flatten
Tracker = C.Tracker


def listed_scenarios(root):
    """The mandatory scenario ids in SCENARIOS.md, in file order; an empty list when the file is absent."""
    return C.listed_ids(SPEC, root)


def scenario_of(test):
    return C.owner_of(SPEC, test)


def run_gate(root, out=sys.stdout, err=sys.stderr):
    """Run the gate for the tests in `root`. Returns (exit_code, evidence_line, problems)."""
    return C.run_gate(SPEC, root, out, err)


def main(argv=None):
    return C.main(SPEC, "integration_gate.py", argv)


if __name__ == "__main__":
    sys.exit(main())
