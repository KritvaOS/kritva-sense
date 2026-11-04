"""Shared helpers of the integration scenarios (standard library only)."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import fixture  # noqa: F401  (puts src on sys.path)

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
HERE = Path(__file__).resolve().parent


class TempDir:
    def __enter__(self):
        self._t = tempfile.TemporaryDirectory(prefix="kritva-int-")
        return Path(self._t.name)

    def __exit__(self, *exc):
        self._t.cleanup()


def env(**extra):
    e = dict(os.environ)
    e["PYTHONPATH"] = os.pathsep.join([str(SRC)] + ([e["PYTHONPATH"]] if e.get("PYTHONPATH") else []))
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra)
    return e


def run(args, cwd, stdin=None, timeout=60, **extra_env):
    return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, env=env(**extra_env), capture_output=True,
                          text=True, timeout=timeout, input=stdin)


def launcher(directory, name, function):
    """A console-script launcher of the form pip generates for an entry point `kritva_sense._entry:<function>`."""
    path = Path(directory) / name
    path.write_text("import sys\nfrom kritva_sense._entry import %s\nsys.exit(%s())\n" % (function, function),
                    encoding="utf-8")
    return path


def scenario_of(cls):
    return getattr(cls, "SCENARIO", None)
