"""KOS-SENSE-003 unit tests: frame graph and transform validation (synthetic data only)."""
import copy
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kritva_sense import frame_graph as F  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
TOL = 1e-9
H = math.sqrt(0.5)
SAMPLE_SCHEMA_SHA256 = "1f6f0824af55237b0b3e90ddd413ddef8c48e2eb3cd19a7f4244295bd2b9bc6b"


def load(group):
    return [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted((FIX / group).glob("*.json"))]


def edge(parent, child, t=(0.0, 0.0, 0.0), q=(1.0, 0.0, 0.0, 0.0)):
    return {"parent": parent, "child": child, "translation": dict(zip("xyz", t)), "translation_unit": "m",
            "rotation": dict(zip("wxyz", q))}


def graph(*edges):
    return {"contract_version": "0.1.0", "transforms": list(edges)}


def close(a, b):
    return all(abs(a["translation"][k] - b["translation"][k]) <= TOL for k in "xyz") and \
        all(abs(a["rotation"][k] - b["rotation"][k]) <= TOL for k in "wxyz")


class Representation(unittest.TestCase):  # AC-301
    def test_schema_and_constants_agree(self):
        schema = json.loads((ROOT / "contract" / "frame-transform.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["contract_version"]["const"], F.FRAME_GRAPH_VERSION)
        t = schema["$defs"]["transform"]
        self.assertEqual(sorted(t["required"]), sorted(F.TRANSFORM_FIELDS))
        self.assertEqual(t["properties"]["translation_unit"]["const"], F.TRANSLATION_UNIT)
        self.assertEqual(sorted(t["properties"]["rotation"]["required"]), sorted(F.ROTATION_FIELDS))
        self.assertEqual(sorted(t["properties"]["translation"]["required"]), sorted(F.TRANSLATION_FIELDS))
        for sub in (t, t["properties"]["rotation"], t["properties"]["translation"], schema):
            self.assertIs(sub["additionalProperties"], False)

    def test_contract_document_states_version_direction_and_every_error_code(self):
        doc = (ROOT / "contract" / "FRAME_GRAPH_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("| Version | Frame graph contract version: %s |" % F.FRAME_GRAPH_VERSION, doc)
        for code in F.ERROR_CODES:
            self.assertIn("`%s`" % code, doc)
        for needle in ("p_parent = R(q) * p_child + t", "Hamilton", "unit quaternion", "one parent", "never invents"):
            self.assertIn(needle, doc)

class ValidGraphs(unittest.TestCase):  # AC-302
    def test_every_valid_fixture_passes(self):
        fixtures = load("valid")
        self.assertGreaterEqual(len(fixtures), 6)
        for name, doc in fixtures:
            with self.subTest(name):
                self.assertEqual(F.validate_graph(doc["graph"]), [])

    def test_a_single_transform_validates_on_its_own(self):
        self.assertEqual(F.validate_transform(edge("world", "base", (1, 2, 3))), [])

    def test_integers_are_accepted_as_numbers(self):
        self.assertEqual(F.validate_transform(edge("world", "base", (1, 2, 3), (1, 0, 0, 0))), [])


class InvalidGraphs(unittest.TestCase):  # AC-302, AC-303
    def test_each_invalid_fixture_is_rejected_with_the_documented_codes(self):
        fixtures = load("invalid")
        self.assertGreaterEqual(len(fixtures), 30)
        for name, doc in fixtures:
            with self.subTest(name):
                got = sorted({v.code for v in F.validate_graph(doc["graph"])})
                self.assertEqual(got, sorted(doc["expected_codes"]))
                for code in got:
                    self.assertIn(code, F.ERROR_CODES)

    def test_every_error_code_of_graph_validation_is_exercised(self):
        seen = {c for _, doc in load("invalid") for c in doc["expected_codes"]}
        self.assertEqual(seen, set(F.ERROR_CODES) - {"FG_FRAME_NOT_IN_GRAPH", "FG_NO_PATH"})

    def test_results_are_deterministic_and_sorted(self):
        for name, doc in load("invalid"):
            with self.subTest(name):
                a = F.validate_graph(doc["graph"])
                self.assertEqual(a, F.validate_graph(copy.deepcopy(doc["graph"])))
                self.assertEqual(a, sorted(a, key=lambda v: (v.path, v.code, v.message)))

    def test_non_object_inputs_never_raise(self):
        for bad in (None, 5, "x", [], True, 1.5):
            self.assertEqual([v.code for v in F.validate_graph(bad)], ["FG_MALFORMED"])
            self.assertEqual([v.code for v in F.validate_transform(bad)], ["FG_MALFORMED"])

    def test_nan_and_infinity_are_not_finite(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            e = edge("world", "base", (bad, 0, 0))
            self.assertEqual([v.code for v in F.validate_transform(e)], ["FG_NON_FINITE"])
            e = edge("world", "base", q=(bad, 0, 0, 0))
            self.assertEqual([v.code for v in F.validate_transform(e)], ["FG_NON_FINITE"])

    def test_the_duplicate_and_the_cycle_are_reported_once_each(self):
        g = graph(edge("world", "base"), edge("world", "base"), edge("base", "world"))
        codes = [v.code for v in F.validate_graph(g)]
        self.assertEqual(codes.count("FG_DUPLICATE_EDGE"), 1)
        self.assertEqual(codes.count("FG_CYCLE"), 1)

    def test_numerical_boundary_of_the_unit_norm(self):
        inside = edge("world", "base", q=(1 + 0.5 * F.QUAT_TOLERANCE, 0, 0, 0))
        outside = edge("world", "base", q=(1 + 2 * F.QUAT_TOLERANCE, 0, 0, 0))
        self.assertEqual(F.validate_transform(inside), [])
        self.assertEqual([v.code for v in F.validate_transform(outside)], ["FG_NOT_UNIT_QUATERNION"])

    def test_input_is_never_modified(self):
        for _, doc in load("invalid") + load("valid"):
            g = copy.deepcopy(doc["graph"])
            F.validate_graph(g)
            F.resolve(g, "world", "base")
            self.assertEqual(g, doc["graph"])


class Resolution(unittest.TestCase):  # AC-304
    def test_known_answers(self):
        count = 0
        for name, doc in load("valid"):
            for case in doc["resolve"]:
                with self.subTest("%s %s->%s" % (name, case["from"], case["to"])):
                    got, violations = F.resolve(doc["graph"], case["from"], case["to"])
                    self.assertEqual(violations, [])
                    expected = dict(case["expected"], translation_unit="m")
                    self.assertTrue(close(got, expected), (got, expected))
                    count += 1
        self.assertGreaterEqual(count, 15)

    def test_worked_example_of_the_contract(self):
        g = load("valid")
        g = dict(g)["chain_world_base_sensor"]["graph"]
        t, _ = F.resolve(g, "sensor", "world")
        x, y, z = F.transform_point(t, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(x, 1.0, delta=TOL)
        self.assertAlmostEqual(y, 3.1, delta=TOL)
        self.assertAlmostEqual(z, 0.2, delta=TOL)

    def test_reverse_lookup_is_the_inverse(self):
        for name, doc in load("valid"):
            frames = sorted({e[k] for e in doc["graph"]["transforms"] for k in ("parent", "child")})
            for a in frames:
                for b in frames:
                    forward, v1 = F.resolve(doc["graph"], a, b)
                    back, v2 = F.resolve(doc["graph"], b, a)
                    if v1:
                        continue
                    with self.subTest("%s %s<->%s" % (name, a, b)):
                        for p in ((0, 0, 0), (1, 0, 0), (0.3, -2.5, 7.0)):
                            q = F.transform_point(back, F.transform_point(forward, p))
                            for got, want in zip(q, p):
                                self.assertAlmostEqual(got, want, delta=TOL)

    def test_a_frame_resolves_to_itself_as_identity(self):
        g = graph(edge("world", "base", (1, 2, 3), (H, 0, 0, H)))
        t, v = F.resolve(g, "base", "base")
        self.assertEqual(v, [])
        self.assertTrue(close(t, {"translation": {"x": 0, "y": 0, "z": 0}, "rotation": {"w": 1, "x": 0, "y": 0, "z": 0}}))

    def test_four_quarter_turns_make_a_full_turn(self):
        edges = [edge("f%d" % i, "f%d" % (i + 1), (0, 0, 0), (H, 0, 0, H)) for i in range(4)]
        t, v = F.resolve(graph(*edges), "f4", "f0")
        self.assertEqual(v, [])
        self.assertTrue(close(t, {"translation": {"x": 0, "y": 0, "z": 0}, "rotation": {"w": 1, "x": 0, "y": 0, "z": 0}}))

    def test_long_chain_accumulates_translation(self):
        n = 200
        edges = [edge("n%d" % i, "n%d" % (i + 1), (0.5, 0.0, 0.25)) for i in range(n)]
        t, v = F.resolve(graph(*edges), "n%d" % n, "n0")
        self.assertEqual(v, [])
        self.assertAlmostEqual(t["translation"]["x"], 0.5 * n, delta=1e-6)
        self.assertAlmostEqual(t["translation"]["z"], 0.25 * n, delta=1e-6)

    def test_magnitude_boundaries(self):
        for scale in (1e-12, 1.0, 1e6):
            g = graph(edge("world", "base", (scale, -scale, 2 * scale), (H, 0, H, 0)))
            fwd, _ = F.resolve(g, "base", "world")
            back, _ = F.resolve(g, "world", "base")
            x, y, z = F.transform_point(back, F.transform_point(fwd, (scale, scale, scale)))
            for got in (x, y, z):
                self.assertAlmostEqual(got, scale, delta=max(TOL, scale * 1e-12))

    def test_the_result_is_canonical(self):
        g = graph(edge("world", "base", (0, 0, 0), (-H, 0, 0, -H)))
        t, _ = F.resolve(g, "base", "world")
        self.assertGreaterEqual(t["rotation"]["w"], 0.0)
        self.assertNotIn("-0.0", json.dumps(t))
        self.assertAlmostEqual(math.hypot(*(t["rotation"][k] for k in "wxyz")), 1.0, delta=TOL)
        self.assertEqual(t["translation_unit"], "m")

    def test_resolution_is_deterministic(self):
        g = dict(load("valid"))["chain_world_base_sensor"]["graph"]
        self.assertEqual(F.resolve(g, "sensor", "world"), F.resolve(copy.deepcopy(g), "sensor", "world"))

    def test_edge_order_does_not_matter(self):
        g = graph(edge("world", "base", (1, 0, 0), (H, 0, 0, H)), edge("base", "sensor", (0, 1, 0)))
        r = graph(*reversed(g["transforms"]))
        self.assertEqual(F.resolve(g, "sensor", "world"), F.resolve(r, "sensor", "world"))


class MissingRelationships(unittest.TestCase):  # AC-305
    def test_a_frame_not_in_the_graph_is_reported(self):
        g = graph(edge("world", "base"))
        t, v = F.resolve(g, "sensor", "world")
        self.assertIsNone(t)
        self.assertEqual([(x.code, x.path) for x in v], [("FG_FRAME_NOT_IN_GRAPH", "source")])
        t, v = F.resolve(g, "world", "sensor")
        self.assertEqual([(x.code, x.path) for x in v], [("FG_FRAME_NOT_IN_GRAPH", "target")])

    def test_no_identity_is_invented_for_a_frame_not_in_the_graph(self):
        t, v = F.resolve(graph(edge("world", "base")), "sensor", "sensor")
        self.assertIsNone(t)
        self.assertEqual(v[0].code, "FG_FRAME_NOT_IN_GRAPH")
        t, v = F.resolve(graph(), "world", "world")
        self.assertIsNone(t)
        self.assertEqual({x.code for x in v}, {"FG_FRAME_NOT_IN_GRAPH"})

    def test_disconnected_components_have_no_path(self):
        g = graph(edge("world", "base", (1, 0, 0)), edge("arm_link", "tool_tip", (0, 1, 0)))
        for a, b in (("base", "tool_tip"), ("tool_tip", "world"), ("world", "arm_link")):
            with self.subTest("%s->%s" % (a, b)):
                t, v = F.resolve(g, a, b)
                self.assertIsNone(t)
                self.assertEqual([x.code for x in v], ["FG_NO_PATH"])
        t, v = F.resolve(g, "tool_tip", "arm_link")
        self.assertEqual(v, [])
        self.assertAlmostEqual(t["translation"]["y"], 1.0, delta=TOL)

    def test_an_invalid_frame_id_is_reported(self):
        g = graph(edge("world", "base"))
        for bad in ("World", "", "a b", 5, None):
            with self.subTest(repr(bad)):
                t, v = F.resolve(g, bad, "world")
                self.assertIsNone(t)
                self.assertIn(v[0].code, ("FG_INVALID_FRAME_ID", "FG_MALFORMED"))

    def test_a_non_conformant_graph_resolves_nothing(self):
        for name, doc in load("invalid"):
            with self.subTest(name):
                t, v = F.resolve(doc["graph"], "world", "base")
                self.assertIsNone(t)
                self.assertEqual(sorted({x.code for x in v}), sorted(doc["expected_codes"]))


class GraphLocalFrames(unittest.TestCase):  # AC-301, AC-302: separate from the sample contract's frames
    def test_a_graph_local_frame_is_accepted_in_a_graph_but_rejected_in_a_sample(self):
        from kritva_sense import validator as V
        self.assertEqual(F.validate_graph(graph(edge("world", "arm_link", (0, 1, 0)))), [])
        sample = json.loads((ROOT / "tests" / "contract" / "fixtures" / "valid" / "imu_valid.json").read_text(encoding="utf-8"))["sample"]
        self.assertEqual(V.validate_sample(sample), [])
        sample["frame_id"] = "arm_link"
        self.assertIn("UNKNOWN_FRAME", {v.code for v in V.validate_sample(sample)})
        for frame in V.FRAMES:
            self.assertEqual(F.validate_graph(graph(edge(frame, "arm_link"))), [])


class OrderAndFailClosed(unittest.TestCase):  # record order affects diagnostics, never acceptance
    def test_reordering_records_never_makes_a_graph_conformant(self):
        import itertools
        for name, doc in load("invalid"):
            edges = doc["graph"].get("transforms")
            if not isinstance(edges, list) or len(edges) < 2 or len(edges) > 4:
                continue
            for perm in itertools.permutations(edges):
                with self.subTest(name):
                    g = dict(doc["graph"], transforms=list(perm))
                    self.assertNotEqual(F.validate_graph(g), [])
                    t, v = F.resolve(g, "world", "base")
                    self.assertIsNone(t)
                    self.assertNotEqual(v, [])

    def test_the_first_record_is_the_one_retained_and_the_later_one_is_reported(self):
        first = edge("world", "base", (1, 0, 0))
        second = edge("world", "base", (2, 0, 0))
        v = F.validate_graph(graph(first, second))
        self.assertEqual([(x.code, x.path) for x in v], [("FG_DUPLICATE_EDGE", "transforms[1]")])
        v = F.validate_graph(graph(second, first))
        self.assertEqual([(x.code, x.path) for x in v], [("FG_DUPLICATE_EDGE", "transforms[1]")])
        v = F.validate_graph(graph(edge("world", "sensor"), edge("base", "sensor")))
        self.assertEqual([(x.code, x.path) for x in v], [("FG_MULTIPLE_PARENTS", "transforms[1]")])

    def test_an_invalid_record_is_not_dropped_to_leave_a_resolvable_partial_graph(self):
        good, bad = edge("world", "base", (1, 0, 0)), edge("base", "sensor", q=(2, 0, 0, 0))
        t, v = F.resolve(graph(good, bad), "base", "world")
        self.assertIsNone(t)
        self.assertEqual([x.code for x in v], ["FG_NOT_UNIT_QUATERNION"])


class Gate(unittest.TestCase):  # AC-306, AC-307
    def test_coverage_of_required_cases(self):
        valid = dict(load("valid"))
        self.assertGreaterEqual(len(valid["extra_frame_chain"]["graph"]["transforms"]), 3)        # multi-edge
        names = {n for n, _ in load("invalid")}
        for needed in ("cycle_two_frames", "cycle_three_frames", "cycle_with_a_tail", "quaternion_not_unit",
                       "quaternion_zero", "rotation_as_euler", "quaternion_just_outside_tolerance", "self_link",
                       "duplicate_edge", "multiple_parents"):
            self.assertIn(needed, names)
        self.assertIn("unit_norm_within_tolerance", valid)

    def test_makefile_runs_these_tests(self):
        mk = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests/frame_graph", mk)

    def test_the_sample_schema_is_the_one_released_as_0_1_0(self):
        # KOS-SENSE-003 must not change the accepted sample contract. A deliberate change to the schema needs a
        # new contract version, a changelog entry and a decision, and then this pin is updated with it.
        import hashlib
        schema = (ROOT / "contract" / "sense-sample.schema.json").read_bytes()
        self.assertEqual(hashlib.sha256(schema).hexdigest(), SAMPLE_SCHEMA_SHA256)
        sample = (ROOT / "contract" / "SENSE_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("| Version | Contract version: 0.1.0 |", sample)


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "kritva_sense.frame_graph", *args], cwd=ROOT / "src",
                          capture_output=True, text=True)


class Cli(unittest.TestCase):
    def test_exit_codes(self):
        valid = FIX / "valid" / "single_edge.json"
        with self.subTest("a fixture wraps the graph with a description; the CLI reads a bare graph"):
            self.assertEqual(run_cli(str(valid)).returncode, 1)
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            good = Path(d) / "g.json"
            good.write_text(json.dumps(graph(edge("world", "base", (1, 2, 3)))), encoding="utf-8")
            bad = Path(d) / "b.json"
            bad.write_text(json.dumps(graph(edge("base", "base"))), encoding="utf-8")
            junk = Path(d) / "j.json"
            junk.write_text("{not json", encoding="utf-8")
            self.assertEqual(run_cli(str(good)).returncode, 0)
            self.assertIn("conformant", run_cli(str(good)).stdout)
            r = run_cli(str(bad))
            self.assertEqual(r.returncode, 1)
            self.assertIn("FG_SELF_LINK", r.stdout)
            self.assertEqual(run_cli(str(junk)).returncode, 2)
            self.assertEqual(run_cli(str(Path(d) / "missing.json")).returncode, 2)
            self.assertEqual(run_cli().returncode, 2)
            r = run_cli(str(good), "base", "world")
            self.assertEqual(r.returncode, 0)
            self.assertIn('"x": 1.0', r.stdout)
            r = run_cli(str(good), "base", "moon")
            self.assertEqual(r.returncode, 1)
            self.assertIn("FG_FRAME_NOT_IN_GRAPH", r.stdout)


if __name__ == "__main__":
    unittest.main()
