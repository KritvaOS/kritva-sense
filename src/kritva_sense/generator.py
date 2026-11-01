"""Deterministic synthetic data generator for the Sense contracts (KOS-SENSE-004).

It produces reproducible synthetic samples (Sense data contract 0.1.0) and frame graphs (frame graph
contract 0.1.0) from a seed. It implements neither contract and changes neither: every generated item is
checked with the reference validators. Standard library only. Software behaviour on synthetic data only:
generated values are plausible in form, not physically meaningful, and model no real sensor.

Determinism: the pseudo-random generator is SplitMix64 (implemented below), not Python's `random`
module, so the same seed gives byte-identical output across runs and processes on platforms with IEEE 754 double
arithmetic (only exactly rounded operations are used, no libm function). Floats are
rounded to a fixed number of decimals before they enter a document.

    python3 -m kritva_sense.generator samples --kind imu --sensor-id imu.base --count 5 --seed 7
    python3 -m kritva_sense.generator graph --seed 7 --extra-frames 2 [--defect cycle]
Exit 0 on success, 2 on a usage or write error. The format is documented in GENERATOR.md.
"""
import argparse
import json
import math
import sys

from . import frame_graph as fg
from . import validator as V

GENERATOR_VERSION = "0.1.0"
MAX_COUNT = 1_000_000  # largest sample count one call or command line accepts (KOS-SENSE-008, finding F-003)
MASK64 = (1 << 64) - 1
VALUE_DECIMALS = 6
ROTATION_DECIMALS = 12

# Defects of a sample sequence. Each maps to the code the generator expects, or None when the contract
# defines no error (a sequence gap is conformant: the contract only requires strictly increasing).
SAMPLE_FAULTS = {
    "stale": "STALE_DATA",            # validity STALE (conformant sample, not usable)
    "missing": "MISSING_DATA",        # validity MISSING, empty measurements
    "invalid": "INVALID_DATA",        # validity INVALID
    "regression": "SEQUENCE_REGRESSION",  # sequence repeats the previous one; later samples continue as if it had not
    "gap": None,                      # sequence jumps ahead and later samples continue from it; conformant by contract
    "boundary": None,                 # extreme but valid numbers; last sample only; conformant by contract
    "bad_unit": "INVALID_UNIT",
    "unknown_frame": "UNKNOWN_FRAME",
    "missing_measurement": "MISSING_FIELD",
    "bad_timestamp": "INVALID_TIMESTAMP",
    "bad_version": "UNSUPPORTED_CONTRACT_VERSION",
}
GRAPH_DEFECTS = {
    "cycle": "FG_CYCLE",
    "duplicate_edge": "FG_DUPLICATE_EDGE",
    "multiple_parents": "FG_MULTIPLE_PARENTS",
    "not_unit_quaternion": "FG_NOT_UNIT_QUATERNION",
}
MAX_BOUNDARY_TS = (1 << 63) - 1
MAX_BOUNDARY_SEQ = (1 << 53)


class SplitMix64:
    """SplitMix64 (Steele, Lea, Flood). State is one 64-bit integer; all arithmetic is on integers."""

    def __init__(self, seed):
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed > MASK64:
            raise ValueError("seed must be an integer from 0 to 2**64 - 1")
        self.state = seed

    def next_u64(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def random(self):
        """A float in [0, 1) with 53 random bits."""
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def uniform(self, lo, hi):
        return lo + (hi - lo) * self.random()


def _r(x, decimals=VALUE_DECIMALS):
    x = round(x, decimals)
    return 0.0 if x == 0 else x  # no negative zero


def _measurements(kind, rng):
    spec = V.KINDS[kind]
    out = {}
    for name in spec:  # dict order of the validator's table: fixed, so the draw order is fixed
        if name == "accel_z":
            v = 9.81 + rng.uniform(-0.2, 0.2)
        elif name.startswith("accel"):
            v = rng.uniform(-2.0, 2.0)
        elif name.startswith("gyro"):
            v = rng.uniform(-1.0, 1.0)
        elif name == "distance":
            v = rng.uniform(0.05, 10.0)
        elif name == "position":
            v = rng.uniform(-3.14159, 3.14159)
        else:  # temperature
            v = rng.uniform(273.15, 323.15)
        out[name] = {"value": _r(v), "unit": spec[name]}
    return out


def _check_config(kind, sensor_id, clock, frame):
    if kind not in V.KINDS:
        raise ValueError("unknown kind %r (one of %s)" % (kind, ", ".join(V.KINDS)))
    if not isinstance(sensor_id, str) or not V.SENSOR_ID_RE.match(sensor_id):
        raise ValueError("sensor_id %r does not match the contract pattern" % (sensor_id,))
    if clock not in V.CLOCKS:
        raise ValueError("clock %r is not one of %s" % (clock, ", ".join(V.CLOCKS)))
    if frame not in V.FRAMES:
        raise ValueError("frame %r is not one of %s" % (frame, ", ".join(V.FRAMES)))


def make_sample(kind, sensor_id, sequence, timestamp_ns, rng, clock="monotonic", frame="sensor", validity="VALID"):
    """One sample object. VALID by default; STALE, MISSING and INVALID carry the error_code the contract requires."""
    _check_config(kind, sensor_id, clock, frame)
    s = {
        "contract_version": V.CONTRACT_VERSION,
        "sensor_id": sensor_id,
        "kind": kind,
        "sequence": sequence,
        "timestamp": {"clock": clock, "unit": V.TIMESTAMP_UNIT, "value": timestamp_ns},
        "frame_id": frame,
        "validity": validity,
        "measurements": {} if validity == "MISSING" else _measurements(kind, rng),
    }
    if validity != "VALID":
        s["error_code"] = {"STALE": "STALE_DATA", "MISSING": "MISSING_DATA", "INVALID": "INVALID_DATA"}[validity]
    return s


def _apply_fault(sample, fault, previous):
    """Return the sample with the fault applied. previous is the preceding sample of the sequence, or None."""
    s = json.loads(json.dumps(sample))
    if fault == "stale":
        s["validity"], s["error_code"] = "STALE", "STALE_DATA"
    elif fault == "missing":
        s["validity"], s["error_code"], s["measurements"] = "MISSING", "MISSING_DATA", {}
    elif fault == "invalid":
        s["validity"], s["error_code"] = "INVALID", "INVALID_DATA"
    elif fault == "regression":
        if previous is None:
            raise ValueError("a regression needs a preceding sample (index must be at least 1)")
        s["sequence"] = previous["sequence"]
    elif fault == "gap":
        s["sequence"] += 5
    elif fault == "boundary":
        s["sequence"] = MAX_BOUNDARY_SEQ
        s["timestamp"]["value"] = MAX_BOUNDARY_TS
        for m in s["measurements"].values():
            m["value"] = 1e300
    elif fault == "bad_unit":
        name = sorted(s["measurements"])[0]
        s["measurements"][name]["unit"] = "furlong"
    elif fault == "unknown_frame":
        s["frame_id"] = "map"
    elif fault == "missing_measurement":
        del s["measurements"][sorted(s["measurements"])[0]]
    elif fault == "bad_timestamp":
        s["timestamp"]["value"] = -1
    elif fault == "bad_version":
        s["contract_version"] = "9.9.9"
    else:
        raise ValueError("unknown fault %r (one of %s)" % (fault, ", ".join(sorted(SAMPLE_FAULTS))))
    return s


def generate_samples(kind, sensor_id, count, seed, start_sequence=0, start_ns=0, step_ns=10_000_000,
                     clock="monotonic", frame="sensor", faults=None):
    """A document {generator_version, seed, samples, expectations}.

    faults maps a sample index to a fault name (SAMPLE_FAULTS). Nothing is faulty unless asked for.
    expectations has one entry per faulty sample: index, fault, expected_code (None when the contract
    defines no error for it).
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be an integer >= 0")
    if count > MAX_COUNT:
        raise ValueError("count must be at most %d" % MAX_COUNT)
    if isinstance(step_ns, bool) or not isinstance(step_ns, int) or step_ns <= 0:
        raise ValueError("step_ns must be an integer > 0")
    if isinstance(start_sequence, bool) or not isinstance(start_sequence, int) or start_sequence < 0:
        raise ValueError("start_sequence must be an integer >= 0")
    if isinstance(start_ns, bool) or not isinstance(start_ns, int) or start_ns < 0:
        raise ValueError("start_ns must be an integer >= 0")
    _check_config(kind, sensor_id, clock, frame)
    faults = dict(faults or {})
    for idx, name in faults.items():
        if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx < count:
            raise ValueError("fault index %r is outside 0..%d" % (idx, count - 1))
        if name not in SAMPLE_FAULTS:
            raise ValueError("unknown fault %r (one of %s)" % (name, ", ".join(sorted(SAMPLE_FAULTS))))
    for idx, name in faults.items():
        if name == "boundary" and idx != count - 1:
            raise ValueError("a boundary fault is only allowed on the last sample (index %d)" % (count - 1))
    rng = SplitMix64(seed)
    samples, expectations, previous = [], [], None
    next_seq = start_sequence
    for i in range(count):
        s = make_sample(kind, sensor_id, next_seq, start_ns + i * step_ns, rng, clock, frame)
        if i in faults:
            s = _apply_fault(s, faults[i], previous)
            expectations.append({"index": i, "fault": faults[i], "expected_code": SAMPLE_FAULTS[faults[i]]})
        samples.append(s)
        # the sequence continues from the sample as emitted, except after a regression, which does not move it back
        next_seq = next_seq + 1 if faults.get(i) == "regression" else s["sequence"] + 1
        previous = s
    return {"generator_version": GENERATOR_VERSION, "seed": seed, "samples": samples, "expectations": expectations}


VALIDITY_CODES = ("STALE_DATA", "MISSING_DATA", "INVALID_DATA")


def check_samples(doc):
    """Verify a generated sample document with the reference validators. Returns a list of mismatch strings;
    [] means that, compared as complete lists of codes (duplicates count), every sample has exactly the structural
    violations its fault states (none for a clean sample, a conformant gap or boundary, or a validity state), every
    adjacent pair has a sequence violation only where a regression was requested, and every validity state is
    reported as not usable with its code."""
    problems = []
    samples, by_index = doc["samples"], {e["index"]: e for e in doc["expectations"]}
    for i, s in enumerate(samples):
        exp = by_index.get(i)
        code = exp["expected_code"] if exp else None
        label = "sample %d%s" % (i, " (%s)" % exp["fault"] if exp else "")
        structural = sorted(v.code for v in V.validate_sample(s))
        want = [code] if code is not None and code not in VALIDITY_CODES and code != "SEQUENCE_REGRESSION" else []
        if structural != want:
            problems.append("%s: expected structural codes %s, got %s" % (label, want, structural))
        if i > 0:
            seq = sorted(v.code for v in V.check_sequence(samples[i - 1], s))
            want_seq = ["SEQUENCE_REGRESSION"] if code == "SEQUENCE_REGRESSION" else []
            if seq != want_seq:
                problems.append("%s: expected sequence codes %s, got %s" % (label, want_seq, seq))
        if code in VALIDITY_CODES and not structural:
            usable, v = V.usability(s, s["timestamp"]["value"], s["timestamp"]["clock"], 1)
            got = sorted(x.code for x in v)
            if usable or got != [code]:
                problems.append("%s: expected not usable with %s, got usable=%s %s" % (label, code, usable, got))
    return problems


def _rotation(rng):
    """A unit quaternion {w, x, y, z}: four uniform draws, normalized (only +, *, / and sqrt, which are exactly
    rounded by IEEE 754, so no libm function enters the result), w not negative, rounded so |norm - 1| stays far
    below 1e-9."""
    while True:
        q = [rng.uniform(-1.0, 1.0) for _ in range(4)]
        n = math.sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3])
        if n > 0.1:
            break
    q = [c / n for c in q]
    if q[0] < 0:
        q = [-c for c in q]
    return dict(zip("wxyz", [_r(c, ROTATION_DECIMALS) for c in q]))


def make_edge(parent, child, rng):
    t = [_r(rng.uniform(-5.0, 5.0)) for _ in range(3)]
    return {"parent": parent, "child": child, "translation": dict(zip("xyz", t)), "translation_unit": "m",
            "rotation": _rotation(rng)}


def generate_graph(seed, extra_frames=0, defect=None):
    """A document {generator_version, seed, graph, expectation}: the chain world -> base -> sensor followed by
    `extra_frames` graph-local frames (link_1, link_2, ...), each the child of the one before. With a defect
    the graph has exactly that defect and expectation.codes names the code the validator must report."""
    if isinstance(extra_frames, bool) or not isinstance(extra_frames, int) or not 0 <= extra_frames <= 100:
        raise ValueError("extra_frames must be an integer from 0 to 100")
    if defect is not None and defect not in GRAPH_DEFECTS:
        raise ValueError("unknown defect %r (one of %s)" % (defect, ", ".join(sorted(GRAPH_DEFECTS))))
    rng = SplitMix64(seed)
    names = ["world", "base", "sensor"] + ["link_%d" % i for i in range(1, extra_frames + 1)]
    edges = [make_edge(names[i], names[i + 1], rng) for i in range(len(names) - 1)]
    if defect == "cycle":
        edges.append(make_edge("sensor", "world", rng))
    elif defect == "duplicate_edge":
        edges.append(json.loads(json.dumps(edges[0])))
    elif defect == "multiple_parents":
        edges.append(make_edge("world", "sensor", rng))
    elif defect == "not_unit_quaternion":
        edges[0]["rotation"] = {k: _r(v * 1.5, ROTATION_DECIMALS) for k, v in edges[0]["rotation"].items()}
    doc = {"contract_version": fg.FRAME_GRAPH_VERSION, "transforms": edges}
    exp = {"defect": defect, "codes": [GRAPH_DEFECTS[defect]] if defect else []}
    return {"generator_version": GENERATOR_VERSION, "seed": seed, "graph": doc, "expectation": exp}


def check_graph(doc):
    """Verify a generated graph document: it must give exactly the expected codes; a conformant graph must
    also resolve from its first to its last frame."""
    g, exp = doc["graph"], doc["expectation"]
    got = sorted(v.code for v in fg.validate_graph(g))
    problems = []
    if got != sorted(exp["codes"]):
        problems.append("graph: expected codes %s, got %s" % (sorted(exp["codes"]), got))
    if not exp["codes"] and g["transforms"]:
        first, last = g["transforms"][0]["parent"], g["transforms"][-1]["child"]
        tf, viol = fg.resolve(g, first, last)
        if tf is None or viol:
            problems.append("graph: %s -> %s did not resolve" % (first, last))
    return problems


def dumps(doc):
    """The one output format: sorted keys, two-space indent, trailing newline, no NaN or infinity."""
    return json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _parse_fault(text):
    idx, sep, name = text.partition(":")
    if not sep or not idx.isdigit() or name not in SAMPLE_FAULTS:
        raise argparse.ArgumentTypeError("fault must be INDEX:NAME with NAME one of %s" % ", ".join(sorted(SAMPLE_FAULTS)))
    return int(idx), name


def _nonneg(text):
    if not text.isdigit():
        raise argparse.ArgumentTypeError("must be an integer >= 0")
    return int(text)


def _build_parser():
    p = argparse.ArgumentParser(prog="python3 -m kritva_sense.generator",
                                description="Deterministic synthetic Sense samples and frame graphs (synthetic data only).")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("samples", help="generate a sample sequence")
    s.add_argument("--kind", required=True, choices=sorted(V.KINDS))
    s.add_argument("--sensor-id", required=True)
    s.add_argument("--count", required=True, type=_nonneg)
    s.add_argument("--seed", required=True, type=_nonneg)
    s.add_argument("--start-sequence", type=_nonneg, default=0)
    s.add_argument("--start-ns", type=_nonneg, default=0)
    s.add_argument("--step-ns", type=_nonneg, default=10_000_000)
    s.add_argument("--clock", choices=V.CLOCKS, default="monotonic")
    s.add_argument("--frame", choices=V.FRAMES, default="sensor")
    s.add_argument("--fault", action="append", type=_parse_fault, default=[], metavar="INDEX:NAME")
    s.add_argument("--out", help="write to this file instead of standard output")
    g = sub.add_parser("graph", help="generate a frame graph")
    g.add_argument("--seed", required=True, type=_nonneg)
    g.add_argument("--extra-frames", type=_nonneg, default=0)
    g.add_argument("--defect", choices=sorted(GRAPH_DEFECTS))
    g.add_argument("--out", help="write to this file instead of standard output")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)  # argparse exits with 2 on a usage error
    try:
        if args.command == "samples":
            idxs = [i for i, _ in args.fault]
            if len(idxs) != len(set(idxs)):
                raise ValueError("a sample index may carry one fault only (repeated --fault index)")
            doc = generate_samples(args.kind, args.sensor_id, args.count, args.seed, args.start_sequence, args.start_ns,
                                   args.step_ns, args.clock, args.frame, dict(args.fault))
            problems = check_samples(doc)
        else:
            doc = generate_graph(args.seed, args.extra_frames, args.defect)
            problems = check_graph(doc)
    except ValueError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    if problems:
        print("error: generated data failed the reference validators: %s" % "; ".join(problems), file=sys.stderr)
        return 2
    text = dumps(doc)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            print("error: cannot write %s: %s" % (args.out, e), file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
