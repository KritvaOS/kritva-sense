"""KOS-SENSE-004 unit tests: deterministic synthetic sample and frame graph generator (synthetic data only)."""
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kritva_sense import frame_graph as FG  # noqa: E402
from kritva_sense import generator as G  # noqa: E402
from kritva_sense import validator as V  # noqa: E402

SEEDS = list(range(40)) + [2**32, 2**63, 2**64 - 1]
SAMPLE_SCHEMA_SHA256 = "1f6f0824af55237b0b3e90ddd413ddef8c48e2eb3cd19a7f4244295bd2b9bc6b"
FRAME_SCHEMA_SHA256 = "ae644360dc5ba0e679a9e616022b4261b2e95fe967da8af1e4d440f718a099e2"


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def run(*args):
    return subprocess.run([sys.executable, "-m", "kritva_sense.generator", *args], cwd=ROOT / "src",
                          capture_output=True, text=True)


class Determinism(unittest.TestCase):  # AC-401
    def test_splitmix64_known_answers(self):
        r = G.SplitMix64(0)
        self.assertEqual([r.next_u64() for _ in range(3)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F])
        r = G.SplitMix64(1234567)
        self.assertEqual([r.next_u64() for _ in range(2)], [6457827717110365317, 3203168211198807973])

    def test_random_is_in_unit_interval_and_exact(self):
        r = G.SplitMix64(0)
        x = r.random()
        self.assertEqual(x, (0xE220A8397B1DCDAF >> 11) / float(1 << 53))
        for _ in range(1000):
            self.assertTrue(0.0 <= r.random() < 1.0)

    def test_seed_validation(self):
        for bad in (-1, 2**64, 1.5, "1", None, True):
            with self.assertRaises(ValueError):
                G.SplitMix64(bad)

    def test_same_seed_same_bytes(self):
        a = G.dumps(G.generate_samples("imu", "imu.base", 20, 99, faults={3: "stale"}))
        b = G.dumps(G.generate_samples("imu", "imu.base", 20, 99, faults={3: "stale"}))
        self.assertEqual(a, b)
        ga = G.dumps(G.generate_graph(99, 4, "cycle"))
        self.assertEqual(ga, G.dumps(G.generate_graph(99, 4, "cycle")))

    def test_known_answer_samples(self):
        d = G.generate_samples("range", "range.front", 2, 1)
        self.assertEqual(G.SplitMix64(1).next_u64(), 10451216379200822465)
        self.assertEqual(d["samples"][0]["measurements"]["distance"]["value"], 5.687288)
        self.assertEqual(d["samples"][0]["sequence"], 0)
        self.assertEqual(d["samples"][1]["timestamp"]["value"], 10_000_000)

    def test_different_seeds_differ(self):
        a = G.generate_samples("imu", "imu.base", 5, 1)["samples"]
        b = G.generate_samples("imu", "imu.base", 5, 2)["samples"]
        self.assertNotEqual(a, b)
        self.assertNotEqual(G.generate_graph(1)["graph"], G.generate_graph(2)["graph"])

    def test_no_negative_zero_and_json_safe(self):
        text = G.dumps(G.generate_samples("imu", "imu.base", 200, 5))
        self.assertIsNone(re.search(r"-0\.0(?![0-9])", text))
        json.loads(text)


class ValidSamples(unittest.TestCase):  # AC-402
    def test_every_kind_every_seed_conforms(self):
        for kind in V.KINDS:
            for seed in SEEDS:
                d = G.generate_samples(kind, "sensor.a", 4, seed)
                for s in d["samples"]:
                    self.assertEqual(V.validate_sample(s), [], (kind, seed))
                self.assertEqual(G.check_samples(d), [])

    def test_measurements_match_kind_and_units(self):
        for kind, spec in V.KINDS.items():
            s = G.generate_samples(kind, "sensor.a", 1, 3)["samples"][0]
            self.assertEqual(sorted(s["measurements"]), sorted(spec))
            for name, m in s["measurements"].items():
                self.assertEqual(m["unit"], spec[name])
                self.assertTrue(math.isfinite(m["value"]))

    def test_documented_value_ranges(self):
        rng = {"accel_x": (-2.0, 2.0), "accel_y": (-2.0, 2.0), "accel_z": (9.61, 10.01), "gyro_x": (-1.0, 1.0),
               "gyro_y": (-1.0, 1.0), "gyro_z": (-1.0, 1.0), "distance": (0.05, 10.0),
               "position": (-math.pi, math.pi), "temperature": (273.15, 323.15)}
        for kind in V.KINDS:
            for s in G.generate_samples(kind, "sensor.a", 300, 21)["samples"]:
                for name, m in s["measurements"].items():
                    lo, hi = rng[name]
                    self.assertTrue(lo <= m["value"] <= hi, (name, m["value"]))

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            G.generate_samples("lidar", "sensor.a", 1, 1)


class Configuration(unittest.TestCase):  # AC-403
    def test_fields_follow_configuration(self):
        d = G.generate_samples("encoder", "enc.left", 4, 8, start_sequence=10, start_ns=1000, step_ns=250,
                               clock="utc", frame="world")
        self.assertEqual([s["sequence"] for s in d["samples"]], [10, 11, 12, 13])
        self.assertEqual([s["timestamp"]["value"] for s in d["samples"]], [1000, 1250, 1500, 1750])
        for s in d["samples"]:
            self.assertEqual((s["sensor_id"], s["frame_id"], s["timestamp"]["clock"]), ("enc.left", "world", "utc"))
        self.assertEqual(G.check_samples(d), [])

    def test_strictly_increasing_without_faults(self):
        s = G.generate_samples("temperature", "temp.a", 50, 4)["samples"]
        for prev, cur in zip(s, s[1:]):
            self.assertEqual(V.check_sequence(prev, cur), [])

    def test_bad_configuration_is_refused(self):
        for kw in ({"count": -1}, {"count": True}, {"step_ns": 0}, {"start_sequence": -1}, {"start_ns": -5}):
            args = dict(kind="imu", sensor_id="a", count=2, seed=1)
            args.update(kw)
            with self.assertRaises(ValueError, msg=str(kw)):
                G.generate_samples(**args)

    def test_empty_sequence(self):
        d = G.generate_samples("imu", "imu.a", 0, 1)
        self.assertEqual((d["samples"], d["expectations"]), ([], []))


class Faults(unittest.TestCase):  # AC-404
    def test_no_faults_unless_requested(self):
        d = G.generate_samples("imu", "imu.a", 30, 6)
        self.assertEqual(d["expectations"], [])
        self.assertTrue(all(s["validity"] == "VALID" for s in d["samples"]))

    def test_every_fault_gives_its_documented_code(self):
        for fault, code in G.SAMPLE_FAULTS.items():
            for kind in V.KINDS:
                d = G.generate_samples(kind, "sensor.a", 4, 11, faults={3: fault})
                self.assertEqual(d["expectations"], [{"index": 3, "fault": fault, "expected_code": code}])
                self.assertEqual(G.check_samples(d), [], (fault, kind))

    def test_fault_codes_come_from_the_contract(self):
        for code in G.SAMPLE_FAULTS.values():
            if code is not None:
                self.assertIn(code, V.ERROR_CODES)

    def test_gap_and_boundary_are_conformant(self):
        d = G.generate_samples("imu", "imu.a", 4, 2, faults={1: "gap", 3: "boundary"})
        for s in d["samples"]:
            self.assertEqual(V.validate_sample(s), [])
        self.assertEqual([s["sequence"] for s in d["samples"][:3]], [0, 6, 7])
        self.assertEqual(d["samples"][3]["sequence"], 2**53)
        self.assertEqual(d["samples"][3]["timestamp"]["value"], 2**63 - 1)
        self.assertEqual(G.check_samples(d), [])

    def test_sequence_continues_after_a_gap_and_a_regression(self):
        d = G.generate_samples("imu", "imu.a", 6, 2, faults={1: "regression", 3: "gap"})
        self.assertEqual([s["sequence"] for s in d["samples"]], [0, 0, 2, 8, 9, 10])
        self.assertEqual(G.check_samples(d), [])

    def test_boundary_only_on_the_last_sample(self):
        with self.assertRaises(ValueError):
            G.generate_samples("imu", "imu.a", 4, 2, faults={1: "boundary"})

    def test_validity_faults_are_conformant_but_not_usable(self):
        for fault in ("stale", "missing", "invalid"):
            d = G.generate_samples("range", "range.a", 2, 2, faults={1: fault})
            s = d["samples"][1]
            self.assertEqual(V.validate_sample(s), [])
            usable, _ = V.usability(s, s["timestamp"]["value"], "monotonic", 10**9)
            self.assertFalse(usable)

    def test_regression_needs_a_predecessor(self):
        with self.assertRaises(ValueError):
            G.generate_samples("imu", "imu.a", 3, 1, faults={0: "regression"})

    def test_bad_fault_requests_are_refused(self):
        for faults in ({5: "stale"}, {-1: "stale"}, {0: "explode"}, {True: "stale"}):
            with self.assertRaises(ValueError, msg=str(faults)):
                G.generate_samples("imu", "imu.a", 3, 1, faults=faults)

    def test_a_wrong_expectation_is_detected(self):
        d = G.generate_samples("imu", "imu.a", 3, 1, faults={1: "bad_unit"})
        d["expectations"][0]["expected_code"] = "INVALID_TIMESTAMP"
        self.assertTrue(G.check_samples(d))
        d = G.generate_samples("imu", "imu.a", 3, 1)
        d["samples"][1]["frame_id"] = "map"
        self.assertTrue(G.check_samples(d))


class Graphs(unittest.TestCase):  # AC-405
    def test_conformant_graphs_validate_and_resolve(self):
        for seed in SEEDS:
            for extra in (0, 1, 5):
                d = G.generate_graph(seed, extra)
                self.assertEqual(FG.validate_graph(d["graph"]), [])
                self.assertEqual(G.check_graph(d), [])
                self.assertEqual(len(d["graph"]["transforms"]), 2 + extra)

    def test_resolution_matches_hand_composition(self):
        d = G.generate_graph(3)
        a, b = d["graph"]["transforms"]
        tf, viol = FG.resolve(d["graph"], "sensor", "world")
        self.assertEqual(viol, [])
        # world <- base <- sensor: t_world = R_a * t_b + t_a for a point at the sensor origin
        p = FG.transform_point(tf, (0.0, 0.0, 0.0))
        pb = FG.transform_point({"translation": b["translation"], "rotation": b["rotation"]}, (0.0, 0.0, 0.0))
        pw = FG.transform_point({"translation": a["translation"], "rotation": a["rotation"]}, pb)
        for u, v in zip(p, pw):
            self.assertAlmostEqual(u, v, places=9)

    def test_each_defect_gives_exactly_its_code(self):
        for defect, code in G.GRAPH_DEFECTS.items():
            for seed in SEEDS[:12]:
                for extra in (0, 3):
                    d = G.generate_graph(seed, extra, defect)
                    self.assertEqual(sorted({v.code for v in FG.validate_graph(d["graph"])}), [code], (defect, seed))
                    self.assertEqual(d["expectation"], {"defect": defect, "codes": [code]})
                    self.assertEqual(G.check_graph(d), [])

    def test_defect_codes_come_from_the_contract(self):
        for code in G.GRAPH_DEFECTS.values():
            self.assertIn(code, FG.ERROR_CODES)

    def test_graph_local_ids_are_not_sample_frames(self):
        d = G.generate_graph(1, 2)
        ids = {e["child"] for e in d["graph"]["transforms"]} | {e["parent"] for e in d["graph"]["transforms"]}
        self.assertTrue({"link_1", "link_2"} <= ids)
        self.assertFalse({"link_1", "link_2"} & set(V.FRAMES))

    def test_bad_graph_requests_are_refused(self):
        for kw in ({"extra_frames": -1}, {"extra_frames": 101}, {"extra_frames": True}, {"defect": "melt"}):
            with self.assertRaises(ValueError, msg=str(kw)):
                G.generate_graph(1, **kw)

    def test_a_wrong_graph_expectation_is_detected(self):
        d = G.generate_graph(1, 0, "cycle")
        d["expectation"]["codes"] = ["FG_SELF_LINK"]
        self.assertTrue(G.check_graph(d))


class Interface(unittest.TestCase):  # AC-406
    def test_cli_samples_matches_api(self):
        r = run("samples", "--kind", "imu", "--sensor-id", "imu.base", "--count", "6", "--seed", "7",
                "--fault", "2:stale", "--fault", "4:regression")
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = G.dumps(G.generate_samples("imu", "imu.base", 6, 7, faults={2: "stale", 4: "regression"}))
        self.assertEqual(r.stdout, expected)
        doc = json.loads(r.stdout)
        self.assertEqual(set(doc), {"generator_version", "seed", "samples", "expectations"})

    def test_cli_graph_matches_api(self):
        r = run("graph", "--seed", "7", "--extra-frames", "2", "--defect", "multiple_parents")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, G.dumps(G.generate_graph(7, 2, "multiple_parents")))

    def test_cli_writes_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "g.json"
            r = run("graph", "--seed", "1", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "")
            self.assertEqual(out.read_text(encoding="utf-8"), G.dumps(G.generate_graph(1)))

    def test_cli_refusals_exit_2(self):
        bad = [
            ["samples", "--kind", "lidar", "--sensor-id", "a", "--count", "1", "--seed", "1"],
            ["samples", "--kind", "imu", "--sensor-id", "a", "--count", "-1", "--seed", "1"],
            ["samples", "--kind", "imu", "--sensor-id", "a", "--count", "1"],
            ["samples", "--kind", "imu", "--sensor-id", "a", "--count", "1", "--seed", "1", "--fault", "9:stale"],
            ["samples", "--kind", "imu", "--sensor-id", "a", "--count", "2", "--seed", "1", "--fault", "0:melt"],
            ["samples", "--kind", "imu", "--sensor-id", "a", "--count", "2", "--seed", "1", "--step-ns", "0"],
            ["samples", "--kind", "imu", "--sensor-id", "Bad Id", "--count", "1", "--seed", "1"],
            ["graph", "--seed", "1", "--defect", "melt"],
            ["graph", "--seed", "1", "--extra-frames", "101"],
            ["graph", "--seed", "99999999999999999999999"],
            ["frobnicate"],
            [],
        ]
        for args in bad:
            r = run(*args)
            self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
            self.assertEqual(r.stdout, "")

    def test_cli_unwritable_target_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("graph", "--seed", "1", "--out", str(Path(tmp) / "no_such_dir" / "g.json"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("cannot write", r.stderr)


class Boundaries(unittest.TestCase):  # AC-407
    def test_contract_versions_and_schemas_are_unchanged(self):
        self.assertEqual(V.CONTRACT_VERSION, "0.1.0")
        self.assertEqual(FG.FRAME_GRAPH_VERSION, "0.1.0")
        self.assertEqual(sha("contract/sense-sample.schema.json"), SAMPLE_SCHEMA_SHA256)
        self.assertEqual(sha("contract/frame-transform.schema.json"), FRAME_SCHEMA_SHA256)

    def test_generated_documents_carry_the_contract_versions(self):
        d = G.generate_samples("imu", "imu.a", 1, 1)
        self.assertEqual(d["samples"][0]["contract_version"], V.CONTRACT_VERSION)
        self.assertEqual(G.generate_graph(1)["graph"]["contract_version"], FG.FRAME_GRAPH_VERSION)

    def test_standard_library_only(self):
        src = (ROOT / "src/kritva_sense/generator.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            if line.startswith(("import ", "from ")):
                mod = line.split()[1]
                self.assertIn(mod, {"argparse", "json", "math", "sys", ".", "frame_graph", "validator"}, line)
        self.assertNotIn("import random", src)

    def test_generator_version_is_documented(self):
        doc = (ROOT / "src/kritva_sense/GENERATOR.md").read_text(encoding="utf-8")
        self.assertIn("Generator version: " + G.GENERATOR_VERSION, doc)
        for name in list(G.SAMPLE_FAULTS) + list(G.GRAPH_DEFECTS):
            self.assertIn("`%s`" % name, doc)


if __name__ == "__main__":
    unittest.main()
