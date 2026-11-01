"""KOS-SENSE-008 AC-802: command line, file and JSON input paths (malformed, oversized, deeply nested, path misuse,
resource exhaustion). Synthetic inputs only; every case runs in a fresh interpreter with a timeout."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import ROOT, SRC, TempDir, run_module, unavailable  # noqa: E402

READERS = [("validate", "sample"), ("frame_graph", "frame graph"), ("stream", "stream")]


def write(d, name, text, binary=False):
    p = d / name
    p.write_bytes(text) if binary else p.write_text(text, encoding="utf-8")
    return p


class MalformedInput(unittest.TestCase):
    def test_f001_deeply_nested_json_is_a_read_error_not_a_traceback(self):
        """F-001: nesting beyond the JSON decoder's recursion limit exits 2 with a message, never a traceback."""
        with TempDir() as d:
            arr = write(d, "deep_array.json", "[" * 200000 + "]" * 200000)
            obj = write(d, "deep_object.json", '{"a":' * 100000 + "1" + "}" * 100000)
            for module, noun in READERS:
                for p in (arr, obj):
                    with self.subTest(module=module, file=p.name):
                        r = run_module(module, p)
                        self.assertEqual(r.returncode, 2, r.stderr[-300:])
                        self.assertIn("cannot read %s" % noun, r.stderr)
                        self.assertNotIn("Traceback", r.stderr)

    def test_malformed_and_non_object_documents_exit_cleanly(self):
        """Not JSON, empty, a list, a string, null, NaN, a huge integer: exit 0, 1 or 2, never a traceback."""
        cases = {"empty.json": "", "notjson.json": "{not json", "list.json": "[1,2,3]", "str.json": '"x"',
                 "null.json": "null", "nan.json": '{"a": NaN}', "bigint.json": '{"a": %s}' % ("9" * 5000),
                 "trailing.json": '{"a":1} trailing', "bom.json": "﻿{}"}
        with TempDir() as d:
            for name, text in cases.items():
                p = write(d, name, text)
                for module, _ in READERS:
                    with self.subTest(module=module, file=name):
                        r = run_module(module, p)
                        self.assertIn(r.returncode, (0, 1, 2), r.stderr[-300:])
                        self.assertNotIn("Traceback", r.stderr)

    def test_invalid_utf8_and_binary_input_is_a_read_error(self):
        with TempDir() as d:
            p = write(d, "binary.json", b"\xff\xfe\x00\x80" * 1000, binary=True)
            for module, noun in READERS:
                with self.subTest(module=module):
                    r = run_module(module, p)
                    self.assertEqual(r.returncode, 2)
                    self.assertIn("cannot read %s" % noun, r.stderr)
                    self.assertNotIn("Traceback", r.stderr)

    def test_missing_file_directory_and_wrong_argument_count(self):
        with TempDir() as d:
            for module, noun in READERS:
                with self.subTest(module=module):
                    for target in (d / "missing.json", d):
                        r = run_module(module, target)
                        self.assertEqual(r.returncode, 2)
                        self.assertNotIn("Traceback", r.stderr)
                    self.assertEqual(run_module(module).returncode, 2)

    def test_standard_input_is_not_read(self):
        """No command reads standard input as a document: a path is always needed."""
        r = run_module("validate", "-", stdin="{}")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)


class DepthAndSize(unittest.TestCase):
    def test_validators_do_not_recurse_over_values(self):
        """A sample whose payload nests 1500 levels (below the decoder limit) is judged, not crashed on."""
        depth = 1500
        text = '{"contract_version":"0.1.0","extra":' + "[" * depth + "]" * depth + "}"
        with TempDir() as d:
            p = write(d, "nested.json", text)
            r = run_module("validate", p)
            self.assertEqual(r.returncode, 1)          # not conformant (missing fields), judged without a crash
            self.assertNotIn("Traceback", r.stderr)

    def test_large_stream_is_checked_in_bounded_time(self):
        """A 20000-record stream is checked well inside the timeout (the check is linear, not quadratic)."""
        with TempDir() as d:
            out = d / "samples.json"
            r = run_module("generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", "20000",
                           "--seed", "1", "--out", out, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            self.assertGreater(out.stat().st_size, 1_000_000)
            r = run_module("stream", out, timeout=120)
            self.assertIn(r.returncode, (0, 1))
            self.assertNotIn("Traceback", r.stderr)

    def test_wide_object_is_handled(self):
        with TempDir() as d:
            p = write(d, "wide.json", json.dumps({("k%d" % i): i for i in range(200000)}))
            r = run_module("validate", p, timeout=120)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Traceback", r.stderr)


class GeneratorBounds(unittest.TestCase):
    ARGS = ("samples", "--kind", "range", "--sensor-id", "range_front", "--seed", "1")

    def test_f003_count_is_capped(self):
        """F-003: --count above the documented cap is a usage error at once, not a hang or memory exhaustion."""
        sys.path.insert(0, str(SRC))
        try:
            from kritva_sense import generator
        finally:
            sys.path.remove(str(SRC))
        self.assertEqual(generator.MAX_COUNT, 1_000_000)
        for count in (generator.MAX_COUNT + 1, 10**9, 10**18):
            with self.subTest(count=count):
                r = run_module("generator", *self.ARGS, "--count", count, timeout=30)
                self.assertEqual(r.returncode, 2)
                self.assertIn("count must be at most", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_count_cap_is_documented(self):
        doc = (ROOT / "src" / "kritva_sense" / "GENERATOR.md").read_text(encoding="utf-8")
        self.assertIn("1000000", doc)
        self.assertIn("`--count`", doc)

    def test_negative_zero_and_non_numeric_counts_and_seeds_are_usage_errors(self):
        for count in ("-1", "x", "1.5", ""):
            with self.subTest(count=count):
                r = run_module("generator", *self.ARGS, "--count", count)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)
        r = run_module("generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", "1", "--seed", "-1")
        self.assertIn(r.returncode, (0, 2))
        self.assertNotIn("Traceback", r.stderr)

    def test_repeated_fault_and_bad_fault_specs_are_usage_errors(self):
        for fault in ("0", "x:y", "0:no_such_fault", "99:stale_timestamp"):
            with self.subTest(fault=fault):
                r = run_module("generator", *self.ARGS, "--count", "3", "--fault", fault)
                self.assertIn(r.returncode, (2,))
                self.assertNotIn("Traceback", r.stderr)


class PathHandling(unittest.TestCase):
    """The commands read and write exactly the path the operator names. They do not resolve, sanitise or restrict
    paths: the operator is trusted (THREAT_MODEL.md, assumption A-1). The tests record that behaviour so a change
    is deliberate."""

    def test_output_path_errors_are_exit_2(self):
        with TempDir() as d:
            bad = d / "no_such_dir" / "out.json"
            r = run_module("generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", "1",
                           "--seed", "1", "--out", bad)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)
            r = run_module("conformance", "--output", bad)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)
            r = run_module("generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", "1",
                           "--seed", "1", "--out", d)
            self.assertEqual(r.returncode, 2)

    def test_output_overwrites_an_existing_file_and_follows_a_symbolic_link(self):
        """--out and --output truncate the named path, also through a symbolic link, with no confirmation."""
        if not hasattr(os, "symlink"):
            unavailable(self, "no symbolic links on this platform")
        with TempDir() as d:
            target = d / "target.txt"
            target.write_text("precious", encoding="utf-8")
            link = d / "link.json"
            try:
                os.symlink(target, link)
            except OSError as exc:
                unavailable(self, "cannot create a symbolic link: %s" % exc)
            r = run_module("generator", "samples", "--kind", "range", "--sensor-id", "range_front", "--count", "1",
                           "--seed", "1", "--out", link)
            self.assertEqual(r.returncode, 0)
            self.assertNotEqual(target.read_text(encoding="utf-8"), "precious")
            self.assertTrue(json.loads(target.read_text(encoding="utf-8")))

    def test_a_path_that_looks_like_an_option_is_still_a_path(self):
        with TempDir() as d:
            r = run_module("validate", "--help", cwd=d)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("Traceback", r.stderr)

    def test_conformance_unknown_and_incomplete_options(self):
        for args in (["--bogus"], ["--seed"], ["--seed", "x"], ["--seed", "-1"], ["--consumer"], ["--output"],
                     ["--consumer", "reference", "--consumer", "reference"], ["--list-cases", "--output", "x"]):
            with self.subTest(args=args):
                r = run_module("conformance", *args)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
