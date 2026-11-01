"""Shared helpers of the KOS-SENSE-008 security tests (standard library only, synthetic data only)."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def env(**extra):
    e = dict(os.environ)
    e["PYTHONPATH"] = os.pathsep.join([str(SRC)] + ([e["PYTHONPATH"]] if e.get("PYTHONPATH") else []))
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra)
    return e


def run_module(module, *args, cwd=None, timeout=60, stdin=None, **extra_env):
    """Run `python3 -m kritva_sense.<module>` (or `kritva_sense` itself) in a fresh interpreter."""
    name = "kritva_sense" if module == "validate" else "kritva_sense." + module
    return subprocess.run([sys.executable, "-m", name, *map(str, args)], cwd=cwd, env=env(**extra_env),
                          capture_output=True, text=True, timeout=timeout, input=stdin)


def run_python(code, *args, cwd=None, timeout=60, **extra_env):
    return subprocess.run([sys.executable, "-c", code, *map(str, args)], cwd=cwd, env=env(**extra_env),
                          capture_output=True, text=True, timeout=timeout)


class TempDir:
    def __enter__(self):
        self._t = tempfile.TemporaryDirectory(prefix="kritva-sec-")
        return Path(self._t.name)

    def __exit__(self, *exc):
        self._t.cleanup()


def table(text, heading):
    """The rows of the first Markdown table under `## heading` as lists of cell strings (header row excluded)."""
    m = re.search(r"(?ms)^## %s\n(.*?)(?=^## |\Z)" % re.escape(heading), text)
    if not m:
        raise AssertionError("section %r not found" % heading)
    rows = []
    for line in m.group(1).splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows[1:]


def task_status(task_id):
    for line in (ROOT / "planning" / "TASKS.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| %s \| [^|]+ \| ([A-Z_]+)" % re.escape(task_id), line)
        if m:
            return m.group(1)
    raise AssertionError("%s is not in planning/TASKS.md" % task_id)


IN_CI = "true" in (os.environ.get("CI", "").lower(), os.environ.get("GITHUB_ACTIONS", "").lower())


def unavailable(test, reason):
    """A security check that cannot run is a SKIP with its reason on a developer machine and a FAILURE in CI:
    an incomplete security check never counts as a pass (AC-807)."""
    if IN_CI:
        test.fail("security check could not run in CI: %s" % reason)
    test.skipTest(reason)
