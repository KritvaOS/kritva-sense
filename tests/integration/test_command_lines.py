"""INT-08 to INT-10: the command lines chained as documented, failure propagation and determinism."""
import json
import unittest

import fixture as F
import helpers as H
from kritva_sense import frame_graph as FG
from kritva_sense import stream as S
from kritva_sense import validator as V

LAUNCHERS = {"kritva-sense-validate": "validate", "kritva-sense-frame-graph": "frame_graph",
             "kritva-sense-generator": "generator", "kritva-sense-stream": "stream",
             "kritva-sense-conformance": "conformance"}


def cli(tool, *args, cwd, **kw):
    return H.run(["-m", tool, *args], cwd=cwd, **kw)


def generate_samples(cwd, *extra, count=5, **kw):
    p = cli("kritva_sense.generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", count,
            "--seed", F.SEED, "--start-ns", F.START_NS, *extra, cwd=cwd, **kw)
    return p


class Int08CommandLinesChained(unittest.TestCase):
    SCENARIO = "INT-08"

    def test_generator_output_is_read_by_the_validator_command(self):
        with H.TempDir() as d:
            p = generate_samples(d, "--fault", "2:bad_unit")
            self.assertEqual((p.returncode, p.stderr), (0, ""))
            samples = json.loads(p.stdout)["samples"]
            for i, sample in enumerate(samples):
                path = F.write_json(d / ("sample_%d.json" % i), sample)
                q = cli("kritva_sense", path, cwd=d)
                expected = V.validate_sample(sample)
                self.assertEqual(q.returncode, 1 if expected else 0, i)
                self.assertEqual(q.stdout.splitlines(),
                                 ["%s %s: %s" % (v.code, v.path, v.message) for v in expected]
                                 + ["not conformant" if expected else "conformant"], i)
            self.assertEqual([i for i, s in enumerate(samples) if V.validate_sample(s)], [2])

    def test_generated_stream_is_read_by_the_stream_command(self):
        with H.TempDir() as d:
            for faults, rc in (((), 0), (("--fault", "2:gap"), 1)):
                p = generate_samples(d, *faults)
                doc = F.produce_stream(json.loads(p.stdout)["samples"])
                q = cli("kritva_sense.stream", F.write_json(d / "stream.json", doc), cwd=d)
                result = S.check_stream(doc)
                self.assertEqual(q.returncode, rc)
                self.assertEqual(q.returncode == 0, result.conformant)
                self.assertEqual(q.stdout.splitlines()[-1], "conformant" if rc == 0 else "not conformant")
            self.assertIn("STREAM_SEQUENCE_GAP record 3", q.stdout)

    def test_generated_graph_is_read_by_the_frame_graph_command(self):
        with H.TempDir() as d:
            p = cli("kritva_sense.generator", "graph", "--seed", F.SEED, "--extra-frames", 2, cwd=d)
            self.assertEqual((p.returncode, p.stderr), (0, ""))
            graph = json.loads(p.stdout)["graph"]
            path = F.write_json(d / "graph.json", graph)
            q = cli("kritva_sense.frame_graph", path, "world", "link_2", cwd=d)
            self.assertEqual(q.returncode, 0, q.stdout)
            transform, _ = FG.resolve(graph, "world", "link_2")
            self.assertEqual(json.loads(q.stdout.rsplit("conformant", 1)[0]), transform)
            bad = cli("kritva_sense.generator", "graph", "--seed", F.SEED, "--defect", "cycle", cwd=d)
            q = cli("kritva_sense.frame_graph", F.write_json(d / "bad.json", json.loads(bad.stdout)["graph"]), cwd=d)
            self.assertEqual(q.returncode, 1)
            self.assertIn("FG_CYCLE", q.stdout)

    def test_console_script_launchers_behave_like_the_modules(self):
        with H.TempDir() as d:
            scripts = {name: H.launcher(d, name, fn) for name, fn in LAUNCHERS.items()}
            version = H.launcher(d, "kritva-sense-version", "main")
            version.write_text("import sys\nfrom kritva_sense.version import main\nsys.exit(main())\n", encoding="utf-8")
            sample = F.write_json(d / "sample.json", F.produce_samples(count=1)["samples"][0])
            doc = F.produce_stream(F.produce_samples(count=3)["samples"])
            graph = F.write_json(d / "graph.json", F.produce_graph()["graph"])
            runs = {
                "kritva-sense-validate": ([sample], 0, "conformant"),
                "kritva-sense-stream": ([F.write_json(d / "stream.json", doc)], 0, "conformant"),
                "kritva-sense-frame-graph": ([graph, "world", "sensor"], 0, "conformant"),
                "kritva-sense-generator": (["samples", "--kind", "range", "--sensor-id", "range_front", "--count", "2",
                                           "--seed", "1"], 0, '"samples"'),
                "kritva-sense-conformance": (["--list-cases"], 0, "sample."),
            }
            for name, (args, rc, needle) in runs.items():
                p = H.run([scripts[name], *args], cwd=d)
                self.assertEqual((p.returncode, p.stderr), (rc, ""), name)
                self.assertIn(needle, p.stdout, name)
            p = H.run([version, "--check"], cwd=d)
            self.assertEqual((p.returncode, p.stderr), (0, ""), p.stdout)


class Int09FailurePropagation(unittest.TestCase):
    SCENARIO = "INT-09"

    TOOLS = (("kritva_sense", 2), ("kritva_sense.stream", 2), ("kritva_sense.frame_graph", 2))

    def assert_clean_failure(self, p, rc, label):
        self.assertEqual(p.returncode, rc, label)
        self.assertNotIn("Traceback", p.stdout + p.stderr, label)

    def test_missing_file_is_a_read_error(self):
        with H.TempDir() as d:
            for tool, rc in self.TOOLS:
                p = cli(tool, d / "absent.json", cwd=d)
                self.assert_clean_failure(p, rc, tool)
                self.assertEqual(p.stdout, "", tool)
                self.assertIn("cannot read", p.stderr, tool)

    def test_input_that_is_not_json_is_a_read_error(self):
        with H.TempDir() as d:
            (d / "junk.json").write_text("{not json", encoding="utf-8")
            for tool, rc in self.TOOLS:
                p = cli(tool, d / "junk.json", cwd=d)
                self.assert_clean_failure(p, rc, tool)
                self.assertEqual(p.stdout, "", tool)
                self.assertIn("cannot read", p.stderr, tool)

    def test_wrong_argument_count_is_a_usage_error(self):
        with H.TempDir() as d:
            for tool, _ in self.TOOLS:
                p = cli(tool, cwd=d)
                self.assert_clean_failure(p, 2, tool)
                self.assertIn("usage", p.stderr, tool)
                self.assertEqual(p.stdout, "", tool)

    def test_non_conformant_documents_are_exit_1_with_the_documented_code(self):
        with H.TempDir() as d:
            bad_sample = produce_bad_sample()
            p = cli("kritva_sense", F.write_json(d / "s.json", bad_sample), cwd=d)
            self.assert_clean_failure(p, 1, "validate")
            self.assertIn("INVALID_UNIT", p.stdout)
            doc = F.produce_stream(F.produce_samples(count=3)["samples"], with_close=False)
            p = cli("kritva_sense.stream", F.write_json(d / "st.json", doc), cwd=d)
            self.assert_clean_failure(p, 1, "stream")
            self.assertIn("STREAM_UNTERMINATED", p.stdout)
            graph = F.produce_graph(defect="multiple_parents")["graph"]
            p = cli("kritva_sense.frame_graph", F.write_json(d / "g.json", graph), cwd=d)
            self.assert_clean_failure(p, 1, "frame_graph")
            self.assertIn("FG_MULTIPLE_PARENTS", p.stdout)

    def test_unknown_frame_is_exit_1_not_an_identity(self):
        with H.TempDir() as d:
            graph = F.write_json(d / "g.json", F.produce_graph()["graph"])
            p = cli("kritva_sense.frame_graph", graph, "world", "nowhere", cwd=d)
            self.assert_clean_failure(p, 1, "unknown frame")
            self.assertIn("FG_FRAME_NOT_IN_GRAPH", p.stdout)
            self.assertNotIn('"translation"', p.stdout)

    def test_inapplicable_generator_fault_writes_nothing(self):
        with H.TempDir() as d:
            p = generate_samples(d, "--fault", "9:stale")
            self.assert_clean_failure(p, 2, "generator")
            self.assertEqual(p.stdout, "")
            self.assertNotEqual(p.stderr, "")

    def test_a_faulty_consumer_that_cannot_load_is_a_load_error(self):
        with H.TempDir() as d:
            p = cli("kritva_sense.conformance", "--consumer", "no_such_module:Thing", cwd=d)
            self.assert_clean_failure(p, 2, "conformance")


def produce_bad_sample():
    return F.produce_samples(count=3, faults={1: "bad_unit"})["samples"][1]


class Int10Determinism(unittest.TestCase):
    SCENARIO = "INT-10"

    def chain(self, d, hashseed):
        g = generate_samples(d, "--fault", "2:gap", PYTHONHASHSEED=hashseed)
        doc = F.produce_stream(json.loads(g.stdout)["samples"])
        st = cli("kritva_sense.stream", F.write_json(d / "stream.json", doc), cwd=d, PYTHONHASHSEED=hashseed)
        out = d / ("result_%s.json" % hashseed)
        h = cli("kritva_sense.conformance", "--consumer", "fixture:FixtureConsumer", "--output", out, cwd=d,
                PYTHONHASHSEED=hashseed, PYTHONPATH=str(H.HERE) + ":" + str(H.SRC))
        return g.stdout, st.stdout, st.returncode, out.read_text(), h.returncode

    def test_the_chain_is_byte_identical_across_runs(self):
        with H.TempDir() as d:
            first = self.chain(d, "0")
            second = self.chain(d, "12345")
        self.assertEqual(first, second)
        self.assertEqual((first[2], first[4]), (1, 0))


if __name__ == "__main__":
    unittest.main()
