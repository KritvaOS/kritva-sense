"""KOS-SENSE-010 AC-1007: `make test` runs the three gates once each, shows the three results separately, and cannot
pass when any one fails, is missing or is incomplete. The tests use stand-in gate commands, never the real suites, and
check the make targets and the CI workflow as text."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "test_all.py"
sys.path.insert(0, str(ROOT / "scripts"))
import test_all as T  # noqa: E402

PASS_UNIT = "echo 'Ran 5 tests in 0.1s'; echo; echo OK"
PASS_INT = "echo INTEGRATION-GATE PASS"
PASS_REG = "echo REGRESSION-GATE PASS"


def run(unit=PASS_UNIT, integration=PASS_INT, regression=PASS_REG, extra=()):
    cmd = [sys.executable, str(SCRIPT), "--gate", "unit=" + unit, "--gate", "integration=" + integration,
           "--gate", "regression=" + regression, *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def summary(r):
    m = re.search(r"(?m)^TEST-SUMMARY unit=(\S+) integration=(\S+) regression=(\S+)$", r.stdout)
    assert m, r.stdout
    return m.groups()


class Aggregate(unittest.TestCase):
    def test_all_three_pass_and_are_shown_separately(self):
        r = run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(summary(r), ("PASS", "PASS", "PASS"))
        for name in ("unit", "integration", "regression"):
            self.assertRegex(r.stdout, r"(?m)^%s +PASS " % name)
        self.assertIn("TEST PASS", r.stdout)

    def test_each_gate_runs_exactly_once_in_order_and_after_an_earlier_failure(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log"
            mark = lambda n, rest: "echo %s >> %s; %s" % (n, log, rest)   # noqa: E731
            r = run(unit=mark("unit", "exit 1"), integration=mark("integration", PASS_INT),
                    regression=mark("regression", PASS_REG))
            self.assertEqual(log.read_text().split(), ["unit", "integration", "regression"])
            self.assertEqual(r.returncode, 1)
            self.assertEqual(summary(r), ("FAIL", "PASS", "PASS"))

    def test_any_one_failing_fails_the_aggregate(self):
        for which, kw in (("unit", {"unit": "exit 1"}), ("integration", {"integration": "exit 1"}),
                          ("regression", {"regression": "exit 2"})):
            with self.subTest(failing=which):
                r = run(**kw)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(summary(r)[("unit", "integration", "regression").index(which)], "FAIL")
                self.assertIn("TEST FAIL", r.stdout)
                self.assertNotIn("TEST PASS", r.stdout)

    def test_a_not_implemented_gate_is_missing_never_a_pass(self):
        for which in ("unit", "integration", "regression"):
            with self.subTest(gate=which):
                r = run(**{which: "echo 'NOT_IMPLEMENTED: x has no tests yet; this is not a pass'; exit 3"})
                self.assertEqual(r.returncode, 1)
                self.assertEqual(summary(r)[("unit", "integration", "regression").index(which)], "MISSING")

    def test_a_gate_that_exits_zero_without_the_evidence_is_missing(self):
        for which, cmd in (("unit", "true"), ("unit", "echo Ran 0 tests; echo OK"), ("integration", "true"),
                           ("regression", "echo all fine")):
            with self.subTest(gate=which, command=cmd):
                r = run(**{which: cmd})
                self.assertEqual(r.returncode, 1)
                self.assertEqual(summary(r)[("unit", "integration", "regression").index(which)], "MISSING")
                self.assertIn("incomplete run", r.stdout)

    def test_a_command_that_cannot_run_is_missing(self):
        r = run(regression="kritva-no-such-command-xyz")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(summary(r)[2], "MISSING")

    def test_the_output_of_every_gate_is_shown(self):
        r = run(unit="echo 'Ran 5 tests in 0.1s'; echo UNIT-MARKER; echo OK", integration="echo INTEGRATION-GATE PASS; echo INT-MARKER")
        self.assertIn("UNIT-MARKER", r.stdout)
        self.assertIn("INT-MARKER", r.stdout)

    def test_usage_errors_are_exit_2(self):
        for extra in (["--bogus"], ["--gate", "nonsense"], ["--gate", "other=true"], ["--gate", "unit="]):
            with self.subTest(args=extra):
                r = subprocess.run([sys.executable, str(SCRIPT), *extra], capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True).returncode, 0)

    def test_the_default_gates_are_the_three_make_targets(self):
        self.assertEqual([(n, c) for n, c, _ in T.DEFAULT_GATES],
                         [("unit", "make --no-print-directory test-unit"),
                          ("integration", "make --no-print-directory test-integration"),
                          ("regression", "make --no-print-directory test-regression")])

    def test_the_default_evidence_patterns_accept_real_output_and_reject_empty_output(self):
        unit, integration, regression = (g[2] for g in T.DEFAULT_GATES)
        self.assertTrue(unit.search("Ran 27 tests in 19.5s\n\nOK (skipped=1)\n"))
        self.assertFalse(unit.search("Ran 0 tests in 0.0s\n\nOK\n"))
        self.assertFalse(unit.search(""))
        self.assertTrue(integration.search("x\nINTEGRATION-GATE PASS\n"))
        self.assertTrue(regression.search("x\nREGRESSION-GATE PASS\n"))
        self.assertFalse(regression.search("REGRESSION-GATE FAIL: x\n"))


class MakeAndCi(unittest.TestCase):
    """The make targets and the workflow, read as text (the Makefile and .github/ are protected paths)."""

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "unit-tests.yml").read_text(encoding="utf-8")

    def body(self, target):
        start = self.makefile.index("\n%s:" % target) + 1
        end = re.search(r"(?m)^[a-zA-Z0-9_.-]+:[^=]", self.makefile[start + len(target) + 1:])
        return self.makefile[start:start + len(target) + 1 + (end.start() if end else len(self.makefile))]

    def test_test_regression_is_a_real_gate(self):
        body = self.body("test-regression")
        self.assertIn("python3 scripts/regression_gate.py", body)
        self.assertNotIn("not_implemented", body)

    def test_make_test_runs_the_aggregate_and_is_not_a_placeholder(self):
        body = self.body("test")
        self.assertIn("python3 scripts/test_all.py", body)
        self.assertNotIn("not_implemented", body)

    def test_the_golden_target_never_writes_by_default(self):
        body = self.body("regression-golden")
        self.assertIn("scripts/regenerate_regression_golden.py $(if $(WRITE),--write,)", body)

    def test_only_lint_and_acceptance_remain_placeholders(self):
        self.assertEqual(re.findall(r"\$\(call not_implemented,([\w-]+)\)", self.makefile), ["lint", "acceptance"])

    def test_the_unit_gate_runs_the_gate_tests_of_both_gates(self):
        body = self.body("test-unit")
        for d in ("integration_gate", "regression_gate"):
            self.assertIn("discover -s tests/%s\n" % d, body)

    def test_ci_runs_the_three_gates_as_separate_visible_steps_and_not_make_test(self):
        steps = re.findall(r"(?m)^      - name: (.+)\n        run: (.+)$", self.workflow)
        self.assertEqual(steps, [("Structure checks", "make check docs-check"), ("Unit gate", "make test-unit"),
                                 ("Integration gate", "make test-integration"),
                                 ("Regression gate", "make test-regression")])
        self.assertNotRegex(self.workflow, r"(?m)^\s+run: make test$")
        self.assertEqual(len(re.findall(r"(?m)^  [a-z0-9-]+:$", self.workflow[self.workflow.index("jobs:"):])), 1)
        self.assertEqual(self.workflow.count("\n  unit-tests:"), 1)


if __name__ == "__main__":
    unittest.main()
