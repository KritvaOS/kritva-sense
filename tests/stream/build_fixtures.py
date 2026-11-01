"""Builds the KOS-SENSE-005 stream fixtures (synthetic data only) and their hand-written expectations.

    python3 tests/stream/build_fixtures.py          rewrite tests/stream/fixtures/
The unit tests compare the committed files with this builder's output, so the fixtures are reproducible. The
expectations below are written by hand from the stream contract; they are never produced by the checker.
Samples are made with the KOS-SENSE-004 generator (fixed seeds); stream records are assembled here.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kritva_sense import generator as G  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
SENSOR = "imu.main"


def samples(n=5, kind="imu", sensor=SENSOR, start=100, seed=7, clock="monotonic", faults=None, start_ns=1_000_000_000):
    return G.generate_samples(kind, sensor, n, seed, start_sequence=start, start_ns=start_ns, clock=clock,
                              faults=faults)["samples"]


def opened(kind="imu", sensor=SENSOR, clock="monotonic", first=None, stream_id="stream_one"):
    r = {"record": "open", "index": 0, "stream_id": stream_id, "sensor_id": sensor, "kind": kind, "clock": clock}
    if first is not None:
        r["first_sequence"] = first
    return r


def closed(last=None):
    r = {"record": "close", "index": 0}
    if last is not None:
        r["last_sequence"] = last
    return r


def smp(sample):
    return {"record": "sample", "index": 0, "sample": copy.deepcopy(sample)}


def doc(records, version="0.1.0"):
    recs = copy.deepcopy(records)
    for i, r in enumerate(recs):
        if isinstance(r, dict) and r.get("index") == 0:
            r["index"] = i
    return {"stream_version": version, "records": recs}


def full(ss, first=None, last=None, **kw):
    return doc([opened(first=first, **kw)] + [smp(s) for s in ss] + [closed(last)])


def E(*pairs):
    return [list(p) for p in pairs]


VALID = {}
INVALID = {}   # name -> (document, expected stream [(position, code)], expected sample violations [(position, code)])


def valid(name, document):
    VALID[name] = document


def invalid(name, document, stream, sample=()):
    INVALID[name] = (document, E(*stream), E(*sample))


def build():
    s5 = samples(5)
    # ---- valid ------------------------------------------------------------------------------------------------
    valid("worked_example", full(samples(3), first=100, last=102))
    valid("open_close_no_samples", doc([opened(), closed()]))
    valid("imu_with_bounds", full(s5, first=100, last=104))
    valid("imu_without_bounds", full(s5))
    valid("range_utc", full(samples(4, "range", "range.front", 0, 11, "utc", start_ns=1_700_000_000_000_000_000),
                            kind="range", sensor="range.front", clock="utc"))
    valid("encoder_monotonic", full(samples(4, "encoder", "enc.left", 5, 12), kind="encoder", sensor="enc.left"))
    valid("temperature_monotonic", full(samples(3, "temperature", "temp.board", 0, 13), kind="temperature",
                                        sensor="temp.board"))
    valid("validity_states_are_conformant",
          full(samples(5, faults={1: "stale", 2: "missing", 3: "invalid"}), first=100, last=104))
    valid("equal_timestamps", full([dict(s, timestamp=dict(s["timestamp"], value=1_000_000_000)) for s in s5]))
    # ---- invalid: document and records --------------------------------------------------------------------------
    invalid("empty_stream", doc([]), [(-1, "STREAM_OPEN_MISSING")])
    invalid("document_not_object", [1, 2], [(-1, "STREAM_MALFORMED")])
    invalid("missing_version", {"records": full(s5)["records"]}, [(-1, "STREAM_MISSING_FIELD")])
    invalid("missing_records", {"stream_version": "0.1.0"}, [(-1, "STREAM_MISSING_FIELD")])
    invalid("records_not_array", {"stream_version": "0.1.0", "records": {}}, [(-1, "STREAM_MALFORMED")])
    invalid("version_not_string", dict(full(s5), stream_version=1), [(-1, "STREAM_MALFORMED")])
    invalid("unsupported_version", dict(full(s5), stream_version="9.9.9"), [(-1, "STREAM_UNSUPPORTED_VERSION")])
    d = full(s5)
    d["extra"] = 1
    invalid("unknown_document_field", d, [(-1, "STREAM_UNKNOWN_FIELD")])
    d = full(s5)
    d["records"][2]["extra"] = True
    invalid("unknown_record_field", d, [(2, "STREAM_UNKNOWN_FIELD")])
    d = full(s5)
    d["records"][2]["record"] = "heartbeat"
    invalid("unknown_record_kind", d, [(2, "STREAM_UNKNOWN_RECORD"), (3, "STREAM_SEQUENCE_GAP")])   # an unknown record is not read, so the hole shows
    d = full(s5)
    del d["records"][2]["record"]
    invalid("record_kind_missing", d, [(2, "STREAM_MISSING_FIELD"), (3, "STREAM_SEQUENCE_GAP")])
    d = full(s5)
    d["records"][2] = "not a record"
    invalid("record_not_object", d, [(2, "STREAM_MALFORMED"), (3, "STREAM_SEQUENCE_GAP")])
    d = full(s5)
    del d["records"][0]["sensor_id"], d["records"][0]["clock"]
    invalid("open_missing_fields", d, [(0, "STREAM_MISSING_FIELD"), (0, "STREAM_MISSING_FIELD")])
    d = full(s5)
    d["records"][0].update(sensor_id="Bad Sensor", kind="lidar", clock="gps", stream_id=5, first_sequence=-1)
    invalid("open_malformed_fields", d, [(0, "STREAM_MALFORMED")] * 5)
    d = full(s5)
    d["records"][-1]["last_sequence"] = "last"
    invalid("close_last_sequence_malformed", d, [(6, "STREAM_MALFORMED")])
    d = full(s5)
    d["records"][2]["sample"] = [1]
    invalid("sample_not_object", d, [(2, "STREAM_MALFORMED"), (3, "STREAM_SEQUENCE_GAP")])
    d = full(s5)
    del d["records"][2]["sample"]
    invalid("sample_missing", d, [(2, "STREAM_MISSING_FIELD"), (3, "STREAM_SEQUENCE_GAP")])   # the next sample follows a hole
    d = full(s5)
    d["records"][3]["index"] = 9
    invalid("index_mismatch", d, [(3, "STREAM_INDEX_MISMATCH")])
    d = full(s5)
    d["records"][3]["index"] = "three"
    invalid("index_malformed", d, [(3, "STREAM_MALFORMED")])
    d = full(s5)
    del d["records"][3]["index"]
    invalid("index_missing", d, [(3, "STREAM_MISSING_FIELD")])
    d = full(s5)
    d["records"][3]["index"] = 2          # a duplicated index (the record before has index 2)
    invalid("index_duplicated", d, [(3, "STREAM_INDEX_MISMATCH")])
    # ---- invalid: lifecycle -----------------------------------------------------------------------------------------
    s3 = samples(3)
    invalid("open_missing", doc([smp(s) for s in s3] + [closed()]),
            [(-1, "STREAM_OPEN_MISSING"), (0, "STREAM_SAMPLE_BEFORE_OPEN"), (1, "STREAM_SAMPLE_BEFORE_OPEN"),
             (2, "STREAM_SAMPLE_BEFORE_OPEN"), (3, "STREAM_CLOSE_BEFORE_OPEN")])
    invalid("open_not_first", doc([smp(s3[0]), opened()] + [smp(s) for s in s3[1:]] + [closed()]),
            [(0, "STREAM_SAMPLE_BEFORE_OPEN"), (1, "STREAM_OPEN_NOT_FIRST")])
    invalid("open_repeated", doc([opened()] + [smp(s3[0]), opened(sensor="other.sensor")] +
                                 [smp(s) for s in s3[1:]] + [closed()]),
            [(2, "STREAM_OPEN_REPEATED")])
    invalid("sample_after_close", doc([opened()] + [smp(s) for s in s3[:2]] + [closed(), smp(s3[2])]),
            [(4, "STREAM_SAMPLE_AFTER_CLOSE")])
    invalid("close_repeated", doc([opened()] + [smp(s) for s in s3] + [closed(), closed()]),
            [(5, "STREAM_CLOSE_REPEATED")])
    invalid("unterminated", doc([opened()] + [smp(s) for s in s3]), [(-1, "STREAM_UNTERMINATED")])
    invalid("open_only", doc([opened()]), [(-1, "STREAM_UNTERMINATED")])
    invalid("lifecycle_combination",
            doc([smp(s3[0]), closed(), opened(), smp(s3[1]), closed(), smp(s3[2]), closed(), opened()]),
            [(0, "STREAM_SAMPLE_BEFORE_OPEN"), (1, "STREAM_CLOSE_BEFORE_OPEN"), (2, "STREAM_OPEN_NOT_FIRST"),
             (5, "STREAM_SAMPLE_AFTER_CLOSE"), (6, "STREAM_CLOSE_REPEATED"), (7, "STREAM_OPEN_REPEATED")])
    # ---- invalid: sequence --------------------------------------------------------------------------------------------
    w = full(samples(3), first=100, last=102)
    del w["records"][2]
    for i, r in enumerate(w["records"]):
        r["index"] = i
    invalid("worked_example_gap", w, [(2, "STREAM_SEQUENCE_GAP")])
    invalid("gap_from_generator", full(samples(6, faults={3: "gap"})), [(4, "STREAM_SEQUENCE_GAP")])
    invalid("duplicate_from_generator", full(samples(6, faults={3: "regression"})),
            [(4, "STREAM_SEQUENCE_DUPLICATE"), (5, "STREAM_SEQUENCE_GAP")])   # the generator continues as if it had not repeated
    ss = copy.deepcopy(s5)
    ss[3]["sequence"] = 90
    ss[4]["sequence"] = 91
    invalid("regression_then_continue", full(ss), [(4, "STREAM_SEQUENCE_REGRESSION")])
    ss = copy.deepcopy(s5)
    ss[2]["sequence"] = 99
    invalid("regression_below_start", full(ss), [(3, "STREAM_SEQUENCE_REGRESSION"), (4, "STREAM_SEQUENCE_GAP")])
    invalid("first_sequence_unmet", full(s5, first=99), [(1, "STREAM_FIRST_SEQUENCE_UNMET")])
    invalid("last_sequence_unmet", full(s5, last=105), [(6, "STREAM_LAST_SEQUENCE_UNMET")])
    invalid("first_unmet_without_samples", doc([opened(first=5), closed()]), [(1, "STREAM_FIRST_SEQUENCE_UNMET")])
    invalid("last_unmet_without_samples", doc([opened(), closed(last=5)]), [(1, "STREAM_LAST_SEQUENCE_UNMET")])
    invalid("first_unmet_unterminated_without_samples", doc([opened(first=5)]),
            [(-1, "STREAM_FIRST_SEQUENCE_UNMET"), (-1, "STREAM_UNTERMINATED")])
    valid("no_first_or_last_inferred", full(samples(3, start=7)))          # no bound, so a late start is conformant
    # ---- invalid: timestamps and identity -------------------------------------------------------------------------------
    ss = copy.deepcopy(s5)
    ss[3]["timestamp"]["value"] = ss[2]["timestamp"]["value"] - 1
    ss[4]["timestamp"]["value"] = ss[3]["timestamp"]["value"] + 1
    invalid("timestamp_regression", full(ss), [(4, "STREAM_TIMESTAMP_REGRESSION")])
    ss = copy.deepcopy(s5)
    ss[2]["timestamp"]["clock"] = "utc"
    invalid("clock_mismatch", full(ss), [(3, "STREAM_CLOCK_MISMATCH")])
    ss = copy.deepcopy(s5)
    ss[2]["sensor_id"] = "imu.other"
    invalid("sensor_change", full(ss), [(3, "STREAM_SENSOR_CHANGE")])
    ss = copy.deepcopy(s5)
    ss[2] = samples(5, "range", SENSOR)[2]
    ss[2]["sequence"] = 102
    invalid("kind_change", full(ss), [(3, "STREAM_KIND_CHANGE")])
    # ---- samples carried unchanged ---------------------------------------------------------------------------------------
    ss = copy.deepcopy(s5)
    ss[2]["measurements"]["accel_x"]["unit"] = "g"
    invalid("sample_violation_only", full(ss), [], [(3, "INVALID_UNIT")])
    ss = copy.deepcopy(s5)
    ss[2]["sequence"] = 102
    ss[3]["sequence"] = 103
    ss[4]["sequence"] = 104
    ss[2]["timestamp"]["clock"] = "utc"
    invalid("conformant_samples_stream_defects", full(ss), [(3, "STREAM_CLOCK_MISMATCH")], [])
    # ---- combinations ---------------------------------------------------------------------------------------------
    ss = copy.deepcopy(s5)
    ss[1]["sequence"] = 103                       # gap
    ss[1]["timestamp"]["clock"] = "utc"           # and a different clock
    ss[1]["measurements"]["accel_y"]["unit"] = "g"  # and a sample violation
    ss[3]["sensor_id"] = "imu.other"
    invalid("defects_in_combination", full(ss, first=100, last=104),
            [(2, "STREAM_CLOCK_MISMATCH"), (2, "STREAM_SEQUENCE_GAP"), (3, "STREAM_SEQUENCE_REGRESSION"),
             (4, "STREAM_SENSOR_CHANGE")],
            [(2, "INVALID_UNIT")])
    # sequences 100, 101 ... then 101 again after a gap check: duplicates and regressions are independent of gaps
    ss = copy.deepcopy(s5)
    ss[1]["sequence"] = 100
    ss[2]["sequence"] = 99
    ss[3]["sequence"] = 105
    ss[4]["sequence"] = 106
    invalid("duplicate_regression_gap_together", full(ss),
            [(2, "STREAM_SEQUENCE_DUPLICATE"), (3, "STREAM_SEQUENCE_REGRESSION"), (4, "STREAM_SEQUENCE_GAP")])


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write():
    build()
    for sub in ("valid", "invalid"):
        (FIX / sub).mkdir(parents=True, exist_ok=True)
        for old in (FIX / sub).glob("*.json"):
            old.unlink()
    for name, d in VALID.items():
        dump(FIX / "valid" / (name + ".json"), d)
    expected = {}
    for name, (d, stream, sample) in INVALID.items():
        dump(FIX / "invalid" / (name + ".json"), d)
        expected[name] = {"stream": stream, "samples": sample}
    dump(FIX / "expected.json", expected)


if __name__ == "__main__":
    write()
    print("%d valid and %d invalid fixtures written" % (len(VALID), len(INVALID)))
