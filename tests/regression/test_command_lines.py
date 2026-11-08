"""REG-06 to REG-11: the documented exit codes, diagnostics and options of the five command lines and the version
command (AC-1004). Each case runs the command in a fresh directory and compares the exit code, the standard output
(byte for byte, by SHA-256), the first line of the standard error and the files written with the golden record.

The golden record is regenerated only by scripts/regenerate_regression_golden.py. The documented exit codes are also
asserted here directly, so that a regenerated golden file cannot silently change the meaning of an exit code.
"""
import unittest

import regression_support as R

DOCUMENTED_EXIT = {          # case id -> the exit code its documentation promises
    "validate.conformant": 0, "validate.not_conformant": 1, "validate.no_argument": 2, "validate.two_arguments": 2,
    "validate.missing_file": 2, "validate.not_json": 2,
    "frame_graph.conformant": 0, "frame_graph.not_conformant": 1, "frame_graph.resolve": 0,
    "frame_graph.resolve_unknown_frame": 1, "frame_graph.no_argument": 2, "frame_graph.three_arguments": 2,
    "frame_graph.missing_file": 2,
    "stream.conformant": 0, "stream.not_conformant": 1, "stream.no_argument": 2, "stream.missing_file": 2,
    "stream.not_json": 2,
    "generator.samples": 0, "generator.samples_with_fault": 0, "generator.samples_utc_clock_world_frame": 0,
    "generator.samples_to_file": 0, "generator.graph": 0, "generator.graph_with_defect": 0,
    "generator.no_command": 2, "generator.unknown_kind": 2, "generator.bad_fault": 2, "generator.negative_count": 2,
    "conformance.list_cases": 0, "conformance.reference": 0, "conformance.mutant": 1,
    "conformance.unknown_argument": 2, "conformance.bad_seed": 2, "conformance.list_cases_with_output": 2,
    "conformance.unknown_mutant": 2,
    "version.print": 0, "version.check": 0, "version.bad_option": 2,
}
READ_ERROR_PREFIX = {"validate": "cannot read sample: ", "frame_graph": "cannot read frame graph: ",
                     "stream": "cannot read stream: "}


class Family:
    """The shared check; a subclass names its family and its regression case."""
    FAMILY = None

    def test_every_case_matches_the_golden_record(self):
        golden = R.load_golden("command_lines.json")
        expected = {c[0] for c in R.COMMAND_CASES if c[1] == self.FAMILY}
        self.assertTrue(expected, self.FAMILY)
        self.assertEqual({k for k in golden if k.split(".")[0] == self.FAMILY}, expected,
                         "the golden record and the case table list different cases")
        current = R.collect_command_lines(self.FAMILY)
        for case_id in sorted(expected):
            with self.subTest(case=case_id):
                self.assertEqual(current[case_id], golden[case_id])

    def test_documented_exit_codes_and_no_traceback(self):
        current = R.collect_command_lines(self.FAMILY)
        for case_id, record in sorted(current.items()):
            with self.subTest(case=case_id):
                self.assertEqual(record["exit"], DOCUMENTED_EXIT[case_id])
                self.assertFalse(record["traceback"])
                if record["exit"] == 2:
                    self.assertNotEqual(record["stderr_first_line"], "", "an exit 2 explains itself on standard error")
                    self.assertEqual(record["stdout_bytes"], 0, "an exit 2 writes nothing to standard output")
                    prefix = READ_ERROR_PREFIX.get(self.FAMILY)
                    if prefix and case_id.endswith(("missing_file", "not_json")):
                        self.assertTrue(record["stderr_first_line"].startswith(prefix), record["stderr_first_line"])


class Reg06ValidateCommand(Family, unittest.TestCase):
    REGRESSION = "REG-06"
    FAMILY = "validate"


class Reg07FrameGraphCommand(Family, unittest.TestCase):
    REGRESSION = "REG-07"
    FAMILY = "frame_graph"


class Reg08StreamCommand(Family, unittest.TestCase):
    REGRESSION = "REG-08"
    FAMILY = "stream"


class Reg09GeneratorCommand(Family, unittest.TestCase):
    REGRESSION = "REG-09"
    FAMILY = "generator"


class Reg10ConformanceCommand(Family, unittest.TestCase):
    REGRESSION = "REG-10"
    FAMILY = "conformance"


class Reg11VersionCommand(Family, unittest.TestCase):
    REGRESSION = "REG-11"
    FAMILY = "version"


class CaseTable(unittest.TestCase):
    """Not a regression case of its own: keeps the table of cases, the exit-code table and the families in step."""
    REGRESSION = "REG-06"

    def test_every_case_has_a_documented_exit_code_and_a_family(self):
        ids = [c[0] for c in R.COMMAND_CASES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(DOCUMENTED_EXIT))
        self.assertEqual({c[1] for c in R.COMMAND_CASES}, set(R.FAMILIES))
        for case_id, family, *_ in R.COMMAND_CASES:
            self.assertEqual(case_id.split(".")[0], family)


if __name__ == "__main__":
    unittest.main()
