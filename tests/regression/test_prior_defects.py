"""REG-14 to REG-16: the fixed findings F-001, F-002 and F-003 of KOS-SENSE-008 stay fixed (AC-1002).

Each test drives the documented command line, not an internal function, so it stays valid when the code is
reorganised. The mutation record (MUTATION_RECORD.md) shows that each fails on the pre-fix behaviour.
"""
import unittest

import regression_support as R

DEEP = {"array": "[" * 200000, "object": '{"a":' * 100000}
METHODS = ("decide_sample", "decide_stream", "decide_frame")


class Reg14DeepNesting(unittest.TestCase):
    """F-001: JSON nested thousands of levels deep is an unreadable document (exit 2), not a traceback (exit 1)."""
    REGRESSION = "REG-14"

    def test_the_three_commands_report_an_unreadable_document_with_exit_2(self):
        for module, prefix in (("kritva_sense", "cannot read sample"), ("kritva_sense.frame_graph", "cannot read frame graph"),
                               ("kritva_sense.stream", "cannot read stream")):
            for shape, text in DEEP.items():
                with self.subTest(command=module, shape=shape), R.TempDir() as d:
                    (d / "deep.json").write_text(text, encoding="utf-8")
                    r = R.run_module(module, ["deep.json"], d)
                    self.assertEqual(r.returncode, 2, r.stderr[-300:])
                    self.assertEqual(r.stdout, b"")
                    self.assertTrue(r.stderr.decode().startswith(prefix), r.stderr[:120])
                    self.assertNotIn(b"Traceback", r.stderr)


def consumer_source(body):
    return "import sys\n%s\n" % body


class Reg15ConsumerExit(unittest.TestCase):
    """F-002: a consumer that calls sys.exit cannot end the harness with a false pass."""
    REGRESSION = "REG-15"

    def run_consumer(self, source):
        with R.TempDir() as d:
            (d / "leaver.py").write_text(source, encoding="utf-8")
            return R.run_module("kritva_sense.conformance", ["--consumer", "leaver:consumer"], d, extra_path=d)

    def test_exit_zero_at_import_is_a_load_error_not_a_pass(self):
        r = self.run_consumer(consumer_source("sys.exit(0)"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b"")
        self.assertNotIn(b"Traceback", r.stderr)

    def test_exit_zero_in_a_factory_is_a_load_error_not_a_pass(self):
        r = self.run_consumer(consumer_source("def consumer():\n    sys.exit(0)"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b"")

    def test_exit_zero_when_invoked_fails_the_run_and_does_not_end_it(self):
        body = "class L:\n" + "".join("    def %s(self, *a, **k):\n        sys.exit(0)\n" % m for m in METHODS) + \
               "consumer = L()"
        r = self.run_consumer(consumer_source(body))
        self.assertEqual(r.returncode, 1, r.stderr[-300:])
        self.assertIn(b"NOT_CONFORMANT", r.stdout)
        self.assertNotIn(b"Traceback", r.stderr)


class Reg16GeneratorCountCap(unittest.TestCase):
    """F-003: --count has an upper bound, so a mistyped count is a usage error at once."""
    REGRESSION = "REG-16"
    ARGS = ["samples", "--kind", "range", "--sensor-id", "x", "--seed", "1", "--count"]

    def test_counts_above_the_cap_are_a_usage_error(self):
        from kritva_sense import generator
        self.assertEqual(generator.MAX_COUNT, 1_000_000)
        for count in (generator.MAX_COUNT + 1, 10 ** 9, 10 ** 18):
            with self.subTest(count=count), R.TempDir() as d:
                r = R.run_module("kritva_sense.generator", self.ARGS + [count], d, timeout=30)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, b"")
                self.assertIn(b"count must be at most 1000000", r.stderr)
                self.assertNotIn(b"Traceback", r.stderr)

    def test_the_function_enforces_the_same_cap(self):
        from kritva_sense import generator
        with self.assertRaises(ValueError):
            generator.generate_samples("range", "x", generator.MAX_COUNT + 1, 1)

    def test_a_small_count_still_works(self):
        with R.TempDir() as d:
            r = R.run_module("kritva_sense.generator", self.ARGS + ["3"], d)
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
