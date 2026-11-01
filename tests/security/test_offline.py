"""KOS-SENSE-008 AC-805 and AC-807: the mandatory suites pass with the network disabled, and a missing mandatory build
tool fails CI.

Network is disabled in the child interpreters by a sitecustomize module (found through PYTHONPATH) that makes socket
connection and name resolution raise; the probe test proves the block works. The packaging suite clears PYTHON*
variables on purpose, so for it the package index is pointed at a dead address instead (see offline_env). On a Linux machine with `unshare -n` an operator can repeat the run with a real network
namespace (SECURITY_REVIEW.md, section Offline run).

Network-needing tests (NETWORK_TESTS) are identified, excluded from the offline suite (KRITVA_OFFLINE_SUITE=1) and
justified here: the only network use of the repository tests is the one fetch of the hash-pinned build tools, which
exists to prove the packaging suite can be prepared; the offline run of that suite uses a prepared wheelhouse."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import IN_CI, ROOT, TempDir, env, unavailable  # noqa: E402

SUITES = ["contract", "frame_graph", "generator", "stream", "conformance", "status", "security"]
# Justification: fetching the pinned build tools needs the package index. This is the single network need.
NETWORK_TESTS = {"test_packaging_suite_passes_offline_with_a_prepared_wheelhouse"}
OFFLINE_SUITE = os.environ.get("KRITVA_OFFLINE_SUITE") == "1"
BLOCK = '''import socket


def _blocked(*args, **kwargs):
    raise OSError("network disabled by the KOS-SENSE-008 offline test")


socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
socket.gethostbyname = _blocked
'''


def offline_env(blockdir, **extra):
    e = env(**extra)
    e["PYTHONPATH"] = os.pathsep.join([str(blockdir), e["PYTHONPATH"]])
    e["KRITVA_OFFLINE_SUITE"] = "1"
    e.pop("KRITVA_WHEELHOUSE", None) if "KRITVA_WHEELHOUSE" not in extra else None
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        e.pop(k, None)
    # The packaging suite removes every PYTHON* variable on purpose, so the socket block cannot reach the
    # interpreters it starts. For pip, the only network user there, the package index is replaced by a dead address
    # and the machine's pip configuration (index, proxy) is ignored: without a wheelhouse the fetch of the pinned
    # build tools fails, with one the suite needs no index at all.
    e["PIP_NO_CACHE_DIR"] = "1"
    e["PIP_INDEX_URL"] = "http://127.0.0.1:9/simple"
    e["PIP_CONFIG_FILE"] = os.devnull
    e["PIP_RETRIES"] = "0"
    e["PIP_TIMEOUT"] = "2"
    e.pop("PIP_CERT", None)
    return e


def discover(suite, e, timeout=900):
    return subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/" + suite], cwd=ROOT, env=e,
                          capture_output=True, text=True, timeout=timeout)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="kritva-offline-")
        cls.blockdir = Path(cls._tmp.name) / "block"
        cls.blockdir.mkdir()
        (cls.blockdir / "sitecustomize.py").write_text(BLOCK, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class OfflineBlock(Base):
    def test_the_block_stops_connections_and_name_resolution(self):
        probe = ("import socket, sys, urllib.request\n"
                 "for f in (lambda: socket.create_connection(('127.0.0.1', 9), 1),\n"
                 "          lambda: socket.getaddrinfo('example.com', 443),\n"
                 "          lambda: urllib.request.urlopen('http://127.0.0.1:9/', timeout=1)):\n"
                 "    try:\n        f()\n    except OSError as e:\n        assert 'network disabled' in str(e) or 'urlopen' in str(e), e\n"
                 "    else:\n        sys.exit(1)\n")
        r = subprocess.run([sys.executable, "-c", probe], env=offline_env(self.blockdir), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    @unittest.skipIf(OFFLINE_SUITE, "nested offline run")
    def test_non_packaging_suites_pass_offline(self):
        e = offline_env(self.blockdir)
        for suite in SUITES:
            with self.subTest(suite=suite):
                r = discover(suite, e)
                self.assertEqual(r.returncode, 0, "%s\n%s" % (suite, (r.stdout + r.stderr)[-1500:]))
                self.assertIn("OK", r.stderr)

    @unittest.skipIf(OFFLINE_SUITE, "nested offline run")
    def test_packaging_suite_passes_offline_with_a_prepared_wheelhouse(self):
        """NETWORK TEST (prepares the wheelhouse online once; the suite itself then runs with the network blocked)."""
        if os.environ.get("KRITVA_WHEELHOUSE"):
            wheelhouse = Path(os.environ["KRITVA_WHEELHOUSE"])
            prepared = None
        else:
            prepared = tempfile.TemporaryDirectory(prefix="kritva-wheelhouse-")
            wheelhouse = Path(prepared.name)
            r = subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary", ":all:",
                                "--dest", str(wheelhouse), "-r", str(ROOT / "release" / "build-requirements.txt")],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                prepared.cleanup()
                unavailable(self, "cannot prepare a wheelhouse of the pinned build tools: %s" % (r.stderr.strip()[-300:]))
        try:
            e = offline_env(self.blockdir, KRITVA_WHEELHOUSE=str(wheelhouse))
            if IN_CI:
                e["CI"] = "true"
            r = discover("packaging", e)
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, out[-2000:])
            import re
            m = re.search(r"PACKAGING-EVIDENCE mandatory=(\d+) executed=(\d+)", out)
            self.assertTrue(m, out[-500:])
            self.assertEqual(m.group(1), m.group(2), "every mandatory packaging test must run offline")
        finally:
            if prepared:
                prepared.cleanup()


class MissingBuildTools(Base):
    """Packaging without a wheelhouse and without network cannot get the build tools."""

    def run_packaging(self, ci, wheelhouse=None):
        extra = {"KRITVA_WHEELHOUSE": wheelhouse} if wheelhouse else {}
        e = offline_env(self.blockdir, **extra)
        for k in ("CI", "GITHUB_ACTIONS"):
            e.pop(k, None)
        if ci:
            e["CI"] = "true"
        return discover("packaging", e)

    @unittest.skipIf(OFFLINE_SUITE, "nested offline run")
    def test_in_ci_a_missing_build_tool_fails_the_run(self):
        r = self.run_packaging(ci=True)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, out[-800:])
        self.assertIn("UNAVAILABLE", out)
        self.assertRegex(out, r"packaging prerequisite missing in CI|mandatory packaging tests did not run in CI")

    @unittest.skipIf(OFFLINE_SUITE, "nested offline run")
    def test_in_ci_an_unusable_wheelhouse_fails_the_run(self):
        with TempDir() as d:
            r = self.run_packaging(ci=True, wheelhouse=str(d / "does-not-exist"))
            self.assertNotEqual(r.returncode, 0)
            r = self.run_packaging(ci=True, wheelhouse=str(d))                     # exists but holds no wheel
            self.assertNotEqual(r.returncode, 0)

    @unittest.skipIf(OFFLINE_SUITE, "nested offline run")
    def test_on_a_developer_machine_it_is_a_skip_with_the_reason_never_a_pass(self):
        r = self.run_packaging(ci=False)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out[-800:])
        self.assertIn("skipped=", out)
        self.assertIn("UNAVAILABLE", out)


class NetworkTestsAreIdentified(unittest.TestCase):
    def test_every_network_test_is_listed_and_excluded_from_the_offline_suite(self):
        marked = {n for n in dir(OfflineBlock) if n.startswith("test_") and "wheelhouse" in n}
        self.assertEqual(marked, NETWORK_TESTS)
        src = Path(__file__).read_text(encoding="utf-8")
        self.assertIn("Justification", src)
        for sec in ROOT.glob("tests/*/test_*.py"):
            if sec.name == "test_offline.py":
                continue
            text = sec.read_text(encoding="utf-8")
            if sec.parent.name == "packaging":
                continue          # the one fetch, covered above (a wheelhouse removes it)
            for needle in ("urlopen(", "create_connection(", "requests.", "pip download", "git clone", "git fetch",
                           "git pull", "import urllib", "import http.client", "import socket"):
                if needle in text:
                    self.fail("%s uses the network (%s) and is not identified" % (sec, needle))


if __name__ == "__main__":
    unittest.main()
