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
import argparse
import io
import re
import sys
import unittest
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "tests" / "integration"
ROW = re.compile(r"^\|\s*(INT-\d{2})\s*\|")


def listed_scenarios(root):
    """The mandatory scenario ids in SCENARIOS.md, in file order; an empty list when the file is absent."""
    path = Path(root) / "SCENARIOS.md"
    if not path.is_file():
        return []
    seen = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def scenario_of(test):
    return getattr(type(test), "SCENARIO", None)


class Tracker(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []
        self.skipped_ids = []
        self.odd = []          # expected failures and unexpected successes

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped_ids.append(test.id())

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.odd.append(test.id())

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.odd.append(test.id())


def run_gate(root, out=sys.stdout, err=sys.stderr):
    """Run the gate for the tests in `root`. Returns (exit_code, evidence_line, problems)."""
    root = Path(root).resolve()
    problems = []
    listed = listed_scenarios(root)
    if not listed:
        problems.append("no mandatory scenario is listed in %s" % (root / "SCENARIOS.md"))
    sys.path.insert(0, str(root))
    try:
        suite = unittest.defaultTestLoader.discover(str(root), pattern="test_*.py", top_level_dir=str(root))
        tests = list(flatten(suite))
        unowned = sorted(t.id() for t in tests if scenario_of(t) not in listed)
        if unowned:
            problems.append("test(s) outside every listed scenario: %s" % ", ".join(unowned))
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=1, resultclass=Tracker)
        try:
            result = runner.run(suite)
        except SystemExit as exc:        # a test that calls sys.exit() must not end the gate with a pass
            out.write(stream.getvalue())
            problems.append("the run was ended by SystemExit(%r): incomplete run" % (exc.code,))
            evidence = "INTEGRATION-EVIDENCE: scenarios=0 of %d tests=0 ran=none" % len(listed)
            out.write(evidence + "\n")
            for p in problems:
                err.write("INTEGRATION-GATE FAIL: %s\n" % p)
            return 1, evidence, problems
    finally:
        sys.path.remove(str(root))
    out.write(stream.getvalue())
    if result.testsRun == 0:
        problems.append("zero tests ran")
    if result.testsRun != len(tests) or result.shouldStop:
        problems.append("incomplete run: %d of %d tests ran" % (result.testsRun, len(tests)))
    if result.failures or result.errors:
        problems.append("%d failure(s) and %d error(s)" % (len(result.failures), len(result.errors)))
    if result.skipped_ids:
        problems.append("skipped test(s): %s" % ", ".join(sorted(result.skipped_ids)))
    if result.odd:
        problems.append("expected failure or unexpected success: %s" % ", ".join(sorted(result.odd)))
    passed_by = {}
    for t in result.passed:
        passed_by[scenario_of(t)] = passed_by.get(scenario_of(t), 0) + 1
    total_by = {}
    for t in tests:
        total_by[scenario_of(t)] = total_by.get(scenario_of(t), 0) + 1
    ran = [s for s in listed if passed_by.get(s, 0) and passed_by[s] == total_by.get(s, 0)]
    missing = [s for s in listed if s not in ran]
    if missing:
        problems.append("mandatory scenario(s) missing, skipped or failing: %s" % ", ".join(missing))
    evidence = "INTEGRATION-EVIDENCE: scenarios=%d of %d tests=%d ran=%s" % (
        len(ran), len(listed), result.testsRun, ",".join(ran) if ran else "none")
    out.write(evidence + "\n")
    if problems:
        for p in problems:
            err.write("INTEGRATION-GATE FAIL: %s\n" % p)
        return 1, evidence, problems
    out.write("INTEGRATION-GATE PASS\n")
    return 0, evidence, problems


def main(argv=None):
    parser = argparse.ArgumentParser(prog="integration_gate.py", add_help=True)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="directory of the integration tests")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if not Path(args.root).is_dir():
        print("integration_gate: %s is not a directory" % args.root, file=sys.stderr)
        return 2
    code, _, _ = run_gate(args.root)
    return code


if __name__ == "__main__":
    sys.exit(main())
