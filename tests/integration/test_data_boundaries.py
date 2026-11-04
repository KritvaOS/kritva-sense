"""INT-01 to INT-05: generator output across the validator, frame graph reference and stream checker boundaries."""
import math
import unittest

import fixture as F
from kritva_sense import frame_graph as FG
from kritva_sense import stream as S
from kritva_sense import validator as V


def codes(sample):
    return sorted({v.code for v in V.validate_sample(sample)})


class Int01GeneratedSamplesAreConformant(unittest.TestCase):
    SCENARIO = "INT-01"

    def test_every_kind_validates(self):
        for kind, sensor in (("imu", "imu_main"), ("range", "range_front"), ("encoder", "enc_left"),
                             ("temperature", "temp_board")):
            doc = F.produce_samples(kind=kind, sensor_id=sensor, count=6)
            self.assertEqual(len(doc["samples"]), 6)
            for s in doc["samples"]:
                self.assertEqual(V.validate_sample(s), [], (kind, s["sequence"]))

    def test_both_clocks(self):
        for clock in ("monotonic", "utc"):
            for s in F.produce_samples(count=3, clock=clock)["samples"]:
                self.assertEqual(V.validate_sample(s), [])


class Int02GeneratedFaultsMeetTheValidator(unittest.TestCase):
    SCENARIO = "INT-02"

    # Expected codes written from GENERATOR 3 and SENSE_CONTRACT 4 and 6, not read from the generator table.
    STRUCTURAL = {"bad_unit": "INVALID_UNIT", "unknown_frame": "UNKNOWN_FRAME", "missing_measurement": "MISSING_FIELD",
                  "bad_timestamp": "INVALID_TIMESTAMP", "bad_version": "UNSUPPORTED_CONTRACT_VERSION"}
    CONFORMANT = ("stale", "missing", "invalid", "gap", "regression")   # regression is a sequence fault: one sample is clean

    def test_structural_faults_give_their_code_on_the_faulty_sample_only(self):
        for fault, code in self.STRUCTURAL.items():
            samples = F.produce_samples(count=4, faults={2: fault})["samples"]
            self.assertEqual([codes(s) for s in samples], [[], [], [code], []], fault)

    def test_declared_states_gap_regression_and_boundary_are_conformant(self):
        for fault in self.CONFORMANT:
            for s in F.produce_samples(count=4, faults={2: fault})["samples"]:
                self.assertEqual(V.validate_sample(s), [], fault)
        for s in F.produce_samples(count=3, faults={2: "boundary"})["samples"]:
            self.assertEqual(V.validate_sample(s), [])

    def test_declared_states_carry_their_validity(self):
        for fault, validity in (("stale", "STALE"), ("missing", "MISSING"), ("invalid", "INVALID")):
            self.assertEqual(F.produce_samples(count=4, faults={2: fault})["samples"][2]["validity"], validity)


class Int03GeneratedGraphsMeetTheFrameGraphReference(unittest.TestCase):
    SCENARIO = "INT-03"

    def test_clean_graph_resolves_and_inverts(self):
        for extra, last in ((0, "sensor"), (2, "link_2")):
            graph = F.produce_graph(extra_frames=extra)["graph"]
            self.assertEqual(FG.validate_graph(graph), [])
            forward, v1 = FG.resolve(graph, "world", last)
            back, v2 = FG.resolve(graph, last, "world")
            self.assertEqual((v1, v2), ([], []))
            self.assertEqual(forward["translation_unit"], "m")
            # compose back o forward: apply forward (p_world = ... as defined by the contract), then back
            self.assertLess(_compose_error(forward, back), 1e-9, extra)

    def test_defects_give_exactly_their_code_and_resolve_nothing(self):
        for defect, code in (("cycle", "FG_CYCLE"), ("duplicate_edge", "FG_DUPLICATE_EDGE"),
                             ("multiple_parents", "FG_MULTIPLE_PARENTS"),
                             ("not_unit_quaternion", "FG_NOT_UNIT_QUATERNION")):
            graph = F.produce_graph(defect=defect)["graph"]
            self.assertEqual(sorted({v.code for v in FG.validate_graph(graph)}), [code], defect)
            transform, violations = FG.resolve(graph, "world", "sensor")
            self.assertIsNone(transform, defect)
            self.assertIn(code, {v.code for v in violations}, defect)


def _rotate(q, v):
    w, x, y, z = q
    # v' = q v q^-1 for a unit quaternion
    tx, ty, tz = (2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0]))
    return (v[0] + w * tx + (y * tz - z * ty), v[1] + w * ty + (z * tx - x * tz), v[2] + w * tz + (x * ty - y * tx))


def _compose_error(forward, back):
    """Largest deviation from the identity of (back o forward) applied to the origin and to three unit vectors."""
    def apply(tf, p):
        r = tf["rotation"]
        t = tf["translation"]
        rp = _rotate((r["w"], r["x"], r["y"], r["z"]), p)
        return (rp[0] + t["x"], rp[1] + t["y"], rp[2] + t["z"])
    worst = 0.0
    for p in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        q = apply(back, apply(forward, p))
        worst = max(worst, max(abs(q[i] - p[i]) for i in range(3)))
    return worst


class Int04ValidStreams(unittest.TestCase):
    SCENARIO = "INT-04"

    def test_generated_stream_is_conformant(self):
        result = S.check_stream(F.produce_stream(F.produce_samples(count=5)["samples"]))
        self.assertTrue(result.conformant)
        self.assertEqual((result.stream, result.samples), ([], []))

    def test_declared_states_are_not_stream_diagnostics(self):
        samples = F.produce_samples(count=5, faults={1: "stale", 2: "missing", 3: "invalid"})["samples"]
        result = S.check_stream(F.produce_stream(samples))
        self.assertTrue(result.conformant)

    def test_stated_bounds_are_met(self):
        samples = F.produce_samples(count=5)["samples"]
        result = S.check_stream(F.produce_stream(samples, first=0, last=4))
        self.assertTrue(result.conformant)


class Int05FaultedStreams(unittest.TestCase):
    SCENARIO = "INT-05"

    @staticmethod
    def check(doc):
        r = S.check_stream(doc)
        return ([(d.position, d.code) for d in r.stream], [(v.position, v.code) for v in r.samples])

    def test_sequence_repeat_is_a_duplicate_then_a_gap(self):
        # sequences 0, 1, 1, 3, 4: record 0 is the open, so the repeat is at record 3 (STREAM_CONTRACT 6: c == p),
        # and 3 > 1 + 1 at record 4 is a gap
        got = self.check(F.produce_stream(F.produce_samples(count=5, faults={2: "regression"})["samples"]))
        self.assertEqual(got, ([(3, "STREAM_SEQUENCE_DUPLICATE"), (4, "STREAM_SEQUENCE_GAP")], []))

    def test_gap(self):
        # sequences 0, 1, 7, 8, 9: the jump of 5 at sample index 2 is c = 7 > p + 1 = 2 at record 3, reported once
        got = self.check(F.produce_stream(F.produce_samples(count=5, faults={2: "gap"})["samples"]))
        self.assertEqual(got, ([(3, "STREAM_SEQUENCE_GAP")], []))

    def test_out_of_order(self):
        # sequences 0, 2, 1, 3, 4 and timestamps swapped with them: gap at 2, then 1 < 2 is a sequence and a timestamp
        # regression at record 3, then 3 > 1 + 1 is a gap at record 4
        samples = F.produce_samples(count=5)["samples"]
        samples[1], samples[2] = samples[2], samples[1]
        got = self.check(F.produce_stream(samples))
        self.assertEqual(got, ([(2, "STREAM_SEQUENCE_GAP"), (3, "STREAM_SEQUENCE_REGRESSION"),
                                (3, "STREAM_TIMESTAMP_REGRESSION"), (4, "STREAM_SEQUENCE_GAP")], []))

    def test_malformed_lifecycle(self):
        samples = F.produce_samples(count=2)["samples"]
        no_open, _ = self.check(F.produce_stream(samples, with_open=False))
        self.assertEqual(no_open[0], (-1, "STREAM_OPEN_MISSING"))
        self.assertTrue(all(c in ("STREAM_OPEN_MISSING", "STREAM_SAMPLE_BEFORE_OPEN", "STREAM_CLOSE_BEFORE_OPEN")
                            for _, c in no_open))
        no_close, _ = self.check(F.produce_stream(samples, with_close=False))
        self.assertEqual(no_close, [(-1, "STREAM_UNTERMINATED")])

    def test_structural_fault_inside_a_stream_is_a_sample_violation_only(self):
        # sample index 2 is record 3 (the open is record 0); embedded validation reports the validator code
        got = self.check(F.produce_stream(F.produce_samples(count=5, faults={2: "bad_unit"})["samples"]))
        self.assertEqual(got, ([], [(3, "INVALID_UNIT")]))


if __name__ == "__main__":
    unittest.main()
