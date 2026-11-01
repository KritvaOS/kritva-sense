"""KOS-SENSE-008 AC-803: dynamic MODULE:ATTR consumer loading. Controlled temporary modules written by the test are
loaded in separate interpreters; no untrusted code is run. Loading is NOT a sandbox: a consumer module runs with the
privileges of the user who runs the harness. Nothing here makes it one."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import ROOT, TempDir, env, run_module  # noqa: E402

GOOD = "from kritva_sense.conformance import ReferenceConsumer\nconsumer = ReferenceConsumer()\n"
METHODS = ("decide_sample", "decide_stream", "decide_frame")


def module(d, name, source):
    (d / (name + ".py")).write_text(source, encoding="utf-8")


def conformance(d, spec, *more, timeout=60):
    return run_module("conformance", "--consumer", spec, *more, cwd=d, timeout=timeout)


class Loading(unittest.TestCase):
    def test_valid_consumer_object_class_and_factory(self):
        with TempDir() as d:
            module(d, "good", GOOD + "class K(ReferenceConsumer):\n    pass\ndef factory():\n    return ReferenceConsumer()\n")
            for spec in ("good:consumer", "good:K", "good:factory"):
                with self.subTest(spec=spec):
                    r = conformance(d, spec)
                    self.assertEqual(r.returncode, 0, r.stderr[-300:])
                    self.assertEqual(json.loads(r.stdout)["verdict"], "CONFORMANT")

    def test_import_executes_module_code_with_the_users_privileges(self):
        """Documented behaviour: importing the consumer runs its module code, here a file write in the working
        directory. This is why loading is not a sandbox."""
        with TempDir() as d:
            module(d, "marker", "open('IMPORTED', 'w').write('x')\n" + GOOD)
            r = conformance(d, "marker:consumer")
            self.assertEqual(r.returncode, 0)
            self.assertTrue((d / "IMPORTED").exists())

    def test_a_named_factory_is_called_at_load(self):
        with TempDir() as d:
            module(d, "fac", "def make():\n    open('CALLED', 'w').write('x')\n    return None\n")
            r = conformance(d, "fac:make")
            self.assertEqual(r.returncode, 2)
            self.assertTrue((d / "CALLED").exists())

    def test_load_errors_are_exit_2_with_a_message_and_no_traceback(self):
        with TempDir() as d:
            module(d, "raises_at_import", "raise RuntimeError('boom')\n")
            module(d, "exits_at_import", "import sys\nsys.exit(0)\n")
            module(d, "exits_nonzero_at_import", "raise SystemExit(7)\n")
            module(d, "syntax", "def (:\n")
            module(d, "noattr", "x = 1\n")
            module(d, "notcallable", "consumer = 5\nstring = 'decide_sample'\nnone = None\n")
            module(d, "partial", "class P:\n    def decide_sample(self, *a, **k):\n        return None\nconsumer = P()\n")
            module(d, "factory_raises", "def make():\n    raise ValueError('no')\n")
            module(d, "factory_exits", "import sys\ndef make():\n    sys.exit(0)\n")
            specs = ["raises_at_import:consumer", "exits_at_import:consumer", "exits_nonzero_at_import:consumer",
                     "syntax:consumer", "noattr:consumer", "notcallable:consumer", "notcallable:string",
                     "notcallable:none", "partial:consumer", "factory_raises:make", "factory_exits:make",
                     "no_such_module_xyz:consumer", "good_absent:a.b.c"]
            for spec in specs:
                with self.subTest(spec=spec):
                    r = conformance(d, spec)
                    self.assertEqual(r.returncode, 2, "%s -> %s" % (spec, r.stdout[:200]))
                    self.assertNotIn("Traceback", r.stderr)
                    self.assertTrue(r.stderr.strip())
                    self.assertEqual(r.stdout, "")

    def test_f002_import_time_exit_zero_is_not_a_pass(self):
        """F-002: a consumer that calls sys.exit(0) at import must not end the run with exit 0 and no result."""
        with TempDir() as d:
            module(d, "quiet", "import sys\nsys.exit(0)\n")
            r = conformance(d, "quiet:consumer")
            self.assertEqual(r.returncode, 2)
            self.assertEqual(r.stdout, "")

    def test_invalid_specifications(self):
        with TempDir() as d:
            for spec in ("", "x", ":a", "a:", ":", "mutant:", "mutant:nope", "reference:x", "../x:y", "a b:c", "os.path:"):
                with self.subTest(spec=spec):
                    r = conformance(d, spec)
                    self.assertEqual(r.returncode, 2)
                    self.assertNotIn("Traceback", r.stderr)

    def test_module_is_searched_in_the_working_directory(self):
        """Documented behaviour: `python3 -m` puts the working directory on the module path, so a module there is
        found; run the harness from a directory you control."""
        with TempDir() as d:
            module(d, "localonly", GOOD)
            self.assertEqual(conformance(d, "localonly:consumer").returncode, 0)
            with TempDir() as other:
                self.assertEqual(conformance(other, "localonly:consumer").returncode, 2)


class Invocation(unittest.TestCase):
    def test_consumer_that_raises_when_invoked_fails_its_cases_only(self):
        with TempDir() as d:
            module(d, "bad", "class B:\n" + "".join("    def %s(self, *a, **k):\n        raise RuntimeError('SECRET-MESSAGE')\n" % m for m in METHODS) + "consumer = B()\n")
            r = conformance(d, "bad:consumer")
            self.assertEqual(r.returncode, 1)
            result = json.loads(r.stdout)
            self.assertEqual(result["verdict"], "NOT_CONFORMANT")
            self.assertNotIn("SECRET-MESSAGE", r.stdout)         # only the exception type name is recorded
            self.assertNotIn("Traceback", r.stderr)

    def test_f002_consumer_that_exits_when_invoked_fails_and_does_not_end_the_run(self):
        with TempDir() as d:
            module(d, "leaver", "import sys\nclass L:\n" + "".join("    def %s(self, *a, **k):\n        sys.exit(0)\n" % m for m in METHODS) + "consumer = L()\n")
            r = conformance(d, "leaver:consumer")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(json.loads(r.stdout)["verdict"], "NOT_CONFORMANT")

    def test_undefined_and_hostile_decisions_fail_the_case(self):
        with TempDir() as d:
            module(d, "hostile", "import sys\nclass Evil:\n    def __getattr__(self, n):\n        sys.exit(0)\n    def __eq__(self, o):\n        sys.exit(0)\n    __hash__ = None\n"
                   "class H:\n" + "".join("    def %s(self, *a, **k):\n        return Evil()\n" % m for m in METHODS) + "consumer = H()\n")
            r = conformance(d, "hostile:consumer")
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)

    def test_one_failing_consumer_does_not_hide_a_good_one(self):
        with TempDir() as d:
            module(d, "good", GOOD)
            module(d, "bad", "class B:\n" + "".join("    def %s(self, *a, **k):\n        raise RuntimeError()\n" % m for m in METHODS) + "consumer = B()\n")
            r = run_module("conformance", "--consumer", "good:consumer", "--consumer", "bad:consumer", cwd=d)
            self.assertEqual(r.returncode, 1)
            by_name = {c["name"]: c for c in json.loads(r.stdout)["consumers"]}
            self.assertEqual(by_name["good:consumer"]["failed"], 0)
            self.assertGreater(by_name["bad:consumer"]["failed"], 0)


class Hanging(unittest.TestCase):
    """The harness applies no timeout (documented). A hanging consumer blocks it until the caller's timeout ends the
    process. The tests use a subprocess timeout as the only guard and kill the child; the timeout is a test device,
    not a sandbox."""

    def run_with_timeout(self, d, spec, seconds=4):
        proc = subprocess.Popen([sys.executable, "-m", "kritva_sense.conformance", "--consumer", spec], cwd=d, env=env(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc.communicate(timeout=seconds)
            return False
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return True
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_consumer_that_hangs_when_invoked_blocks_until_the_caller_times_out(self):
        with TempDir() as d:
            module(d, "hang", "import time\nclass Hg:\n" + "".join("    def %s(self, *a, **k):\n        time.sleep(3600)\n" % m for m in METHODS) + "consumer = Hg()\n")
            self.assertTrue(self.run_with_timeout(d, "hang:consumer"), "expected the run to block (documented: no harness timeout)")

    def test_module_that_hangs_at_import_blocks_until_the_caller_times_out(self):
        with TempDir() as d:
            module(d, "hang_import", "import time\ntime.sleep(3600)\n")
            self.assertTrue(self.run_with_timeout(d, "hang_import:consumer"))

    def test_documentation_states_the_limit(self):
        doc = (ROOT / "src" / "kritva_sense" / "CONFORMANCE.md").read_text(encoding="utf-8")
        self.assertIn("not a sandbox", doc)
        self.assertIn("No timeout is applied to a consumer", doc)
        self.assertIn("does not make the consumer safe", doc)
        self.assertIn("privileges of the user", doc)


if __name__ == "__main__":
    unittest.main()
