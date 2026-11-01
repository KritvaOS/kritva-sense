"""KOS-SENSE-005 unit tests: telemetry stream contract and reference validator (synthetic data only)."""
import copy
import hashlib
import itertools
import json
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_fixtures as B  # noqa: E402
from kritva_sense import generator as G  # noqa: E402
from kritva_sense import stream as S  # noqa: E402
from kritva_sense import validator as V  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
SAMPLE_SCHEMA_SHA256 = "1f6f0824af55237b0b3e90ddd413ddef8c48e2eb3cd19a7f4244295bd2b9bc6b"
FRAME_SCHEMA_SHA256 = "ae644360dc5ba0e679a9e616022b4261b2e95fe967da8af1e4d440f718a099e2"
# The accepted contract documents and the generator are pinned (AC-507). Any change to them, even wording, is a
# deliberate change: update the pin in the same pull request and record it in planning/CHANGELOG.md.
SENSE_CONTRACT_MD_SHA256 = "f8935feb9efb10dd482e4b7386239295b2180412dbbcbc177aa7a6f86d75abcf"
FRAME_GRAPH_CONTRACT_MD_SHA256 = "a3ded6d06222a7f554127c16265e718f350eef58f0550737be425561c6f10210"
VALIDATOR_PY_SHA256 = "cc758f474c21d1963ebbc3c8629a2f59584ce7f463935064f46e5b98061ccaa6"
GENERATOR_PY_SHA256 = "9c2e2dcbaf0f2e643f0e7dc1ba27ab2585c29852f1f44c038596b52591c07c2a"
FRAME_GRAPH_PY_SHA256 = "4aef1f86a853bf66582b25471f568c421ed41b17f6f7148e5efdb9e5a2e49a6a"


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load(group):
    return [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted((FIX / group).glob("*.json"))]


def pairs(items):
    return sorted([d.position, d.code] for d in items)


def codes(doc):
    r = S.check_stream(doc)
    return [d.code for d in r.stream], [v.code for v in r.samples]


def run(*args):
    return subprocess.run([sys.executable, "-m", "kritva_sense.stream", *args], cwd=ROOT / "src",
                          capture_output=True, text=True)


def good(n=5, first=None, last=None):
    return B.full(B.samples(n), first=first, last=last)


class Representation(unittest.TestCase):  # AC-501
    def test_schema_and_constants_agree(self):
        schema = json.loads((ROOT / "contract" / "stream.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["stream_version"]["const"], S.STREAM_VERSION)
        self.assertEqual(sorted(schema["required"]), sorted(S.DOCUMENT_FIELDS))
        self.assertIs(schema["additionalProperties"], False)
        defs = schema["$defs"]
        for kind, (required, optional) in S.RECORD_FIELDS.items():
            d = defs[kind]
            self.assertEqual(sorted(d["required"]), sorted(required))
            self.assertEqual(sorted(d["properties"]), sorted(required + optional))
            self.assertIs(d["additionalProperties"], False)
            self.assertEqual(d["properties"]["record"]["const"], kind)
        self.assertEqual(sorted(defs["open"]["properties"]["kind"]["enum"]), sorted(V.KINDS))
        self.assertEqual(sorted(defs["open"]["properties"]["clock"]["enum"]), sorted(V.CLOCKS))
        self.assertEqual(defs["identity"]["pattern"], V.SENSOR_ID_RE.pattern)
        self.assertEqual(defs["sample"]["properties"]["sample"]["$ref"], "sense-sample.schema.json")
        self.assertEqual(sorted(S.RECORD_KINDS), ["close", "open", "sample"])

    def test_contract_document_states_version_and_every_code(self):
        doc = (ROOT / "contract" / "STREAM_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("| Version | Stream contract version: %s |" % S.STREAM_VERSION, doc)
        self.assertEqual(len(S.STREAM_ERROR_CODES), len(set(S.STREAM_ERROR_CODES)))
        for code in S.STREAM_ERROR_CODES:
            self.assertTrue(code.startswith("STREAM_"))
            self.assertIn("| `%s` |" % code, doc)
        listed = set(re.findall(r"^\| `(STREAM_[A-Z_]+)` \|", doc, re.M))
        self.assertEqual(listed, set(S.STREAM_ERROR_CODES))
        for needle in ("additional to contract 0.1.0", "never drops, reorders or repairs", "mutually exclusive",
                       "the last missing number", "fixed at `open`"):
            self.assertIn(needle, doc)

    def test_stream_codes_do_not_collide_with_sample_codes(self):
        self.assertFalse(set(S.STREAM_ERROR_CODES) & set(V.ERROR_CODES))

    def test_document_envelope_codes(self):
        self.assertEqual(codes([1]), (["STREAM_MALFORMED"], []))
        self.assertEqual(codes({}), (["STREAM_MISSING_FIELD", "STREAM_MISSING_FIELD"], []))
        d = good()
        d["stream_version"] = "0.2.0"
        self.assertEqual(codes(d), (["STREAM_UNSUPPORTED_VERSION"], []))
        d["stream_version"] = None
        self.assertEqual(codes(d), (["STREAM_MALFORMED"], []))
        d = good()
        d["x"] = 1
        self.assertEqual(codes(d), (["STREAM_UNKNOWN_FIELD"], []))

    def test_optional_bounds_are_validated(self):
        for bad in (-1, 1.5, "1", True, None):
            d = good()
            d["records"][0]["first_sequence"] = bad
            self.assertEqual(codes(d)[0].count("STREAM_MALFORMED"), 1, bad)
            d = good()
            d["records"][-1]["last_sequence"] = bad
            self.assertEqual(codes(d)[0].count("STREAM_MALFORMED"), 1, bad)

    def test_a_malformed_identity_field_skips_only_the_checks_that_need_it(self):
        d = good()
        d["records"][0]["clock"] = "gps"
        self.assertEqual(codes(d), (["STREAM_MALFORMED"], []))     # no clock mismatch guessed
        d["records"][0]["sensor_id"] = "Bad"
        d["records"][2]["sample"]["sensor_id"] = "imu.other"
        c = codes(d)[0]
        self.assertEqual(sorted(c), ["STREAM_MALFORMED", "STREAM_MALFORMED"])  # no sensor change guessed


class Fixtures(unittest.TestCase):  # AC-506 (fixtures) and AC-501 to AC-505
    def test_committed_fixtures_equal_the_builder_output(self):
        B.VALID.clear()
        B.INVALID.clear()
        B.build()
        self.assertEqual(sorted(p.stem for p in (FIX / "valid").glob("*.json")), sorted(B.VALID))
        self.assertEqual(sorted(p.stem for p in (FIX / "invalid").glob("*.json")), sorted(B.INVALID))
        for name, d in B.VALID.items():
            self.assertEqual(json.loads((FIX / "valid" / (name + ".json")).read_text(encoding="utf-8")), d, name)
        expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
        for name, (d, stream, sample) in B.INVALID.items():
            self.assertEqual(json.loads((FIX / "invalid" / (name + ".json")).read_text(encoding="utf-8")), d, name)
            self.assertEqual(expected[name], {"stream": stream, "samples": sample}, name)

    def test_every_valid_fixture_is_conformant(self):
        for name, d in load("valid"):
            r = S.check_stream(d)
            self.assertTrue(r.conformant, (name, r))

    def test_every_invalid_fixture_gives_exactly_the_hand_written_diagnostics(self):
        expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
        for name, d in load("invalid"):
            r = S.check_stream(d)
            self.assertEqual(pairs(r.stream), sorted(expected[name]["stream"]), name)
            self.assertEqual(pairs(r.samples), sorted(expected[name]["samples"]), name)
            self.assertFalse(r.conformant, name)

    def test_every_stream_code_is_exercised_by_a_fixture(self):
        expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
        seen = {c for e in expected.values() for _, c in e["stream"]}
        self.assertEqual(seen, set(S.STREAM_ERROR_CODES))

    def test_fixtures_are_independent_of_the_input_object(self):
        for _, d in load("invalid"):
            before = copy.deepcopy(d)
            S.check_stream(d)
            self.assertEqual(d, before)

    def test_the_empty_stream_and_open_close_stream(self):
        self.assertEqual(codes(B.doc([])), (["STREAM_OPEN_MISSING"], []))
        self.assertEqual(codes(B.doc([B.opened(), B.closed()])), ([], []))
        self.assertEqual(codes(B.doc([B.opened(first=1), B.closed(last=1)])),
                         (["STREAM_FIRST_SEQUENCE_UNMET", "STREAM_LAST_SEQUENCE_UNMET"], []))


class Lifecycle(unittest.TestCase):  # AC-502
    def test_valid_orderings(self):
        s = B.samples(3)
        for recs in ([B.opened(), B.closed()], [B.opened(), B.smp(s[0]), B.closed()],
                     [B.opened()] + [B.smp(x) for x in s] + [B.closed()]):
            self.assertEqual(codes(B.doc(recs)), ([], []))

    def test_each_invalid_ordering_and_the_checker_continues(self):
        s = B.samples(3)
        cases = {
            "STREAM_SAMPLE_BEFORE_OPEN": B.doc([B.smp(s[0]), B.opened(), B.closed()]),
            "STREAM_SAMPLE_AFTER_CLOSE": B.doc([B.opened(), B.closed(), B.smp(s[0])]),
            "STREAM_CLOSE_REPEATED": B.doc([B.opened(), B.closed(), B.closed()]),
            "STREAM_OPEN_REPEATED": B.doc([B.opened(), B.opened(), B.closed()]),
            "STREAM_CLOSE_BEFORE_OPEN": B.doc([B.closed(), B.opened(), B.closed()]),
            "STREAM_OPEN_NOT_FIRST": B.doc([B.smp(s[0]), B.opened(), B.closed()]),
            "STREAM_UNTERMINATED": B.doc([B.opened(), B.smp(s[0])]),
            "STREAM_OPEN_MISSING": B.doc([B.smp(s[0]), B.closed()]),
        }
        for code, d in cases.items():
            self.assertIn(code, codes(d)[0], code)

    def test_no_record_is_dropped_reordered_or_repaired(self):
        s = B.samples(4)
        recs = [B.smp(s[0]), B.closed(), B.opened(), B.smp(s[1]), B.closed(), B.smp(s[2]), B.opened(), B.smp(s[3])]
        d = B.doc(recs)
        before = copy.deepcopy(d)
        r = S.check_stream(d)
        self.assertEqual(d, before)
        # every sample record is still checked: positions 0, 3, 5 and 7 are all reached by the sample checks
        bad = B.doc(copy.deepcopy(recs))
        for pos in (0, 3, 5, 7):
            bad["records"][pos]["sample"]["measurements"]["accel_x"]["unit"] = "g"
        self.assertEqual(sorted(v.position for v in S.check_stream(bad).samples), [0, 3, 5, 7])
        self.assertTrue(r.stream)

    def test_samples_outside_the_open_state_still_take_part_in_sequence_and_timestamp_checks(self):
        s = B.samples(4)
        s[2]["sequence"] = 150
        d = B.doc([B.smp(s[0]), B.smp(s[1]), B.opened(), B.smp(s[2]), B.smp(s[3]), B.closed()])
        r = S.check_stream(d)
        self.assertIn([3, "STREAM_SEQUENCE_GAP"], pairs(r.stream))

    def test_repeated_open_does_not_change_the_identity(self):
        s = B.samples(3)
        d = B.doc([B.opened(), B.opened(sensor="other.sensor", kind="range", clock="utc"), B.smp(s[0]), B.closed()])
        self.assertEqual(codes(d)[0], ["STREAM_OPEN_REPEATED"])

    def test_index_rules(self):
        d = good()
        d["records"][2]["index"] = 5
        self.assertEqual(codes(d), (["STREAM_INDEX_MISMATCH"], []))
        self.assertEqual(pairs(S.check_stream(d).stream), [[2, "STREAM_INDEX_MISMATCH"]])
        # a dropped record shows as an index mismatch from the next record on, and a sequence gap
        d = good()
        del d["records"][2]
        c = pairs(S.check_stream(d).stream)
        self.assertIn([2, "STREAM_INDEX_MISMATCH"], c)
        self.assertIn([2, "STREAM_SEQUENCE_GAP"], c)


class Sequence(unittest.TestCase):  # AC-503
    def seqs(self, values, **kw):
        ss = B.samples(len(values))
        for s, v in zip(ss, values):
            s["sequence"] = v
        return B.full(ss, **kw)

    def test_duplicate_regression_gap_are_mutually_exclusive_for_every_pair(self):
        for p in range(0, 6):
            for c in range(0, 9):
                got = [x for x in codes(self.seqs([p, c]))[0]]
                if c == p:
                    want = ["STREAM_SEQUENCE_DUPLICATE"]
                elif c < p:
                    want = ["STREAM_SEQUENCE_REGRESSION"]
                elif c > p + 1:
                    want = ["STREAM_SEQUENCE_GAP"]
                else:
                    want = []
                self.assertEqual(got, want, (p, c))

    def test_gap_states_first_and_last_missing_number(self):
        r = S.check_stream(self.seqs([4, 9]))
        (gap,) = r.stream
        self.assertEqual((gap.position, gap.code), (2, "STREAM_SEQUENCE_GAP"))
        self.assertIn("5 to 8", gap.message)
        (gap,) = S.check_stream(self.seqs([4, 6])).stream
        self.assertIn("5 to 5", gap.message)

    def test_a_clean_stream_reports_nothing(self):
        self.assertEqual(codes(self.seqs([0, 1, 2, 3])), ([], []))
        self.assertEqual(codes(self.seqs([2**40, 2**40 + 1])), ([], []))
        self.assertEqual(codes(self.seqs([7])), ([], []))

    def test_no_first_or_last_sample_is_inferred_without_a_bound(self):
        self.assertEqual(codes(self.seqs([5, 6, 7])), ([], []))
        self.assertEqual(codes(self.seqs([0], first=None, last=None)), ([], []))

    def test_bounds(self):
        self.assertEqual(codes(self.seqs([5, 6, 7], first=5, last=7)), ([], []))
        self.assertEqual(codes(self.seqs([5, 6, 7], first=4)), (["STREAM_FIRST_SEQUENCE_UNMET"], []))
        self.assertEqual(codes(self.seqs([5, 6, 7], last=8)), (["STREAM_LAST_SEQUENCE_UNMET"], []))
        self.assertEqual(codes(self.seqs([5, 6, 7], first=4, last=8)),
                         (["STREAM_FIRST_SEQUENCE_UNMET", "STREAM_LAST_SEQUENCE_UNMET"], []))
        # a stated last bound with no close record is not judged
        d = self.seqs([5, 6, 7], last=99)
        del d["records"][-1]
        self.assertEqual(codes(d)[0], ["STREAM_UNTERMINATED"])
        # a bound is judged on the first sample after the open and the last sample before the close
        s = B.samples(3, start=5)
        d = B.doc([B.smp(B.samples(1, start=50)[0]), B.opened(first=5), B.smp(s[0]), B.smp(s[1]), B.smp(s[2]),
                   B.closed(last=7)])
        c = codes(d)[0]
        self.assertNotIn("STREAM_FIRST_SEQUENCE_UNMET", c)
        self.assertNotIn("STREAM_LAST_SEQUENCE_UNMET", c)

    def test_a_sample_with_a_bad_sequence_neither_moves_the_previous_nor_is_judged(self):
        ss = B.samples(4)
        ss[2]["sequence"] = -5
        r = S.check_stream(B.full(ss))
        self.assertEqual([d.code for d in r.stream], ["STREAM_SEQUENCE_GAP"])     # 101 then 103 (102 was malformed)
        self.assertEqual([v.code for v in r.samples], ["MALFORMED_FIELD"])
        ss = B.samples(3)
        ss[2]["sequence"] = "last"
        r = S.check_stream(B.full(ss, last=102))
        self.assertEqual([d.code for d in r.stream], [])                           # the bound is not judged on it

    def test_gap_regression_duplicate_from_the_generator(self):
        # the generator continues after a repeated sequence as if it had not repeated: a duplicate, then a gap
        for fault, want in (("gap", ["STREAM_SEQUENCE_GAP"]),
                            ("regression", ["STREAM_SEQUENCE_DUPLICATE", "STREAM_SEQUENCE_GAP"])):
            for seed in range(10):
                ss = G.generate_samples("imu", "imu.main", 8, seed, start_sequence=3, faults={4: fault})["samples"]
                self.assertEqual(codes(B.full(ss))[0], want, (fault, seed))


class TimestampsAndIdentity(unittest.TestCase):  # AC-504
    def test_equal_timestamp_is_not_a_regression_and_lower_is(self):
        ss = B.samples(3)
        ss[1]["timestamp"]["value"] = ss[0]["timestamp"]["value"]
        ss[2]["timestamp"]["value"] = ss[0]["timestamp"]["value"]
        self.assertEqual(codes(B.full(ss)), ([], []))
        ss[2]["timestamp"]["value"] -= 1
        self.assertEqual(codes(B.full(ss)), (["STREAM_TIMESTAMP_REGRESSION"], []))

    def test_clock_mismatch_is_reported_once_and_regression_is_not_compared_across_clocks(self):
        ss = B.samples(3)
        ss[1]["timestamp"]["clock"] = "utc"
        ss[1]["timestamp"]["value"] = 0                   # lower, but on another clock
        self.assertEqual(codes(B.full(ss)), (["STREAM_CLOCK_MISMATCH"], []))

    def test_clock_mismatch_for_a_utc_stream(self):
        ss = B.samples(3, clock="utc")
        ss[1]["timestamp"]["clock"] = "monotonic"
        self.assertEqual(codes(B.full(ss, clock="utc"))[0], ["STREAM_CLOCK_MISMATCH"])

    def test_sensor_and_kind_changes_compare_with_the_open_record(self):
        ss = B.samples(4)
        ss[1]["sensor_id"] = "imu.other"
        ss[2]["sensor_id"] = "imu.other"
        c = codes(B.full(ss))[0]
        self.assertEqual(c, ["STREAM_SENSOR_CHANGE", "STREAM_SENSOR_CHANGE"])
        ss = B.samples(3)
        ss[1]["kind"] = "range"
        r = S.check_stream(B.full(ss))
        self.assertEqual([d.code for d in r.stream], ["STREAM_KIND_CHANGE"])

    def test_sample_codes_stay_separate_and_unchanged(self):
        ss = B.samples(3)
        ss[1]["sensor_id"] = "Bad Id"
        r = S.check_stream(B.full(ss))
        self.assertEqual([v.code for v in r.samples], ["INVALID_SENSOR_ID"])
        self.assertEqual([d.code for d in r.stream], ["STREAM_SENSOR_CHANGE"])
        self.assertFalse(set(d.code for d in r.stream) & set(V.ERROR_CODES))
        self.assertTrue(all(v.code in V.ERROR_CODES for v in r.samples))


class Samples(unittest.TestCase):  # AC-505
    def test_embedded_samples_use_the_unchanged_validator(self):
        ss = B.samples(5, faults={0: "bad_unit", 1: "unknown_frame", 2: "missing_measurement", 3: "bad_timestamp",
                                  4: "bad_version"})
        d = B.full(ss)
        r = S.check_stream(d)
        for i, s in enumerate(ss):
            want = sorted((v.code, v.path, v.message) for v in V.validate_sample(s))
            got = sorted((v.code, v.path, v.message) for v in r.samples if v.position == i + 1)
            self.assertEqual(got, want, i)
        self.assertEqual(len({v.position for v in r.samples}), 5)

    def test_a_gap_or_other_clock_leaves_the_sample_conformant(self):
        ss = B.samples(4, faults={2: "gap"})
        ss[3]["timestamp"]["clock"] = "utc"
        for s in ss:
            self.assertEqual(V.validate_sample(s), [])
        r = S.check_stream(B.full(ss))
        self.assertEqual(r.samples, [])
        self.assertEqual(sorted(d.code for d in r.stream), ["STREAM_CLOCK_MISMATCH", "STREAM_SEQUENCE_GAP"])

    def test_validity_states_are_not_stream_diagnostics(self):
        ss = B.samples(5, faults={1: "stale", 2: "missing", 3: "invalid"})
        self.assertEqual(codes(B.full(ss)), ([], []))

    def test_a_non_conformant_stream_with_only_sample_violations(self):
        ss = B.samples(3)
        ss[1]["measurements"]["accel_x"]["unit"] = "g"
        r = S.check_stream(B.full(ss))
        self.assertEqual(r.stream, [])
        self.assertEqual([(v.position, v.code) for v in r.samples], [(2, "INVALID_UNIT")])
        self.assertFalse(r.conformant)


class Determinism(unittest.TestCase):  # AC-506
    def big(self, n=10_000, seed=3):
        # generator faults: a gap at sample 10, a repeated sequence at sample 500 (a duplicate, and a gap at the next
        # sample because the generator continues as if it had not repeated), a bad unit at sample 0.7 * n
        ss = B.samples(n, seed=seed, faults={10: "gap", 500: "regression", n * 7 // 10: "bad_unit"}, start_ns=0)
        d = B.full(ss, first=100)
        d["records"][n // 4]["sample"]["timestamp"]["value"] = 0     # record n/4: a timestamp regression
        return d

    def test_the_diagnostics_are_sorted_by_the_documented_key_and_repeatable(self):
        d = B.full(B.samples(6, faults={2: "gap", 4: "regression"}))
        d["records"][5]["sample"]["timestamp"]["clock"] = "utc"
        r1, r2 = S.check_stream(d), S.check_stream(copy.deepcopy(d))
        self.assertEqual(r1.stream, r2.stream)
        self.assertEqual(r1.stream, sorted(r1.stream, key=lambda x: (x.position, x.code, x.path, x.message)))
        self.assertEqual(r1.samples, sorted(r1.samples, key=lambda x: (x.position, x.code, x.path, x.message)))

    def test_batching_invariance_for_every_split_of_small_streams(self):
        docs = [good(3, first=100, last=102)]
        d = B.full(B.samples(4, faults={2: "gap"}))
        d["records"][1]["sample"]["sensor_id"] = "imu.other"
        docs.append(d)
        s = B.samples(3)
        docs.append(B.doc([B.smp(s[0]), B.closed(), B.opened(first=1), B.smp(s[1]), B.closed(last=9), B.opened()]))
        docs.append(B.doc([]))
        for d in docs:
            recs = d["records"]
            want = S.check_stream(d)
            n = len(recs)
            for cuts in itertools.product((False, True), repeat=max(n - 1, 0)):
                chk = S.StreamChecker()
                start = 0
                for i, cut in enumerate(list(cuts) + [True]):
                    if cut:
                        chk.feed(recs[start:i + 1])
                        start = i + 1
                chk.finish()
                got = chk.result()
                self.assertEqual(got.stream, want.stream, cuts)
                self.assertEqual(got.samples, want.samples, cuts)

    def test_batching_invariance_for_random_splits_of_a_large_stream(self):
        d = self.big(2000)
        want = S.check_stream(d)
        rng = random.Random(5)
        for _ in range(20):
            chk = S.StreamChecker()
            i = 0
            while i < len(d["records"]):
                step = rng.choice((1, 2, 3, 17, 250, 999))
                chk.feed(d["records"][i:i + step])
                i += step
            chk.finish()
            self.assertEqual(chk.result().stream, want.stream)
            self.assertEqual(chk.result().samples, want.samples)

    def test_a_batch_alone_is_a_stream_of_its_own(self):
        d = good(6)
        tail = B.doc(d["records"][3:])
        alone = S.check_stream(tail)
        self.assertIn("STREAM_OPEN_MISSING", [x.code for x in alone.stream])
        self.assertNotIn("STREAM_SEQUENCE_GAP", [x.code for x in alone.stream])   # no cross-batch condition
        chk = S.StreamChecker()
        chk.feed(d["records"][:3])
        chk.feed(d["records"][3:])
        chk.finish()
        self.assertTrue(chk.result().conformant)

    def test_a_cross_batch_gap_is_found_only_by_one_checker(self):
        d = good(6)
        del d["records"][3]
        for i, r in enumerate(d["records"]):
            r["index"] = i
        chk = S.StreamChecker()
        first = chk.feed(d["records"][:3])
        second = chk.feed(d["records"][3:])
        chk.finish()
        self.assertEqual(first.stream, [])
        self.assertEqual([x.code for x in second.stream], ["STREAM_SEQUENCE_GAP"])
        self.assertEqual([x.position for x in second.stream], [3])

    def test_feed_after_finish_and_double_finish_are_refused(self):
        chk = S.StreamChecker()
        chk.finish()
        with self.assertRaises(ValueError):
            chk.feed([])
        with self.assertRaises(ValueError):
            chk.finish()
        with self.assertRaises(ValueError):
            S.StreamChecker().feed("records")

    def test_ten_thousand_records_are_checked_correctly(self):   # correctness and scale only; no runtime claim
        d = self.big(10_000)
        self.assertEqual(len(d["records"]), 10_002)
        r = S.check_stream(d)
        # sample i is at position i + 1
        self.assertEqual(sorted((x.position, x.code) for x in r.stream),
                         [(11, "STREAM_SEQUENCE_GAP"), (501, "STREAM_SEQUENCE_DUPLICATE"),
                          (502, "STREAM_SEQUENCE_GAP"), (2500, "STREAM_TIMESTAMP_REGRESSION")])
        self.assertEqual([(v.position, v.code) for v in r.samples], [(7001, "INVALID_UNIT")])
        chk = S.StreamChecker()
        for i in range(0, len(d["records"]), 997):
            chk.feed(d["records"][i:i + 997])
        chk.finish()
        self.assertEqual(chk.result().stream, r.stream)
        self.assertEqual(chk.result().samples, r.samples)

    def test_two_runs_in_separate_processes_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            d = B.full(B.samples(30, faults={5: "gap", 9: "regression"}))
            path.write_text(json.dumps(d), encoding="utf-8")
            a, b = run(str(path)), run(str(path))
        self.assertEqual((a.returncode, a.stdout), (b.returncode, b.stdout))
        self.assertEqual(a.returncode, 1)


class CommandLine(unittest.TestCase):  # AC-507
    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = Path(tmp) / "ok.json"
            ok.write_text(json.dumps(good()), encoding="utf-8")
            r = run(str(ok))
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "conformant"))
            bad = Path(tmp) / "bad.json"
            d = good()
            d["records"][2]["sample"]["measurements"]["accel_x"]["unit"] = "g"
            d["records"][3]["sample"]["sequence"] = 150
            bad.write_text(json.dumps(d), encoding="utf-8")
            r = run(str(bad))
            self.assertEqual(r.returncode, 1)
            lines = r.stdout.strip().splitlines()
            self.assertTrue(lines[0].startswith("STREAM_SEQUENCE_GAP record 3 "))
            self.assertTrue(any(l.startswith("SAMPLE INVALID_UNIT record 2 ") for l in lines))
            self.assertEqual(lines[-1], "not conformant")
            junk = Path(tmp) / "junk.json"
            junk.write_text("{not json", encoding="utf-8")
            self.assertEqual(run(str(junk)).returncode, 2)
            self.assertEqual(run(str(Path(tmp) / "absent.json")).returncode, 2)
            binary = Path(tmp) / "bin.json"
            binary.write_bytes(b"\xff\xfe\x00")
            self.assertEqual(run(str(binary)).returncode, 2)
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("a", "b").returncode, 2)

    def test_the_worked_example_fixtures(self):
        self.assertEqual(run(str(FIX / "valid" / "worked_example.json")).returncode, 0)
        r = run(str(FIX / "invalid" / "worked_example_gap.json"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("sequence 101 to 101 missing", r.stdout)

    def test_the_whole_fixture_set_through_the_command_line(self):
        for name, _ in load("valid"):
            self.assertEqual(run(str(FIX / "valid" / (name + ".json"))).returncode, 0, name)
        for name, _ in load("invalid"):
            self.assertEqual(run(str(FIX / "invalid" / (name + ".json"))).returncode, 1, name)


class Boundaries(unittest.TestCase):  # AC-507
    def test_the_accepted_contracts_schemas_and_code_are_unchanged(self):
        self.assertEqual(sha("contract/sense-sample.schema.json"), SAMPLE_SCHEMA_SHA256)
        self.assertEqual(sha("contract/frame-transform.schema.json"), FRAME_SCHEMA_SHA256)
        self.assertEqual(sha("contract/SENSE_CONTRACT.md"), SENSE_CONTRACT_MD_SHA256)
        self.assertEqual(sha("contract/FRAME_GRAPH_CONTRACT.md"), FRAME_GRAPH_CONTRACT_MD_SHA256)
        self.assertEqual(sha("src/kritva_sense/validator.py"), VALIDATOR_PY_SHA256)
        self.assertEqual(sha("src/kritva_sense/generator.py"), GENERATOR_PY_SHA256)
        self.assertEqual(sha("src/kritva_sense/frame_graph.py"), FRAME_GRAPH_PY_SHA256)

    def test_the_stream_module_imports_only_the_standard_library_and_the_validator(self):
        src = (ROOT / "src" / "kritva_sense" / "stream.py").read_text(encoding="utf-8")
        imports = set(re.findall(r"^(?:import|from) ([a-zA-Z_.]+)", src, re.M))
        self.assertEqual(imports, {"json", "sys", "collections", ".validator"})

    def test_the_stream_module_does_not_import_other_sense_modules(self):
        src = (ROOT / "src" / "kritva_sense" / "stream.py").read_text(encoding="utf-8")
        for name in ("generator", "frame_graph", "mind", "motion", "skill"):
            self.assertNotRegex(src, r"import\s+.*\b%s\b" % name)
            self.assertNotRegex(src, r"from\s+\S*\b%s\b\s+import" % name)

    def test_make_test_unit_runs_the_stream_tests(self):
        mk = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s tests/stream", mk)


if __name__ == "__main__":
    unittest.main()
