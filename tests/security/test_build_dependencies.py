"""KOS-SENSE-008 AC-805: build and dependency configuration. Static inspection only; the contents of the release
artifacts are verified by tests/packaging (AC-703: exact file listing of the wheel and the source distribution), which
the offline test in this directory also runs."""
import re
import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import ROOT  # noqa: E402


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class Dependencies(unittest.TestCase):
    def test_runtime_dependencies_are_empty(self):
        doc = pyproject()
        self.assertEqual(doc["project"]["dependencies"], [])
        self.assertNotIn("optional-dependencies", doc["project"])
        self.assertNotIn("dynamic", doc["project"])

    def test_runtime_code_imports_only_the_standard_library_and_itself(self):
        stdlib = sys.stdlib_module_names
        for path in sorted((ROOT / "src" / "kritva_sense").glob("*.py")):
            for line in path.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", line)
                if not m:
                    continue
                top = (m.group(1) or m.group(2)).split(".")[0].rstrip(",")
                if top == "":
                    continue                                   # relative import
                self.assertIn(top, stdlib, "%s imports %s, which is not in the standard library" % (path.name, top))

    def test_runtime_code_has_no_dynamic_execution_other_than_the_documented_consumer_import(self):
        """eval, exec, compile, pickle, marshal, shelve, ctypes, subprocess, os.system and __import__ are absent;
        the one `import_module` use is the documented consumer loader in conformance.py (version.py reads importlib.metadata)."""
        banned = re.compile(r"(?<![\w.])(eval|exec|compile|__import__)\(|\b(pickle|marshal|shelve|ctypes|subprocess|socket|urllib|http|ftplib|"
                            r"smtplib|telnetlib|xmlrpc|requests)\b|os\.(system|popen|exec\w*|spawn\w*)\b|yaml\.load")
        for path in sorted((ROOT / "src" / "kritva_sense").glob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#")[0]
                if re.match(r"^\s*(\"\"\"|')", code):
                    continue
                self.assertIsNone(banned.search(code), "%s:%d %s" % (path.name, n, line.strip()))
        users = [p.name for p in sorted((ROOT / "src" / "kritva_sense").glob("*.py"))
                 if "import_module(" in p.read_text(encoding="utf-8")]
        self.assertEqual(users, ["conformance.py"])
        meta = [p.name for p in sorted((ROOT / "src" / "kritva_sense").glob("*.py"))
                if re.search(r"importlib(\.| import )", p.read_text(encoding="utf-8")) and p.name != "conformance.py"]
        self.assertEqual(meta, ["version.py"])          # importlib.metadata only, to read the installed version

    def test_no_install_time_code(self):
        self.assertFalse((ROOT / "setup.py").exists())
        self.assertFalse((ROOT / "setup.cfg").exists())
        self.assertEqual(pyproject()["build-system"]["build-backend"], "setuptools.build_meta")

    def test_console_scripts_point_at_package_entry_points(self):
        for name, target in pyproject()["project"]["scripts"].items():
            self.assertRegex(target, r"^kritva_sense(\._entry|\.version)?:\w+$", name)


class BuildConfiguration(unittest.TestCase):
    def requirement_lines(self):
        return [l for l in (ROOT / "release" / "build-requirements.txt").read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]

    def test_build_requirements_are_exact_and_hash_pinned(self):
        lines = self.requirement_lines()
        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, r"^[A-Za-z0-9_.-]+==[0-9][0-9A-Za-z.+-]* --hash=sha256:[0-9a-f]{64}$", line)
            self.assertNotRegex(line, r"(git\+|https?://|file:|\.\./|--index-url|--extra-index-url|--find-links|-e )")

    def test_build_system_requirement_is_pinned_and_matches(self):
        requires = pyproject()["build-system"]["requires"]
        self.assertEqual(len(requires), 1)
        pins = {l.split("==")[0].lower().replace("_", "-"): l.split("==")[1].split()[0] for l in self.requirement_lines()}
        name, version = requires[0].split("==")
        self.assertEqual(pins[name], version)

    def test_manifest_has_no_wildcard_grafts(self):
        text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.strip() and not line.startswith("#"):
                self.assertRegex(line, r"^(include|exclude) [\w./-]+$", line)

    def test_release_artifact_listing_is_verified_by_the_packaging_suite(self):
        src = (ROOT / "tests" / "packaging" / "test_packaging.py").read_text(encoding="utf-8")
        self.assertIn("test_ac703_distributions_contain_only_the_intended_files", src)
        self.assertIn("expected_wheel_names()", src)
        self.assertIn("expected_sdist_names()", src)

    def test_unit_gate_runs_every_test_directory(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        gate = makefile[makefile.index("test-unit:"):makefile.index("test-integration:")]
        listed = set(re.findall(r"discover -s tests/(\w+)", gate))
        present = {p.name for p in (ROOT / "tests").iterdir() if p.is_dir() and any(p.glob("test_*.py"))}
        # `integration` is run by `make test-integration` (scripts/integration_gate.py, KOS-SENSE-009). `integration_gate`
        # tests that gate; it moves into the unit gate when the Makefile change of KOS-SENSE-009 is merged.
        self.assertLessEqual(present - listed, {"commit_message_check", "readme_check", "integration", "integration_gate"},
                             "a test directory is not run by make test-unit or make check")
        self.assertIn("security", listed)


if __name__ == "__main__":
    unittest.main()
