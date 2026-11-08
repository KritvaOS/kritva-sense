"""Shared collectors of the regression suite (KOS-SENSE-010). Standard library only; synthetic data only.

The golden data under tests/regression/golden are written only by `scripts/regenerate_regression_golden.py`, which uses
the collectors below, and never by a test or by the regression gate. A test compares what a collector returns now with
what the golden file holds.
"""
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
GOLDEN = Path(__file__).resolve().parent / "golden"
GOLDEN_FILES = ("contract_cases.json", "contract_pins.json", "command_lines.json", "conformance.json")
PINNED_BY = ROOT / "tests" / "packaging" / "test_packaging.py"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kritva_sense import conformance as CF  # noqa: E402
from kritva_sense import frame_graph as FG  # noqa: E402
from kritva_sense import validator as V  # noqa: E402


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def env(hashseed="0", extra_path=None):
    e = dict(os.environ)
    paths = [str(SRC)] + ([str(extra_path)] if extra_path else []) + ([e["PYTHONPATH"]] if e.get("PYTHONPATH") else [])
    e["PYTHONPATH"] = os.pathsep.join(paths)
    e["PYTHONHASHSEED"] = str(hashseed)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def run_module(module, args, cwd, hashseed="0", extra_path=None, timeout=120):
    return subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=cwd, env=env(hashseed, extra_path),
                          capture_output=True, text=False, timeout=timeout)


class TempDir:
    def __enter__(self):
        self._t = tempfile.TemporaryDirectory(prefix="kritva-reg-")
        return Path(self._t.name)

    def __exit__(self, *exc):
        self._t.cleanup()


def pins():
    """The SHA-256 pin table of KOS-SENSE-007, read from its source so that there is one table, not two."""
    tree = ast.parse(PINNED_BY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PINS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("the PINS table was not found in tests/packaging/test_packaging.py")


# ---- contract cases ----------------------------------------------------------------------------------------

def _fixture_files(group):
    return sorted((ROOT / "tests" / group / "fixtures").glob("*/*.json"))


def collect_contract_cases():
    """For every fixture file of the Sense and frame graph tests: the sorted [code, path] violations now reported.
    An empty list is a conformant document. The stream fixtures have hand-written expectations in
    tests/stream/fixtures/expected.json, which are not regenerated."""
    out = {"sense": {}, "frame_graph": {}}
    for key, group, field, check in (("sense", "contract", "sample", V.validate_sample),
                                     ("frame_graph", "frame_graph", "graph", FG.validate_graph)):
        for p in _fixture_files(group):
            doc = json.loads(p.read_text(encoding="utf-8"))[field]     # a fixture wraps the document in a description
            out[key][str(p.relative_to(ROOT))] = sorted([v.code, v.path] for v in check(doc))
    return out


# ---- command lines -----------------------------------------------------------------------------------------

GRAPH = {"contract_version": "0.1.0", "transforms": [
    {"parent": "world", "child": "base", "translation": {"x": 1.0, "y": 0.0, "z": 0.0}, "translation_unit": "m",
     "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}},
    {"parent": "base", "child": "sensor", "translation": {"x": 0.0, "y": 2.0, "z": 0.0}, "translation_unit": "m",
     "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}}]}


def repo(path, field=None):
    """An input file copied from the repository; `field` names the member of a fixture that holds the document."""
    return {"repo": path, "field": field}


def text(value):
    return {"text": value}


SAMPLES = ["samples", "--kind", "range", "--sensor-id", "range_front", "--count", "4", "--seed", "20260109",
           "--start-ns", "1000000000"]
V_OK = "tests/contract/fixtures/valid/imu_valid.json"
V_BAD = "tests/contract/fixtures/invalid/unknown_frame.json"
FG_OK = "tests/frame_graph/fixtures/valid/single_edge.json"
FG_BAD = "tests/frame_graph/fixtures/invalid/cycle_two_frames.json"
ST_OK = "tests/stream/fixtures/valid/worked_example.json"
ST_BAD = "tests/stream/fixtures/invalid/worked_example_gap.json"

# id, family (the regression case that owns it), module, arguments, input files, output files
COMMAND_CASES = [
    ("validate.conformant", "validate", "kritva_sense", ["s.json"], {"s.json": repo(V_OK, "sample")}, []),
    ("validate.not_conformant", "validate", "kritva_sense", ["s.json"], {"s.json": repo(V_BAD, "sample")}, []),
    ("validate.no_argument", "validate", "kritva_sense", [], {}, []),
    ("validate.two_arguments", "validate", "kritva_sense", ["a.json", "b.json"], {}, []),
    ("validate.missing_file", "validate", "kritva_sense", ["missing.json"], {}, []),
    ("validate.not_json", "validate", "kritva_sense", ["s.json"], {"s.json": text("not json")}, []),
    ("frame_graph.conformant", "frame_graph", "kritva_sense.frame_graph", ["g.json"], {"g.json": repo(FG_OK, "graph")}, []),
    ("frame_graph.not_conformant", "frame_graph", "kritva_sense.frame_graph", ["g.json"], {"g.json": repo(FG_BAD, "graph")}, []),
    ("frame_graph.resolve", "frame_graph", "kritva_sense.frame_graph", ["g.json", "world", "sensor"],
     {"g.json": text(json.dumps(GRAPH))}, []),
    ("frame_graph.resolve_unknown_frame", "frame_graph", "kritva_sense.frame_graph", ["g.json", "world", "nope"],
     {"g.json": text(json.dumps(GRAPH))}, []),
    ("frame_graph.no_argument", "frame_graph", "kritva_sense.frame_graph", [], {}, []),
    ("frame_graph.three_arguments", "frame_graph", "kritva_sense.frame_graph", ["g.json", "world", "sensor", "x"], {}, []),
    ("frame_graph.missing_file", "frame_graph", "kritva_sense.frame_graph", ["missing.json"], {}, []),
    ("stream.conformant", "stream", "kritva_sense.stream", ["s.json"], {"s.json": repo(ST_OK)}, []),
    ("stream.not_conformant", "stream", "kritva_sense.stream", ["s.json"], {"s.json": repo(ST_BAD)}, []),
    ("stream.no_argument", "stream", "kritva_sense.stream", [], {}, []),
    ("stream.missing_file", "stream", "kritva_sense.stream", ["missing.json"], {}, []),
    ("stream.not_json", "stream", "kritva_sense.stream", ["s.json"], {"s.json": text("{")}, []),
    ("generator.samples", "generator", "kritva_sense.generator", SAMPLES, {}, []),
    ("generator.samples_with_fault", "generator", "kritva_sense.generator",
     SAMPLES + ["--fault", "2:bad_unit", "--fault", "3:gap"], {}, []),
    ("generator.samples_utc_clock_world_frame", "generator", "kritva_sense.generator",
     ["samples", "--kind", "imu", "--sensor-id", "imu_main", "--count", "2", "--seed", "7", "--clock", "utc",
      "--frame", "world", "--start-sequence", "5", "--step-ns", "20000000"], {}, []),
    ("generator.samples_to_file", "generator", "kritva_sense.generator", SAMPLES + ["--out", "out.json"], {}, ["out.json"]),
    ("generator.graph", "generator", "kritva_sense.generator", ["graph", "--seed", "20260109", "--extra-frames", "2"], {}, []),
    ("generator.graph_with_defect", "generator", "kritva_sense.generator",
     ["graph", "--seed", "20260109", "--defect", "cycle"], {}, []),
    ("generator.no_command", "generator", "kritva_sense.generator", [], {}, []),
    ("generator.unknown_kind", "generator", "kritva_sense.generator",
     ["samples", "--kind", "lidar", "--sensor-id", "x", "--count", "1", "--seed", "1"], {}, []),
    ("generator.bad_fault", "generator", "kritva_sense.generator", SAMPLES + ["--fault", "nonsense"], {}, []),
    ("generator.negative_count", "generator", "kritva_sense.generator",
     ["samples", "--kind", "range", "--sensor-id", "x", "--count", "-1", "--seed", "1"], {}, []),
    ("conformance.list_cases", "conformance", "kritva_sense.conformance", ["--list-cases"], {}, []),
    ("conformance.reference", "conformance", "kritva_sense.conformance", ["--output", "result.json"], {}, ["result.json"]),
    ("conformance.mutant", "conformance", "kritva_sense.conformance",
     ["--consumer", "mutant:sequence_gap_rejected", "--output", "result.json"], {}, ["result.json"]),
    ("conformance.unknown_argument", "conformance", "kritva_sense.conformance", ["--bogus"], {}, []),
    ("conformance.bad_seed", "conformance", "kritva_sense.conformance", ["--seed", "x"], {}, []),
    ("conformance.list_cases_with_output", "conformance", "kritva_sense.conformance",
     ["--list-cases", "--output", "x.json"], {}, []),
    ("conformance.unknown_mutant", "conformance", "kritva_sense.conformance", ["--consumer", "mutant:nope"], {}, []),
    ("version.print", "version", "kritva_sense.version", [], {}, []),
    ("version.check", "version", "kritva_sense.version", ["--check"], {}, []),
    ("version.bad_option", "version", "kritva_sense.version", ["--bad"], {}, []),
]
FAMILIES = ("validate", "frame_graph", "stream", "generator", "conformance", "version")
# The version command also reports whether the package is installed in the environment; that depends on where the
# suite runs, not on the software, so it is left out of the comparison.
ENVIRONMENT_KEYS = ("installed_metadata_version",)


def _normalise(case_id, data):
    if case_id.startswith("version.") and data.startswith(b"{"):
        head, sep, tail = data.partition(b"\n}\n")
        doc = json.loads(head + b"\n}")
        for k in ENVIRONMENT_KEYS:
            doc.pop(k, None)
        return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode() + tail
    return data


def first_line(stderr):
    """The first line of standard error. argparse wraps its usage line at different places in different Python
    versions, so a usage line is cut after `[-h]`, the part every supported version prints the same way."""
    line = stderr.splitlines()[0] if stderr.strip() else ""
    if line.startswith("usage:") and " [-h]" in line:
        line = line[:line.index(" [-h]") + len(" [-h]")]
    return line


def run_case(case, hashseed="0"):
    """Run one command line case in a fresh temporary directory; returns the observable record."""
    case_id, _, module, args, inputs, outputs = case
    with TempDir() as d:
        for name, source in inputs.items():
            if "repo" in source:
                data = (ROOT / source["repo"]).read_bytes()
                if source["field"]:
                    data = json.dumps(json.loads(data)[source["field"]], sort_keys=True).encode()
            else:
                data = source["text"].encode()
            (d / name).write_bytes(data)
        r = run_module(module, args, d, hashseed)
        stdout = _normalise(case_id, r.stdout)
        stderr = r.stderr.decode("utf-8", "replace")
        rec = {"exit": r.returncode, "stdout_sha256": sha256_bytes(stdout), "stdout_bytes": len(stdout),
               "stderr_first_line": first_line(stderr),
               "traceback": "Traceback" in stderr}
        if len(stdout) <= 600:
            rec["stdout"] = stdout.decode("utf-8", "replace")
        if outputs:
            rec["files"] = {name: sha256_bytes((d / name).read_bytes()) for name in outputs if (d / name).is_file()}
        return rec


def collect_command_lines(family=None, hashseed="0"):
    return {c[0]: run_case(c, hashseed) for c in COMMAND_CASES if family in (None, c[1])}


# ---- conformance harness -----------------------------------------------------------------------------------

def collect_conformance():
    """The verdict of the reference consumer and of every shipped mutant, and the byte hash of the reference result."""
    out = {"seed": CF.DEFAULT_SEED, "harness_version": CF.HARNESS_VERSION, "mutants": {}}
    with TempDir() as d:
        r = run_module("kritva_sense.conformance", ["--list-cases"], d)
        out["case_ids"] = [line.split("\t")[0] for line in r.stdout.decode().splitlines()]
        r = run_module("kritva_sense.conformance", ["--output", "ref.json"], d)
        data = (d / "ref.json").read_bytes()
        doc = json.loads(data)
        out["reference"] = {"exit": r.returncode, "verdict": doc["verdict"], "passed": doc["consumers"][0]["passed"],
                            "failed": doc["consumers"][0]["failed"], "result_sha256": sha256_bytes(data)}
        for name in sorted(CF.MUTANTS):
            r = run_module("kritva_sense.conformance", ["--consumer", "mutant:" + name, "--output", "m.json"], d)
            doc = json.loads((d / "m.json").read_bytes())
            consumer = doc["consumers"][0]
            out["mutants"][name] = {"exit": r.returncode, "verdict": consumer["verdict"],
                                    "failed_cases": sorted(x["id"] for x in consumer["results"] if x["outcome"] != "PASS")}
    return out


def load_golden(name):
    return json.loads((GOLDEN / name).read_text(encoding="utf-8"))


def dumps_golden(doc):
    return json.dumps(doc, sort_keys=True, indent=2) + "\n"
