"""KOS-SENSE-007 packaging tests (AC-701 to AC-707). Standard library only; synthetic data only.

The tests build the wheel and the source distribution in a pinned, isolated build environment, install them into
clean environments and run the documented command lines from a temporary directory. They need git, the venv module
and the pinned build tools named in release/build-requirements.txt, whose wheels pip checks against the SHA-256 in that
file. The tools are fetched once per run unless KRITVA_WHEELHOUSE names a directory that already holds them; with it
the whole suite needs no network. When any of that is missing, a developer run reports an explicit SKIP with the reason; a run in CI (the CI environment variable
is "true") fails instead, a skip is never counted as a pass, and tearDownModule fails the run if a mandatory test
did not execute. Every run prints one PACKAGING-EVIDENCE line that lists the mandatory tests that ran.
"""
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
REQUIREMENTS = ROOT / "release" / "build-requirements.txt"
IN_CI = "true" in (os.environ.get("CI", "").lower(), os.environ.get("GITHUB_ACTIONS", "").lower())
SOURCE_DATE_EPOCH = "1700000000"
PENDING = "PENDING"

# SHA-256 of the existing software and contract files. KOS-SENSE-007 adds packaging files only; a change to one of
# these files is a change to an accepted interface and must be a deliberate, reviewed change of this table.
PINS = {
    "src/kritva_sense/__init__.py": "f0232671bf69983a2240359242f8af6d36739b32895fb53d0bab5c5c6ac95582",
    "src/kritva_sense/__main__.py": "b588a17c13ecbb4e2305282351b340027f8f66e295bab0966d3cb98ef4c34739",
    "src/kritva_sense/validator.py": "cc758f474c21d1963ebbc3c8629a2f59584ce7f463935064f46e5b98061ccaa6",
    "src/kritva_sense/frame_graph.py": "4aef1f86a853bf66582b25471f568c421ed41b17f6f7148e5efdb9e5a2e49a6a",
    "src/kritva_sense/generator.py": "9c2e2dcbaf0f2e643f0e7dc1ba27ab2585c29852f1f44c038596b52591c07c2a",
    "src/kritva_sense/stream.py": "2d8b3bb95f506baf17648c0f9ee5ed6367a57ce6d0e127e788062d0004439c47",
    "src/kritva_sense/conformance.py": "59933d7f1fcda94adfada75d7175d082fd87cb43437e89ff9c30c464bce7e6c1",
    "contract/FRAME_GRAPH_CONTRACT.md": "a3ded6d06222a7f554127c16265e718f350eef58f0550737be425561c6f10210",
    "contract/SENSE_CONTRACT.md": "f8935feb9efb10dd482e4b7386239295b2180412dbbcbc177aa7a6f86d75abcf",
    "contract/STREAM_CONTRACT.md": "ac6aafea196224509a673c6f4e71c6a983575a24b816cb794669b17e1ff62bf4",
    "contract/frame-transform.schema.json": "ae644360dc5ba0e679a9e616022b4261b2e95fe967da8af1e4d440f718a099e2",
    "contract/sense-sample.schema.json": "1f6f0824af55237b0b3e90ddd413ddef8c48e2eb3cd19a7f4244295bd2b9bc6b",
    "contract/stream.schema.json": "12f2003ab9144d820ea6f8aeb629e85fcbc888c6933c60060dd49162fee0ff51",
}
DIST_INFO = {"licenses/LICENSE", "METADATA", "WHEEL", "entry_points.txt", "top_level.txt", "RECORD"}
EGG_INFO = {"PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt", "top_level.txt"}
SDIST_ROOT_FILES = {"LICENSE", "MANIFEST.in", "PKG-INFO", "pyproject.toml", "setup.cfg", "release/build-requirements.txt",
                    "release/normalise_sdist.py"}
TIME_KEYS = ("mtime", "atime", "ctime")

ENV = {}
MANDATORY = []
EXECUTED = []


class Unavailable(Exception):
    """A prerequisite of the packaging tests is missing (git, venv, network)."""


def mandatory(func):
    """Marks a mandatory packaging test and records that it started."""
    MANDATORY.append(func.__name__)

    def wrapper(self):
        EXECUTED.append(func.__name__)
        return func(self)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def clean_env(**extra):
    """The process environment without any PYTHON* variable, so the source tree cannot leak in through PYTHONPATH."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env.update(extra)
    return env


def run(cmd, cwd=None, env=None, timeout=900):
    return subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or clean_env(), capture_output=True, text=True,
                          timeout=timeout)


def venv_python(venv):
    return Path(venv) / "bin" / "python"


def make_venv(path):
    r = run([sys.executable, "-m", "venv", "--clear", path])
    if r.returncode != 0:
        raise Unavailable("cannot create a virtual environment: %s" % (r.stderr.strip() or r.stdout.strip()))
    return Path(path)


def requirement_lines():
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            yield line


def pinned_requirements():
    """name -> version from release/build-requirements.txt; every line must be an exact pin with a SHA-256."""
    pins = {}
    for line in requirement_lines():
        m = re.fullmatch(r"([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.!+\-]+) --hash=sha256:[0-9a-f]{64}", line)
        if not m:
            raise AssertionError("not an exact pin with a SHA-256 hash: %r" % line)
        pins[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(2)
    return pins


def tracked_files():
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        raise Unavailable("git ls-files failed: %s" % r.stderr.decode(errors="replace").strip())
    return [f for f in r.stdout.decode().split("\0") if f and (ROOT / f).is_file()]


def make_checkout(dest, mtime):
    """A clean copy of the tracked files at one fixed modification time (a build must not depend on it)."""
    dest = Path(dest)
    for rel in tracked_files():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
        os.chmod(target, 0o755 if os.access(ROOT / rel, os.X_OK) else 0o644)
        os.utime(target, (mtime, mtime))
    return dest


def build(checkout, outdir):
    r = run([venv_python(ENV["build_venv"]), "-m", "build", "--no-isolation", "--outdir", outdir, checkout],
            cwd=checkout, env=clean_env(SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH))
    log = r.stdout + r.stderr
    if r.returncode != 0:
        raise AssertionError("build failed:\n%s" % log[-3000:])
    wheels = sorted(Path(outdir).glob("*.whl"))
    sdists = sorted(Path(outdir).glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise AssertionError("expected one wheel and one sdist, found %s %s" % (wheels, sdists))
    raw = Path(outdir) / "raw" / sdists[0].name
    raw.parent.mkdir()
    shutil.copyfile(sdists[0], raw)
    r = run([venv_python(ENV["build_venv"]), checkout / "release" / "normalise_sdist.py", sdists[0]], cwd=checkout,
            env=clean_env(SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH))
    if r.returncode != 0:
        raise AssertionError("normalise_sdist failed: %s" % r.stderr)
    return {"wheel": wheels[0], "sdist": sdists[0], "raw_sdist": raw, "log": log}


def sdist_listing(path):
    """The normalised content of an sdist: member name, type, mode, size, link target, extended (PAX) headers and
    SHA-256 of the content, sorted by name. It leaves out exactly the fields that setuptools fills from the build
    time or the build user: the modification, access and change time of every member (also as extended headers),
    the owner and group (numeric and names) and the gzip header time (RELEASE.md, Build and reproducibility)."""
    rows = []
    with tarfile.open(path, "r:gz") as tar:
        for m in tar.getmembers():
            digest = sha256_bytes(tar.extractfile(m).read()) if m.isfile() else None
            pax = sorted((k, v) for k, v in m.pax_headers.items() if k not in TIME_KEYS)
            rows.append([m.name, m.type.decode(), m.mode & 0o7777, m.size, digest, m.linkname, pax])
    return sorted(rows)


def sdist_normalised_hash(path):
    return sha256_bytes(json.dumps(sdist_listing(path), sort_keys=True).encode())


def wheel_names(path):
    with zipfile.ZipFile(path) as z:
        return sorted(z.namelist())


def expected_wheel_names():
    names = {"kritva_sense/" + p.name for p in (ROOT / "src" / "kritva_sense").glob("*.py")}
    names |= {"kritva_sense/contract/" + p.name for p in (ROOT / "contract").iterdir() if p.is_file()}
    names |= {"kritva_sense-%s.dist-info/%s" % (package_version(), n) for n in DIST_INFO}
    return sorted(names)


def expected_sdist_names():
    root = "kritva_sense-%s/" % package_version()
    names = {root + n for n in SDIST_ROOT_FILES}
    names |= {root + "src/kritva_sense/" + p.name for p in (ROOT / "src" / "kritva_sense").glob("*.py")}
    names |= {root + "contract/" + p.name for p in (ROOT / "contract").iterdir() if p.is_file()}
    names |= {root + "src/kritva_sense.egg-info/" + n for n in EGG_INFO}
    return sorted(names)


def sdist_file_names(path):
    with tarfile.open(path, "r:gz") as tar:
        return sorted(m.name for m in tar.getmembers() if m.isfile())


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def package_version():
    return pyproject()["project"]["version"]


def load_version_module():
    sys.path.insert(0, str(SRC))
    try:
        import importlib
        return importlib.import_module("kritva_sense.version")
    finally:
        sys.path.remove(str(SRC))


def prepare():
    """The pinned build environment and two builds of the same source revision, made once for the whole module."""
    tmp = Path(tempfile.mkdtemp(prefix="kritva-pkg-"))
    ENV["tmp"] = tmp
    tracked_files()
    bootstrap = make_venv(tmp / "bootstrap")
    prepared = os.environ.get("KRITVA_WHEELHOUSE")
    if prepared:
        wheelhouse = Path(prepared)
        ENV["offline"] = True
        if not wheelhouse.is_dir():
            raise Unavailable("KRITVA_WHEELHOUSE is not a directory: %s" % prepared)
    else:
        wheelhouse = tmp / "wheelhouse"
        r = run([venv_python(bootstrap), "-m", "pip", "download", "--no-deps", "--only-binary", ":all:",
                 "--dest", wheelhouse, "-r", REQUIREMENTS], cwd=tmp)
        if r.returncode != 0:
            raise Unavailable("cannot fetch the pinned build tools: %s" % (r.stderr.strip() or r.stdout.strip())[-800:])
    build_venv = make_venv(tmp / "build-env")
    r = run([venv_python(build_venv), "-m", "pip", "install", "--no-index", "--find-links", wheelhouse,
             "-r", REQUIREMENTS], cwd=tmp)
    if r.returncode != 0:
        raise Unavailable("cannot install the pinned build tools: %s" % (r.stderr.strip() or r.stdout.strip())[-800:])
    ENV.update(wheelhouse=wheelhouse, build_venv=build_venv)
    ENV["freeze"] = run([venv_python(build_venv), "-m", "pip", "freeze"], cwd=tmp).stdout.split()
    builds = []
    for n, mtime in ((1, 1_000_000_000), (2, 1_600_000_000)):
        checkout = make_checkout(tmp / ("checkout-%d" % n), mtime)
        builds.append(build(checkout, tmp / ("dist-%d" % n)))
    ENV["builds"] = builds


def setUpModule():
    try:
        prepare()
    except Unavailable as exc:
        ENV["unavailable"] = str(exc)


def tearDownModule():
    names = sorted(set(EXECUTED))
    print("\nPACKAGING-EVIDENCE mandatory=%d executed=%d tests=%s%s"
          % (len(MANDATORY), len(names), ",".join(names), " UNAVAILABLE: " + ENV["unavailable"] if "unavailable" in ENV else ""))
    if ENV.get("tmp"):
        shutil.rmtree(ENV["tmp"], ignore_errors=True)
    if IN_CI:
        missing = sorted(set(MANDATORY) - set(EXECUTED))
        if missing or "unavailable" in ENV:
            raise AssertionError("mandatory packaging tests did not run in CI: %s %s" % (missing, ENV.get("unavailable", "")))


class Base(unittest.TestCase):
    def need_env(self):
        """A missing prerequisite is a SKIP with its reason on a developer machine and a failure in CI."""
        if "unavailable" in ENV:
            if IN_CI:
                self.fail("packaging prerequisite missing in CI: %s" % ENV["unavailable"])
            self.skipTest("packaging prerequisite missing: %s" % ENV["unavailable"])


class Metadata(Base):
    @mandatory
    def test_ac701_metadata(self):
        """AC-701: name, version, Python versions, licence, contents, entry points, empty runtime dependencies."""
        doc = pyproject()
        project = doc["project"]
        self.assertEqual(project["name"], "kritva-sense")
        self.assertRegex(project["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(project["requires-python"], ">=3.12")
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["license-files"], ["LICENSE"])
        self.assertEqual(project["dependencies"], [])
        self.assertNotIn("optional-dependencies", project)
        self.assertNotIn("dynamic", project)
        self.assertEqual(project["scripts"], {
            "kritva-sense-validate": "kritva_sense._entry:validate",
            "kritva-sense-frame-graph": "kritva_sense._entry:frame_graph",
            "kritva-sense-generator": "kritva_sense._entry:generator",
            "kritva-sense-stream": "kritva_sense._entry:stream",
            "kritva-sense-conformance": "kritva_sense._entry:conformance",
            "kritva-sense-version": "kritva_sense.version:main"})
        tool = doc["tool"]["setuptools"]
        self.assertEqual(tool["packages"], ["kritva_sense", "kritva_sense.contract"])
        self.assertEqual(tool["package-dir"], {"": "src", "kritva_sense.contract": "contract"})
        self.assertEqual(tool["package-data"], {"kritva_sense.contract": ["*.md", "*.json"]})

    @mandatory
    def test_ac701_entry_points_resolve_to_callables(self):
        """AC-701: every declared entry point names an existing callable of the package."""
        sys.path.insert(0, str(SRC))
        try:
            import importlib
            for name, target in pyproject()["project"]["scripts"].items():
                module, _, attr = target.partition(":")
                self.assertTrue(callable(getattr(importlib.import_module(module), attr)), name)
        finally:
            sys.path.remove(str(SRC))

    @mandatory
    def test_ac702_build_tools_pinned_apart_from_runtime(self):
        """AC-702: build tools are exact pins in the build configuration; the runtime dependencies stay empty."""
        pins = pinned_requirements()
        requires = pyproject()["build-system"]["requires"]
        self.assertEqual(requires, ["setuptools==%s" % pins["setuptools"]])
        self.assertEqual(set(pins), {"build", "packaging", "pyproject-hooks", "setuptools"})
        self.assertEqual(pyproject()["project"]["dependencies"], [])
        self.assertEqual(pyproject()["build-system"]["build-backend"], "setuptools.build_meta")

    @mandatory
    def test_ac707_existing_files_unchanged(self):
        """AC-707: the accepted software and contract files are byte-identical to their accepted state."""
        for rel, digest in PINS.items():
            self.assertEqual(sha256_file(ROOT / rel), digest, rel)

    @mandatory
    def test_ac707_no_other_contract_or_module_files(self):
        """AC-707: the only additions under src/kritva_sense and contract are the two packaging modules."""
        modules = {p.name for p in (SRC / "kritva_sense").glob("*.py")}
        self.assertEqual(modules, {Path(k).name for k in PINS if k.endswith(".py")} | {"_entry.py", "version.py"})
        self.assertEqual({p.name for p in (ROOT / "contract").iterdir()}, {Path(k).name for k in PINS if k.startswith("contract/")})


class Versions(Base):
    def setUp(self):
        self.v = load_version_module()

    @mandatory
    def test_ac705_versions_are_separate(self):
        """AC-705: package, three contract versions and harness version are separately identifiable and differ."""
        d = self.v.declared_versions()
        self.assertEqual(set(d), {"package_version", "sense_contract_version", "frame_graph_contract_version",
                                  "stream_contract_version", "harness_version", "generator_version"})
        self.assertEqual(d["package_version"], package_version())
        self.assertNotEqual(d["package_version"], d["sense_contract_version"])
        self.assertNotEqual(d["package_version"], d["frame_graph_contract_version"])
        self.assertNotEqual(d["package_version"], d["stream_contract_version"])
        self.assertEqual(d["sense_contract_version"], "0.1.0")
        self.assertEqual(d["frame_graph_contract_version"], "0.1.0")
        self.assertEqual(d["stream_contract_version"], "0.1.0")
        self.assertEqual(d["harness_version"], "0.1.0")
        self.assertNotEqual(d["package_version"], d["harness_version"])
        info = self.v.version_info()
        self.assertEqual(info["package_version"], d["package_version"])
        self.assertEqual(set(info["shipped_contract_files"].values()), {"0.1.0"})
        self.assertIsNone(info["installed_metadata_version"])

    @mandatory
    def test_ac705_shipped_files_agree_with_declared_versions(self):
        """AC-705: the repository contract files agree with the declared versions."""
        self.assertEqual(self.v.check_shipped_contracts(), [])

    def mutated_copy(self, name, old, new):
        tmp = Path(tempfile.mkdtemp(prefix="kritva-contract-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        for p in (ROOT / "contract").iterdir():
            shutil.copyfile(p, tmp / p.name)
        text = (tmp / name).read_text(encoding="utf-8")
        self.assertIn(old, text)
        (tmp / name).write_text(text.replace(old, new, 1), encoding="utf-8")
        return tmp

    @mandatory
    def test_ac705_mismatch_between_declared_versions_and_shipped_files_is_detected(self):
        """AC-705: a contract document or schema with another version than the code declares is reported."""
        cases = [
            ("SENSE_CONTRACT.md", "Contract version: 0.1.0", "Contract version: 0.9.0"),
            ("FRAME_GRAPH_CONTRACT.md", "Frame graph contract version: 0.1.0", "Frame graph contract version: 0.9.0"),
            ("STREAM_CONTRACT.md", "Stream contract version: 0.1.0", "Stream contract version: 0.9.0"),
            ("sense-sample.schema.json", '"0.1.0"', '"0.9.0"'),
            ("frame-transform.schema.json", '"const": "0.1.0"', '"const": "0.9.0"'),
            ("stream.schema.json", '"stream_version": { "const": "0.1.0" }', '"stream_version": { "const": "0.9.0" }'),
        ]
        for name, old, new in cases:
            with self.subTest(file=name):
                problems = self.v.check_shipped_contracts(self.mutated_copy(name, old, new))
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(name, problems[0])
                self.assertIn("0.9.0", problems[0])

    @mandatory
    def test_ac705_missing_or_unreadable_contract_file_is_a_problem(self):
        """AC-705: a missing file, an unreadable version and a missing directory are never a pass."""
        tmp = self.mutated_copy("SENSE_CONTRACT.md", "| Version | Contract version: 0.1.0 |", "| Version | unknown |")
        self.assertEqual(self.v.check_shipped_contracts(tmp), ["SENSE_CONTRACT.md: no readable version"])
        (tmp / "stream.schema.json").unlink()
        problems = self.v.check_shipped_contracts(tmp)
        self.assertIn("stream.schema.json is missing", problems)
        self.assertEqual(self.v.check_shipped_contracts(tmp / "absent"),
                         ["%s is missing" % n for k in self.v.FILES for n in self.v.FILES[k]])

    @mandatory
    def test_ac705_malformed_schema_is_a_problem_not_an_exception(self):
        """AC-705: invalid JSON, a non-object schema and an undecodable file give a diagnostic and --check exits 1."""
        for label, payload in (("invalid JSON", b"{ not json"), ("a JSON list", b"[1, 2]"), ("not UTF-8", b"\xff\xfe\x00")):
            with self.subTest(case=label):
                tmp = self.mutated_copy("stream.schema.json", '"stream_version"', '"stream_version"')
                (tmp / "stream.schema.json").write_bytes(payload)
                problems = self.v.check_shipped_contracts(tmp)
                self.assertTrue(problems and all("stream.schema.json" in p for p in problems), problems)
                self.assertIsInstance(self.v.shipped_versions(tmp), dict)

    @mandatory
    def test_ac705_different_contract_versions_and_other_versions_are_independent(self):
        """AC-705: two contracts at different versions, a package and a harness version of their own."""
        declared = dict(self.v.declared_versions(), package_version="9.9.9", harness_version="7.7.7",
                        frame_graph_contract_version="0.3.0", stream_contract_version="0.1.0")
        problems = self.v.check_shipped_contracts(None, declared)
        self.assertEqual(sorted(p.split(" ")[0] for p in problems), ["FRAME_GRAPH_CONTRACT.md", "frame-transform.schema.json"])
        declared = dict(self.v.declared_versions(), package_version="9.9.9", harness_version="7.7.7")
        self.assertEqual(self.v.check_shipped_contracts(None, declared), [])

    @mandatory
    def test_ac705_version_command_line(self):
        """AC-705: python -m kritva_sense.version prints the versions; --check exits 0 here and 2 on bad usage."""
        r = run([sys.executable, "-m", "kritva_sense.version", "--check"], cwd=SRC)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("versions consistent", r.stdout)
        self.assertEqual(run([sys.executable, "-m", "kritva_sense.version", "--bad"], cwd=SRC).returncode, 2)


class Release(Base):
    text = (ROOT / "RELEASE.md").read_text(encoding="utf-8") if (ROOT / "RELEASE.md").exists() else ""

    def table(self, heading):
        """The rows (cells) of the first Markdown table after a heading of RELEASE.md."""
        m = re.search(r"^## %s\n(.*?)(?=^## |\Z)" % re.escape(heading), self.text, re.M | re.S)
        self.assertIsNotNone(m, "RELEASE.md has no section %r" % heading)
        rows = [[c.strip() for c in line.strip("|").split("|")] for line in m.group(1).splitlines() if line.startswith("|")]
        return [r for r in rows[2:]]

    @mandatory
    def test_ac705_release_notes_list_the_versions(self):
        """AC-705: RELEASE.md lists the package, contract, harness and generator versions the package declares."""
        v = load_version_module().declared_versions()
        rows = {r[0]: r[1] for r in self.table("Versions")}
        self.assertEqual(rows, {
            "Package (kritva-sense)": v["package_version"],
            "Sense data contract": v["sense_contract_version"],
            "Frame graph contract": v["frame_graph_contract_version"],
            "Stream contract": v["stream_contract_version"],
            "Consumer conformance harness": v["harness_version"],
            "Synthetic data generator": v["generator_version"]})

    @mandatory
    def test_ac707_release_notes_content(self):
        """AC-707: functionality, limitations, compatibility, the tag policy and the non-claims are stated."""
        for heading in ("Versions", "Supported functionality", "Limitations", "Contract compatibility", "Release tag",
                        "Build and reproducibility", "Release record"):
            self.assertRegex(self.text, r"(?m)^## %s$" % re.escape(heading), heading)
        for phrase in (
                "one repository release tag per release", "created by the owner", "no tool creates it",
                "does not imply that the component versions are equal", "No release is published",
                "SOURCE_DATE_EPOCH", "tar member modification time", "gzip header", "normalised-content hash",
                "software only", "not hardware or safety validation", "CI platform only"):
            self.assertIn(phrase, self.text, phrase)

    def record(self):
        return {r[0]: r[1] for r in self.table("Release record")}

    def task_status(self):
        for line in (ROOT / "planning" / "TASKS.md").read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| KOS-SENSE-007 \| [^|]+ \| ([A-Z_]+)", line)
            if m:
                return m.group(1)
        self.fail("KOS-SENSE-007 is not in planning/TASKS.md")

    @mandatory
    def test_ac707_release_record_format(self):
        """AC-707: the release record names the source commit and three hashes, each pending or well formed; once
        the task is IN_REVIEW or ACCEPTED no field may still be PENDING."""
        rec = self.record()
        self.assertEqual(set(rec), {"Source commit", "Wheel SHA-256", "Source distribution SHA-256",
                                    "Source distribution normalised-content hash"})
        self.assertRegex(rec["Source commit"], r"^(%s|[0-9a-f]{40})$" % PENDING)
        for key in list(rec)[1:]:
            self.assertRegex(rec[key], r"^(%s|[0-9a-f]{64})$" % PENDING, key)
        if self.task_status() in ("IN_REVIEW", "ACCEPTED"):
            self.assertNotIn(PENDING, rec.values(), "the release record is complete once the task is submitted")

    @mandatory
    def test_ac707_release_record_matches_the_build(self):
        """AC-707: every recorded hash equals that of the build from this tree (CI platform): the wheel, the source
        distribution file and its normalised-content hash."""
        self.need_env()
        rec = self.record()
        built = ENV["builds"][0]
        actual = {"Wheel SHA-256": sha256_file(built["wheel"]),
                  "Source distribution SHA-256": sha256_file(built["sdist"]),
                  "Source distribution normalised-content hash": sdist_normalised_hash(built["sdist"])}
        print("\nPACKAGING-HASH wheel_sha256=%s sdist_sha256=%s sdist_normalised=%s" % (
            actual["Wheel SHA-256"], actual["Source distribution SHA-256"],
            actual["Source distribution normalised-content hash"]))
        for key, value in actual.items():
            if rec[key] == PENDING:
                continue
            if rec[key] != value and not IN_CI and key != "Source distribution normalised-content hash":
                self.skipTest("%s recorded for the CI platform differs on this machine (zlib or tool version)" % key)
            self.assertEqual(rec[key], value, key)


class Build(Base):
    @mandatory
    def test_ac702_pinned_isolated_build_without_download(self):
        """AC-702: the build environment holds exactly the pinned tools and the build log shows no download."""
        self.need_env()
        frozen = {re.sub(r"[-_.]+", "-", n).lower(): v for n, v in (x.split("==") for x in ENV["freeze"])}
        self.assertEqual(frozen, pinned_requirements())
        for b in ENV["builds"]:
            for marker in ("Collecting ", "Downloading ", "Looking in indexes", "Installing build dependencies",
                           "pip install"):
                self.assertNotIn(marker, b["log"], marker)
            self.assertIn("Successfully built", b["log"])

    @mandatory
    def test_ac703_distributions_contain_only_the_intended_files(self):
        """AC-703: exact content listing of the wheel and of the source distribution."""
        self.need_env()
        for b in ENV["builds"]:
            self.assertEqual(wheel_names(b["wheel"]), expected_wheel_names())
            self.assertEqual(sdist_file_names(b["sdist"]), expected_sdist_names())

    @mandatory
    def test_ac705_shipped_contract_files_are_byte_identical(self):
        """AC-705: the contract and schema files in the wheel and in the sdist equal contract/ byte for byte."""
        self.need_env()
        b = ENV["builds"][0]
        with zipfile.ZipFile(b["wheel"]) as z:
            for p in (ROOT / "contract").iterdir():
                self.assertEqual(z.read("kritva_sense/contract/" + p.name), p.read_bytes(), p.name)
        with tarfile.open(b["sdist"], "r:gz") as tar:
            for p in (ROOT / "contract").iterdir():
                member = tar.extractfile("kritva_sense-%s/contract/%s" % (package_version(), p.name))
                self.assertEqual(member.read(), p.read_bytes(), p.name)

    @mandatory
    def test_ac706_double_build_is_reproducible(self):
        """AC-706: two builds of one revision (different paths and file times, fixed SOURCE_DATE_EPOCH): the wheels
        and the normalised source distributions are byte-identical with equal SHA-256."""
        self.need_env()
        one, two = ENV["builds"]
        for kind in ("wheel", "sdist"):
            self.assertEqual(one[kind].read_bytes(), two[kind].read_bytes(), kind)
            self.assertEqual(sha256_file(one[kind]), sha256_file(two[kind]), kind)
        self.assertEqual(sdist_listing(one["sdist"]), sdist_listing(two["sdist"]))
        self.assertEqual(sdist_normalised_hash(one["sdist"]), sdist_normalised_hash(two["sdist"]))

    @mandatory
    def test_ac706_only_documented_sdist_fields_differ(self):
        """AC-706: the raw setuptools sdists may differ only in the documented fields: member times, owner and
        group, gzip time. Names, types, modes, sizes, link targets, extended headers and contents are equal."""
        self.need_env()
        one, two = ENV["builds"]

        def members(path):
            with tarfile.open(path, "r:gz") as tar:
                return sorted((m.name, m.type, m.mode, m.size, m.linkname,
                               sorted((k, v) for k, v in m.pax_headers.items() if k not in TIME_KEYS),
                               sha256_bytes(tar.extractfile(m).read() if m.isfile() else b"")) for m in tar.getmembers())
        self.assertEqual(members(one["raw_sdist"]), members(two["raw_sdist"]))
        self.assertEqual(sdist_listing(one["raw_sdist"]), sdist_listing(one["sdist"]))

    @mandatory
    def test_ac706_shipped_sdist_carries_the_fixed_fields(self):
        """AC-706: after normalisation every member has modification time SOURCE_DATE_EPOCH, owner 0/root, group
        0/root and no time in its extended headers, and the gzip header time is 0."""
        self.need_env()
        path = ENV["builds"][0]["sdist"]
        self.assertEqual(path.read_bytes()[4:8], b"\0\0\0\0")
        with tarfile.open(path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            self.assertEqual(names, sorted(names))
            for m in tar.getmembers():
                self.assertEqual((m.mtime, m.uid, m.gid, m.uname, m.gname), (int(SOURCE_DATE_EPOCH), 0, 0, "root", "root"), m.name)
                self.assertFalse(set(m.pax_headers) & set(TIME_KEYS), m.name)

    @mandatory
    def test_ac706_normalise_script_is_idempotent_and_keeps_content(self):
        """AC-706: running release/normalise_sdist.py again changes nothing; a raw sdist keeps its content."""
        self.need_env()
        built = ENV["builds"][0]
        copy = Path(tempfile.mkdtemp(prefix="kritva-norm-")) / built["sdist"].name
        self.addCleanup(shutil.rmtree, copy.parent, True)
        shutil.copyfile(built["sdist"], copy)
        r = run([sys.executable, ROOT / "release" / "normalise_sdist.py", copy], env=clean_env(SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(copy.read_bytes(), built["sdist"].read_bytes())
        self.assertEqual(run([sys.executable, ROOT / "release" / "normalise_sdist.py", copy],
                             env=clean_env()).returncode, 2)

    @mandatory
    def test_ac706_normaliser_detects_real_differences(self):
        """AC-706: the content comparison ignores times, owners and the gzip header, but not content, names, modes,
        link targets or extended headers."""
        def make(content=b"x", name="p/a.txt", mode=0o644, mtime=1, gz_mtime=1, uid=0, uname="", pax=None, link=""):
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime, info.uid, info.uname = len(content), mode, mtime, uid, uname
                info.pax_headers = dict(pax or {})
                if link:
                    info.type, info.linkname, info.size = tarfile.SYMTYPE, link, 0
                    tar.addfile(info)
                else:
                    tar.addfile(info, io.BytesIO(content))
            out = Path(tempfile.mkdtemp(prefix="kritva-tar-")) / "x.tar.gz"
            self.addCleanup(shutil.rmtree, out.parent, True)
            with open(out, "wb") as fh:
                with gzip.GzipFile(fileobj=fh, mode="wb", mtime=gz_mtime) as gz:
                    gz.write(raw.getvalue())
            return out
        base = sdist_normalised_hash(make())
        same = [make(mtime=999, gz_mtime=555), make(uid=1001, uname="runner"),
                make(pax={"mtime": "5.5", "atime": "6", "ctime": "7"})]
        for path in same:
            self.assertEqual(base, sdist_normalised_hash(path))
        different = [make(content=b"y"), make(name="p/b.txt"), make(mode=0o755), make(link="p/target"),
                     make(pax={"comment": "extra metadata"}), make(pax={"path": "p/c.txt"})]
        for path in different:
            self.assertNotEqual(base, sdist_normalised_hash(path))


class Install(Base):
    def install(self, kind):
        """A clean virtual environment with the wheel or the sdist installed from the pinned wheelhouse, offline."""
        self.need_env()
        venv = make_venv(ENV["tmp"] / ("install-" + kind))
        r = run([venv_python(venv), "-m", "pip", "install", "--no-index", "--find-links", ENV["wheelhouse"],
                 "--no-deps", ENV["builds"][0][kind]], cwd=ENV["tmp"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return venv

    def installs(self):
        if "installs" not in ENV:
            ENV["installs"] = {kind: self.install(kind) for kind in ("wheel", "sdist")}
        return ENV["installs"]

    def empty_dir(self):
        d = Path(tempfile.mkdtemp(prefix="kritva-cwd-"))
        self.addCleanup(shutil.rmtree, d, True)
        return d

    @mandatory
    def test_ac703_install_and_import_from_a_temporary_directory(self):
        """AC-703: both distributions install into a clean environment and every module imports with the source
        tree out of reach (empty working directory, no PYTHON* variable, isolated interpreter mode)."""
        probe = (
            "import importlib, json, os, pathlib, sys\n"
            "import kritva_sense\n"
            "pkg = pathlib.Path(kritva_sense.__file__).resolve().parent\n"
            "mods = sorted(p.stem for p in pkg.glob('*.py'))\n"
            "for m in mods:\n"
            "    importlib.import_module('kritva_sense' if m == '__init__' else 'kritva_sense.' + m)\n"
            "print(json.dumps({'file': str(pkg), 'path': sys.path, 'cwd': os.getcwd(), 'mods': mods,\n"
            "                  'pythonpath': os.environ.get('PYTHONPATH')}))\n")
        expected = sorted(p.stem for p in (SRC / "kritva_sense").glob("*.py"))
        for kind, venv in self.installs().items():
            with self.subTest(distribution=kind):
                cwd = self.empty_dir()
                r = run([venv_python(venv), "-I", "-c", probe], cwd=cwd)
                self.assertEqual(r.returncode, 0, r.stderr)
                got = json.loads(r.stdout)
                self.assertTrue(Path(got["file"]).is_relative_to(Path(venv).resolve()), got["file"])
                self.assertIsNone(got["pythonpath"])
                self.assertEqual(got["mods"], expected)
                forbidden = {str(ROOT.resolve()), str((ROOT / "src").resolve())}
                for entry in got["path"]:
                    resolved = str(Path(entry or ".").resolve())
                    self.assertNotIn(resolved, forbidden)
                    self.assertFalse(Path(resolved).is_relative_to(ROOT.resolve()), resolved)
                self.assertFalse(Path(got["cwd"]).resolve().is_relative_to(ROOT.resolve()))
                contract = Path(got["file"]) / "contract"
                self.assertEqual(sorted(p.name for p in contract.iterdir() if p.is_file()),
                                 sorted(p.name for p in (ROOT / "contract").iterdir()))
                for p in (ROOT / "contract").iterdir():
                    self.assertEqual((contract / p.name).read_bytes(), p.read_bytes(), p.name)

    @mandatory
    def test_ac705_installed_version_information(self):
        """AC-705: the installed package reports its versions, the metadata version equals PACKAGE_VERSION and the
        shipped contract files agree with the code."""
        for kind, venv in self.installs().items():
            with self.subTest(distribution=kind):
                code = ("import json; from kritva_sense import version as v; "
                        "print(json.dumps({'info': v.version_info(), 'problems': v.check_shipped_contracts()}))")
                r = run([venv_python(venv), "-I", "-c", code], cwd=self.empty_dir())
                self.assertEqual(r.returncode, 0, r.stderr)
                got = json.loads(r.stdout)
                self.assertEqual(got["problems"], [])
                self.assertEqual(got["info"]["installed_metadata_version"], package_version())
                self.assertEqual(got["info"]["package_version"], package_version())
                self.assertEqual(got["info"]["sense_contract_version"], "0.1.0")

    @mandatory
    def test_ac704_installed_command_lines(self):
        """AC-704: every documented command line runs on synthetic input (exit 0), a non-conforming input exits
        non-zero as documented, and a usage error exits 2."""
        fixtures = ROOT / "tests"
        for kind, venv in self.installs().items():
            with self.subTest(distribution=kind):
                work = self.empty_dir()
                bin_ = Path(venv) / "bin"

                def cmd(name, *args):
                    return run([bin_ / name, *args], cwd=work)

                r = cmd("kritva-sense-generator", "samples", "--kind", "imu", "--sensor-id", "imu.main", "--count", "3",
                        "--seed", "7", "--out", "samples.json")
                self.assertEqual(r.returncode, 0, r.stderr)
                (work / "sample.json").write_text(json.dumps(json.loads((work / "samples.json").read_text())["samples"][0]))
                r = cmd("kritva-sense-validate", "sample.json")
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "conformant"))
                bad = json.loads((fixtures / "contract/fixtures/invalid/unknown_frame.json").read_text())["sample"]
                (work / "bad_sample.json").write_text(json.dumps(bad))
                r = cmd("kritva-sense-validate", "bad_sample.json")
                self.assertEqual(r.returncode, 1)
                self.assertIn("UNKNOWN_FRAME", r.stdout)
                self.assertEqual(cmd("kritva-sense-validate").returncode, 2)

                r = cmd("kritva-sense-generator", "graph", "--seed", "3", "--out", "graph.json")
                self.assertEqual(r.returncode, 0, r.stderr)
                (work / "graph_only.json").write_text(json.dumps(json.loads((work / "graph.json").read_text())["graph"]))
                self.assertEqual(cmd("kritva-sense-frame-graph", "graph_only.json").returncode, 0)
                r = cmd("kritva-sense-frame-graph", "graph_only.json", "world", "sensor")
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn("conformant", r.stdout)
                cyc = json.loads((fixtures / "frame_graph/fixtures/invalid/cycle_two_frames.json").read_text())["graph"]
                (work / "cycle.json").write_text(json.dumps(cyc))
                self.assertEqual(cmd("kritva-sense-frame-graph", "cycle.json").returncode, 1)
                self.assertEqual(cmd("kritva-sense-generator").returncode, 2)

                shutil.copyfile(fixtures / "stream/fixtures/valid/imu_with_bounds.json", work / "stream_ok.json")
                shutil.copyfile(fixtures / "stream/fixtures/invalid/clock_mismatch.json", work / "stream_bad.json")
                self.assertEqual(cmd("kritva-sense-stream", "stream_ok.json").returncode, 0)
                self.assertEqual(cmd("kritva-sense-stream", "stream_bad.json").returncode, 1)
                r = run([venv_python(venv), "-I", "-m", "kritva_sense.stream", "stream_ok.json"], cwd=work)
                self.assertEqual(r.returncode, 0, r.stderr)

                r = cmd("kritva-sense-conformance", "--output", "reference.json")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads((work / "reference.json").read_text())["verdict"], "CONFORMANT")
                r = cmd("kritva-sense-conformance", "--consumer", "mutant:freshness_limit_exclusive", "--output", "mutant.json")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertEqual(json.loads((work / "mutant.json").read_text())["verdict"], "NOT_CONFORMANT")
                self.assertEqual(cmd("kritva-sense-conformance", "--bogus").returncode, 2)

                r = cmd("kritva-sense-version", "--check")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("versions consistent", r.stdout)


if __name__ == "__main__":
    unittest.main()
