"""KOS-SENSE-009 AC-901 and AC-906: the integration gate cannot pass when a mandatory scenario did not run.

These tests run in `make test-unit`; they are not integration scenarios. Each negative case works on a copy of
tests/integration in a temporary directory, so the real suite is never changed.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "integration_gate.py"
REAL = ROOT / "tests" / "integration"
sys.path.insert(0, str(ROOT / "scripts"))
import integration_gate as G  # noqa: E402

TEST_TEMPLATE = '''import unittest


class Extra(unittest.TestCase):
%s
    def test_extra(self):
%s
'''


class Copy:
    """A writable copy of tests/integration at <tmp>/tests/integration, with <tmp>/src linked to the real source."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kritva-gate-")
        base = Path(self.tmp.name)
        (base / "tests").mkdir()
        self.root = base / "tests" / "integration"
        shutil.copytree(REAL, self.root, ignore=shutil.ignore_patterns("__pycache__"))
        (base / "src").symlink_to(ROOT / "src")
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def add_test(self, name, scenario, body="        pass", decorator=""):
        attr = '    SCENARIO = "%s"\n' % scenario if scenario else ""
        (self.root / name).write_text(TEST_TEMPLATE % (attr + decorator, body), encoding="utf-8")


def gate(root):
    return subprocess.run([sys.executable, str(GATE), "--root", str(root)], capture_output=True, text=True, timeout=300)


class ScenarioTable(unittest.TestCase):
    """AC-901."""

    def test_every_listed_scenario_has_a_test_and_every_test_belongs_to_a_listed_scenario(self):
        listed = G.listed_scenarios(REAL)
        self.assertGreaterEqual(len(listed), 10)
        suite = unittest.defaultTestLoader.discover(str(REAL), pattern="test_*.py", top_level_dir=str(REAL))
        sys.path.insert(0, str(REAL))
        try:
            tests = list(G.flatten(suite))
        finally:
            sys.path.remove(str(REAL))
        owners = {G.scenario_of(t) for t in tests}
        self.assertEqual(sorted(owners, key=str), sorted(listed))
        self.assertNotIn(None, owners)

    def test_scenario_rows_state_boundary_input_result_and_clause(self):
        rows = [l for l in (REAL / "SCENARIOS.md").read_text(encoding="utf-8").splitlines() if G.ROW.match(l)]
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            self.assertEqual(len(cells), 5, row)
            self.assertTrue(all(cells), row)

    def test_ids_are_unique_and_ordered(self):
        listed = G.listed_scenarios(REAL)
        self.assertEqual(listed, sorted(set(listed)))
        self.assertEqual(listed, ["INT-%02d" % i for i in range(1, len(listed) + 1)])

    def test_the_documents_name_the_reference_fixture(self):
        text = (REAL / "SCENARIOS.md").read_text(encoding="utf-8")
        self.assertIn("not a Mind, Motion or Skill consumer", text)


class GatePasses(unittest.TestCase):
    def test_real_suite_passes_and_prints_the_evidence_line(self):
        p = gate(REAL)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        listed = G.listed_scenarios(REAL)
        line = [l for l in p.stdout.splitlines() if l.startswith("INTEGRATION-EVIDENCE:")]
        self.assertEqual(len(line), 1)
        self.assertIn("scenarios=%d of %d" % (len(listed), len(listed)), line[0])
        for s in listed:
            self.assertIn(s, line[0])
        self.assertRegex(line[0], r"tests=\d+")
        self.assertIn("INTEGRATION-GATE PASS", p.stdout)


class GateFails(unittest.TestCase):
    def assert_fails(self, p, needle):
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(needle, p.stderr)
        self.assertNotIn("INTEGRATION-GATE PASS", p.stdout)

    def test_removing_a_scenario_makes_it_fail(self):
        with Copy() as c:
            (c.root / "test_consumer_harness.py").unlink()          # INT-06 and INT-07 have no test any more
            p = gate(c.root)
            self.assert_fails(p, "INT-06, INT-07")
            self.assertIn("missing, skipped or failing", p.stderr)
            self.assertIn("scenarios=8 of 10", p.stdout)

    def test_removing_the_row_of_a_tested_scenario_makes_it_fail(self):
        with Copy() as c:
            table = c.root / "SCENARIOS.md"
            table.write_text(re.sub(r"(?m)^\| INT-10 .*\n", "", table.read_text(encoding="utf-8")), encoding="utf-8")
            self.assert_fails(gate(c.root), "outside every listed scenario")

    def test_a_listed_scenario_without_a_test_fails(self):
        with Copy() as c:
            table = c.root / "SCENARIOS.md"
            table.write_text(table.read_text(encoding="utf-8").replace(
                "\n## Interpretation notes", "| INT-11 | a | b | c | d |\n\n## Interpretation notes"), encoding="utf-8")
            self.assert_fails(gate(c.root), "INT-11")

    def test_a_failing_test_fails(self):
        with Copy() as c:
            c.add_test("test_extra.py", "INT-01", body="        self.fail('forced')")
            self.assert_fails(gate(c.root), "1 failure(s)")

    def test_a_skipped_mandatory_test_fails(self):
        with Copy() as c:
            c.add_test("test_extra.py", "INT-01", decorator="    @unittest.skip('forced')\n")
            p = gate(c.root)
            self.assert_fails(p, "skipped test(s)")

    def test_a_scenario_whose_only_test_is_skipped_fails_as_missing(self):
        with Copy() as c:
            (c.root / "test_consumer_harness.py").unlink()
            c.add_test("test_extra.py", "INT-06", decorator="    @unittest.skip('forced')\n")
            self.assertIn("INT-06", gate(c.root).stderr)

    def test_an_expected_failure_fails(self):
        with Copy() as c:
            c.add_test("test_extra.py", "INT-01", body="        self.fail('x')", decorator="    @unittest.expectedFailure\n")
            self.assert_fails(gate(c.root), "expected failure or unexpected success")

    def test_a_test_outside_every_scenario_fails(self):
        with Copy() as c:
            c.add_test("test_extra.py", None)
            self.assert_fails(gate(c.root), "outside every listed scenario")

    def test_zero_tests_fails(self):
        with tempfile.TemporaryDirectory(prefix="kritva-gate-") as d:
            (Path(d) / "SCENARIOS.md").write_text("| INT-01 | a | b | c | d |\n", encoding="utf-8")
            p = gate(d)
            self.assert_fails(p, "zero tests ran")
            self.assertIn("scenarios=0 of 1", p.stdout)

    def test_no_scenario_list_fails(self):
        with tempfile.TemporaryDirectory(prefix="kritva-gate-") as d:
            self.assert_fails(gate(d), "no mandatory scenario is listed")

    def test_a_test_that_exits_the_process_fails(self):
        with Copy() as c:
            c.add_test("test_extra.py", "INT-01", body="        import sys\n        sys.exit(0)")
            self.assert_fails(gate(c.root), "error(s)")

    def test_an_import_error_in_a_test_module_fails(self):
        with Copy() as c:
            (c.root / "test_extra.py").write_text("import module_that_does_not_exist\n", encoding="utf-8")
            self.assertEqual(gate(c.root).returncode, 1)

    def test_a_missing_directory_is_a_usage_error_not_a_pass(self):
        p = subprocess.run([sys.executable, str(GATE), "--root", "/nonexistent-kritva-dir"], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 2)

    def test_the_gate_never_exits_3(self):
        self.assertNotIn("exit 3", GATE.read_text(encoding="utf-8").replace("never exits 3", ""))


if __name__ == "__main__":
    unittest.main()
