"""KOS-SENSE-010 AC-1001, AC-1005 and AC-1006: the regression gate and the shared gate engine cannot pass when a
mandatory case did not run, and the inventory, the tests and the golden data agree.

These tests run in `make test-unit`; they are not regression cases. Negative cases work on temporary directories, so
the real suite and the real golden data are never changed.
"""
import ast
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGRESSION = ROOT / "tests" / "regression"
INTEGRATION = ROOT / "tests" / "integration"
sys.path.insert(0, str(ROOT / "scripts"))
import gate_common as C  # noqa: E402
import integration_gate as IG  # noqa: E402
import regression_gate as RG  # noqa: E402

GATES = {"integration": (IG, "integration_gate.py", "SCENARIO", "INT", "SCENARIOS.md", "scenario"),
         "regression": (RG, "regression_gate.py", "REGRESSION", "REG", "REGRESSION_INVENTORY.md", "case")}
ROWS = re.compile(r"^\|\s*(REG-\d{2})\s*\|(.*)$")


def run(script, root=None):
    cmd = [sys.executable, str(ROOT / "scripts" / script)] + (["--root", str(root)] if root else [])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def inventory_rows():
    rows = []
    for line in (REGRESSION / "REGRESSION_INVENTORY.md").read_text(encoding="utf-8").splitlines():
        m = ROWS.match(line)
        if m:
            rows.append((m.group(1), [c.strip() for c in m.group(2).split("|")]))
    return rows


def class_owners():
    """{REG id: [test module.class]} for every test class under tests/regression."""
    owners = {}
    for path in sorted(REGRESSION.glob("test_*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and any(getattr(t, "id", None) == "REGRESSION" for t in stmt.targets):
                        owners.setdefault(ast.literal_eval(stmt.value), []).append("%s.%s" % (path.stem, node.name))
    return owners


class Inventory(unittest.TestCase):
    """AC-1001."""

    def test_every_inventory_entry_has_a_test_and_every_regression_test_has_an_entry(self):
        listed = RG.listed_cases(REGRESSION)
        self.assertGreaterEqual(len(listed), 16)
        self.assertEqual(listed, [r[0] for r in inventory_rows()])
        self.assertEqual(sorted(listed), sorted(set(listed)), "a case is listed twice")
        owners = class_owners()
        self.assertEqual(sorted(owners), sorted(listed))
        import unittest as _u
        suite = _u.defaultTestLoader.discover(str(REGRESSION), pattern="test_*.py", top_level_dir=str(REGRESSION))
        sys.path.insert(0, str(REGRESSION))
        try:
            tests = list(C.flatten(suite))
        finally:
            sys.path.remove(str(REGRESSION))
        self.assertGreater(len(tests), 30)
        for t in tests:
            self.assertIn(getattr(type(t), "REGRESSION", None), listed, t.id())

    def test_the_test_named_in_each_row_is_the_class_that_claims_the_case(self):
        owners = class_owners()
        for case, cells in inventory_rows():
            named = re.findall(r"`(test_\w+\.\w+)`", cells[2])
            with self.subTest(case=case):
                self.assertEqual(len(named), 1, cells[2])
                self.assertIn(named[0], owners[case])

    def test_every_source_test_and_file_named_in_the_inventory_exists(self):
        text = (REGRESSION / "REGRESSION_INVENTORY.md").read_text(encoding="utf-8")
        for path in sorted(set(re.findall(r"`((?:tests|scripts|src|contract)/[\w./-]+)`", text))):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).exists(), path)
        for case, cells in inventory_rows():
            for name in re.findall(r"`(test_f\d{3}_\w+)`", cells[3]):
                with self.subTest(case=case, test=name):
                    self.assertTrue(any(("def %s(" % name) in p.read_text(encoding="utf-8")
                                        for p in (ROOT / "tests" / "security").glob("test_*.py")), name)
            for sid in re.findall(r"INT-\d{2}", cells[3]):
                with self.subTest(case=case, scenario=sid):
                    self.assertIn(sid, IG.listed_scenarios(INTEGRATION))
            for d in re.findall(r"`tests/(\w+)`", cells[3]):
                self.assertTrue((ROOT / "tests" / d).is_dir(), d)
        review = (ROOT / "tasks" / "KOS-SENSE-008" / "SECURITY_REVIEW.md").read_text(encoding="utf-8")
        for f in ("F-001", "F-002", "F-003"):
            self.assertRegex(review, r"\| %s \|.*\| FIXED \|" % f)

    def test_every_golden_file_is_listed_and_the_regeneration_script_is_not_run_by_a_test(self):
        sys.path.insert(0, str(REGRESSION))
        try:
            import regression_support as R
        finally:
            sys.path.remove(str(REGRESSION))
        self.assertEqual(sorted(p.name for p in (REGRESSION / "golden").glob("*.json")), sorted(R.GOLDEN_FILES))
        for path in list(REGRESSION.glob("*.py")) + list((ROOT / "tests" / "regression_gate").glob("*.py")):
            if path.name != Path(__file__).name:
                self.assertIsNone(re.search(r"(?m)^\s*(import|from)\s+regenerate_regression_golden|\"[^\"]*regenerate_regression_golden\.py\"",
                                            path.read_text(encoding="utf-8")), path.name)


class SharedGateBehaviour(unittest.TestCase):
    """AC-1006 for the regression gate and, unchanged, AC-906 for the integration gate: both are the same engine."""

    CASE = '''import unittest


class T(unittest.TestCase):
%s
    def test_t(self):
%s
'''

    def make(self, key, listed=("01",), tests=None):
        mod, script, attr, prefix, listing, noun = GATES[key]
        tmp = tempfile.TemporaryDirectory(prefix="kritva-gate-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        if listed is not None:
            rows = "".join("| %s-%s | s | b | t | c |\n" % (prefix, n) for n in listed)
            (root / listing).write_text("# listing\n\n| ID | a | b | c | d |\n|---|---|---|---|---|\n" + rows, encoding="utf-8")
        for name, (owner, body, deco) in (tests or {}).items():
            attr_line = '    %s = "%s-%s"\n' % (attr, prefix, owner) if owner else ""
            (root / name).write_text(self.CASE % (attr_line + deco, body), encoding="utf-8")
        return root

    def each(self):
        for key in GATES:
            with self.subTest(gate=key):
                yield key, GATES[key]

    def test_a_complete_run_passes_and_prints_evidence(self):
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            root = self.make(key, tests={"test_a.py": ("01", "        pass", "")})
            r = run(script, root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertRegex(r.stdout, r"%s-EVIDENCE: %ss=1 of 1 tests=1 ran=%s-01" % (key.upper(), noun, prefix))
            self.assertIn("%s-GATE PASS" % key.upper(), r.stdout)

    def test_a_missing_case_fails_the_gate(self):
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            root = self.make(key, listed=("01", "02"), tests={"test_a.py": ("01", "        pass", "")})
            r = run(script, root)
            self.assertEqual(r.returncode, 1)
            self.assertIn("%s-02" % prefix, r.stderr)
            self.assertIn("missing, skipped or failing", r.stderr)
            self.assertIn("ran=%s-01" % prefix, r.stdout)

    def test_zero_tests_no_listing_and_a_listing_without_rows_fail(self):
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            for listed in (("01",), None, ()):
                root = self.make(key, listed=listed, tests={})
                r = run(script, root)
                self.assertEqual(r.returncode, 1, (key, listed))
                self.assertNotEqual(r.returncode, 3)
                self.assertNotIn("GATE PASS", r.stdout)
            self.assertIn("zero tests ran", run(script, self.make(key, tests={})).stderr)

    def test_a_failing_skipped_expected_failure_and_untagged_test_fail(self):
        cases = {"failing": ("01", "        self.fail('x')", ""), "skipped": ("01", "        pass", "    @unittest.skip('s')\n"),
                 "expected_failure": ("01", "        self.fail('x')", "    @unittest.expectedFailure\n"),
                 "untagged": (None, "        pass", "")}
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            for name, spec in cases.items():
                tests = {"test_a.py": ("01", "        pass", ""), "test_b.py": spec}
                if name == "untagged":
                    tests = {"test_a.py": ("01", "        pass", ""), "test_b.py": spec}
                with self.subTest(case=name):
                    r = run(script, self.make(key, tests=tests))
                    self.assertEqual(r.returncode, 1, (name, r.stdout, r.stderr))
                    self.assertIn("%s-GATE FAIL" % key.upper(), r.stderr)
                    self.assertNotIn("GATE PASS", r.stdout)

    def test_a_test_that_calls_sys_exit_does_not_end_the_gate_with_a_pass(self):
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            r = run(script, self.make(key, tests={"test_a.py": ("01", "        import sys\n        sys.exit(0)", "")}))
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("GATE PASS", r.stdout)

    def test_usage_errors_are_exit_2_and_never_exit_3(self):
        for key, (mod, script, attr, prefix, listing, noun) in self.each():
            for args in (["--bogus"], ["--root", "/nonexistent-kritva-directory"]):
                r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)] + args, capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, (key, args))
            self.assertEqual(subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--help"],
                                            capture_output=True, text=True).returncode, 0)

    def test_the_engine_gives_the_same_rows_to_both_wrappers(self):
        self.assertIs(IG.flatten, C.flatten)
        self.assertIs(IG.Tracker, C.Tracker)
        self.assertEqual(IG.SPEC.name, "INTEGRATION")
        self.assertEqual(RG.SPEC.name, "REGRESSION")
        self.assertEqual(IG.listed_scenarios(INTEGRATION)[:2], ["INT-01", "INT-02"])
        self.assertEqual(RG.listed_cases(REGRESSION)[:2], ["REG-01", "REG-02"])


class Copy:
    """A writable copy of the parts of the tree the regression suite reads, to mutate without touching the real one."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kritva-regcopy-")
        self.root = Path(self.tmp.name)
        ignore = shutil.ignore_patterns("__pycache__", "security", "packaging_build")
        for name in ("src", "contract", "scripts"):
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "tests", self.root / "tests", ignore=ignore)
        shutil.copytree(ROOT / "tasks" / "KOS-SENSE-008", self.root / "tasks" / "KOS-SENSE-008")
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def gate(self):
        return subprocess.run([sys.executable, str(self.root / "scripts" / "regression_gate.py")], capture_output=True,
                              text=True, timeout=600)


class RealSuite(unittest.TestCase):
    """AC-1003, AC-1004, AC-1006: the real suite passes, and a change to what it protects makes it fail."""

    def test_the_real_gate_passes_with_every_case(self):
        r = run("regression_gate.py")
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        listed = RG.listed_cases(REGRESSION)
        self.assertIn("REGRESSION-EVIDENCE: cases=%d of %d" % (len(listed), len(listed)), r.stdout)
        self.assertIn("ran=" + ",".join(listed), r.stdout)
        self.assertIn("REGRESSION-GATE PASS", r.stdout)

    def test_removing_a_case_makes_the_gate_fail(self):
        with Copy() as c:
            (c.root / "tests" / "regression" / "test_prior_defects.py").unlink()
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            for case in ("REG-14", "REG-15", "REG-16"):
                self.assertIn(case, r.stderr)

    def test_removing_an_inventory_row_makes_the_gate_fail_because_its_tests_are_outside_every_case(self):
        with Copy() as c:
            path = c.root / "tests" / "regression" / "REGRESSION_INVENTORY.md"
            path.write_text("\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                                      if not l.startswith("| REG-16 ")) + "\n", encoding="utf-8")
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            self.assertIn("outside every listed case", r.stderr)

    def test_changing_a_protected_contract_file_fails_the_suite(self):
        with Copy() as c:
            path = c.root / "contract" / "SENSE_CONTRACT.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nAn added sentence.\n", encoding="utf-8")
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            self.assertIn("SENSE_CONTRACT.md", r.stdout + r.stderr)
            self.assertIn("REG-01", r.stderr)

    def test_changing_the_pin_table_without_the_golden_copy_fails_the_suite(self):
        with Copy() as c:
            path = c.root / "tests" / "packaging" / "test_packaging.py"
            text = path.read_text(encoding="utf-8")
            old = '"contract/SENSE_CONTRACT.md": "f8935f'
            self.assertIn(old, text)
            path.write_text(text.replace(old, '"contract/SENSE_CONTRACT.md": "00000f', 1), encoding="utf-8")
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            self.assertIn("REG-01", r.stderr)

    def test_a_changed_exit_code_fails_the_command_line_case(self):
        with Copy() as c:
            path = c.root / "src" / "kritva_sense" / "__main__.py"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("return 1 if violations else 0", "return 0"), encoding="utf-8")
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            self.assertIn("REG-06", r.stderr)

    def test_the_f001_fix_removed_fails_the_deep_nesting_case(self):
        with Copy() as c:
            path = c.root / "src" / "kritva_sense" / "__main__.py"
            text = path.read_text(encoding="utf-8")
            self.assertIn("(OSError, ValueError, RecursionError)", text)
            path.write_text(text.replace("(OSError, ValueError, RecursionError)", "(OSError, ValueError)"), encoding="utf-8")
            r = c.gate()
            self.assertEqual(r.returncode, 1)
            self.assertIn("REG-14", r.stderr)


class Golden(unittest.TestCase):
    """AC-1005: the golden data change only by the documented explicit step, which never runs by itself."""

    def test_the_regeneration_script_shows_no_difference_and_writes_nothing(self):
        before = {p: p.read_bytes() for p in (REGRESSION / "golden").glob("*.json")}
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "regenerate_regression_golden.py")],
                           capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("differs", r.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in (REGRESSION / "golden").glob("*.json")})

    def test_the_regeneration_script_reports_a_difference_with_exit_1_and_does_not_write_without_the_option(self):
        with Copy() as c:
            path = c.root / "tests" / "regression" / "golden" / "conformance.json"
            path.write_text(path.read_text(encoding="utf-8").replace('"CONFORMANT"', '"X"', 1), encoding="utf-8")
            before = path.read_bytes()
            r = subprocess.run([sys.executable, str(c.root / "scripts" / "regenerate_regression_golden.py")],
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 1)
            self.assertIn("differs:   conformance.json", r.stdout)
            self.assertEqual(path.read_bytes(), before)
            r = subprocess.run([sys.executable, str(c.root / "scripts" / "regenerate_regression_golden.py"), "--write"],
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(r.returncode, 0)
            self.assertIn("written:   conformance.json", r.stdout)
            self.assertNotEqual(path.read_bytes(), before)

    def test_a_usage_error_is_exit_2(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "regenerate_regression_golden.py"), "--bogus"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
