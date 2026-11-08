"""Shared engine of the Sense gate runners (KOS-SENSE-010). Standard library only.

`scripts/integration_gate.py` (KOS-SENSE-009) and `scripts/regression_gate.py` (KOS-SENSE-010) are thin wrappers around
this module. A gate is described by a `Spec`: the directory of its tests, the table that lists its mandatory items
(`INT-nn` scenarios, `REG-nn` regression cases), and the class attribute with which a test names the item it belongs to.

A gate passes only when all of this holds:

  * the listing file names at least one mandatory item (a table row whose first cell is the item id);
  * every test belongs to a listed item, and no test is outside one;
  * at least one test ran, the run was complete, and no test failed, errored, was skipped, was expected to fail or
    unexpectedly passed;
  * every listed item ran at least one test and all of its tests passed.

Exit codes of a runner: 0 pass, 1 fail (a missing, skipped or failing item, zero tests, an incomplete run), 2 usage
error. A gate never exits 3 (NOT_IMPLEMENTED) and never reports a pass for work that did not run. Each run prints one
evidence line naming the items that ran.
"""
import argparse
import io
import re
import sys
import unittest
from pathlib import Path


class Spec:
    """What distinguishes one gate from another. `row` is a compiled regex whose first group is the item id."""

    def __init__(self, name, row, attr, listing, noun, plural, default_root, description):
        self.name = name                      # "INTEGRATION" or "REGRESSION": prefix of every printed line
        self.row = row
        self.attr = attr                      # class attribute that names the item of a test
        self.listing = listing                # file name of the table, inside the test directory
        self.noun = noun                      # "scenario" or "case"
        self.plural = plural
        self.default_root = Path(default_root)
        self.description = description


def listed_ids(spec, root):
    """The mandatory item ids in the listing file, in file order; an empty list when the file is absent."""
    path = Path(root) / spec.listing
    if not path.is_file():
        return []
    seen = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = spec.row.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def owner_of(spec, test):
    return getattr(type(test), spec.attr, None)


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


def run_gate(spec, root, out=sys.stdout, err=sys.stderr):
    """Run the gate for the tests in `root`. Returns (exit_code, evidence_line, problems)."""
    root = Path(root).resolve()
    problems = []
    listed = listed_ids(spec, root)
    if not listed:
        problems.append("no mandatory %s is listed in %s" % (spec.noun, root / spec.listing))
    sys.path.insert(0, str(root))
    try:
        suite = unittest.defaultTestLoader.discover(str(root), pattern="test_*.py", top_level_dir=str(root))
        tests = list(flatten(suite))
        unowned = sorted(t.id() for t in tests if owner_of(spec, t) not in listed)
        if unowned:
            problems.append("test(s) outside every listed %s: %s" % (spec.noun, ", ".join(unowned)))
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=1, resultclass=Tracker)
        try:
            result = runner.run(suite)
        except SystemExit as exc:        # a test that calls sys.exit() must not end the gate with a pass
            out.write(stream.getvalue())
            problems.append("the run was ended by SystemExit(%r): incomplete run" % (exc.code,))
            evidence = "%s-EVIDENCE: %s=0 of %d tests=0 ran=none" % (spec.name, spec.plural, len(listed))
            out.write(evidence + "\n")
            for p in problems:
                err.write("%s-GATE FAIL: %s\n" % (spec.name, p))
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
        passed_by[owner_of(spec, t)] = passed_by.get(owner_of(spec, t), 0) + 1
    total_by = {}
    for t in tests:
        total_by[owner_of(spec, t)] = total_by.get(owner_of(spec, t), 0) + 1
    ran = [s for s in listed if passed_by.get(s, 0) and passed_by[s] == total_by.get(s, 0)]
    missing = [s for s in listed if s not in ran]
    if missing:
        problems.append("mandatory %s(s) missing, skipped or failing: %s" % (spec.noun, ", ".join(missing)))
    evidence = "%s-EVIDENCE: %s=%d of %d tests=%d ran=%s" % (
        spec.name, spec.plural, len(ran), len(listed), result.testsRun, ",".join(ran) if ran else "none")
    out.write(evidence + "\n")
    if problems:
        for p in problems:
            err.write("%s-GATE FAIL: %s\n" % (spec.name, p))
        return 1, evidence, problems
    out.write("%s-GATE PASS\n" % spec.name)
    return 0, evidence, problems


def main(spec, prog, argv=None):
    parser = argparse.ArgumentParser(prog=prog, add_help=True)
    parser.add_argument("--root", default=str(spec.default_root), help=spec.description)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if not Path(args.root).is_dir():
        print("%s: %s is not a directory" % (prog.replace(".py", ""), args.root), file=sys.stderr)
        return 2
    code, _, _ = run_gate(spec, args.root)
    return code
