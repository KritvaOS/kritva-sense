"""REG-12 and REG-13: determinism of the generator and the conformance harness against golden results (AC-1005)."""
import unittest

import regression_support as R


class Reg12GeneratorDeterminism(unittest.TestCase):
    REGRESSION = "REG-12"

    def test_generator_output_equals_the_golden_bytes_for_two_hash_seeds(self):
        golden = R.load_golden("command_lines.json")
        first = R.collect_command_lines("generator", hashseed="1")
        second = R.collect_command_lines("generator", hashseed="2")
        self.assertEqual(first, second, "generator output depends on PYTHONHASHSEED")
        for case_id, record in first.items():
            if record["exit"] == 0:
                with self.subTest(case=case_id):
                    self.assertEqual(record["stdout_sha256"], golden[case_id]["stdout_sha256"])
                    self.assertEqual(record.get("files"), golden[case_id].get("files"))

    def test_the_golden_data_hold_a_successful_run_of_every_generator_mode(self):
        golden = R.load_golden("command_lines.json")
        ok = [k for k, v in golden.items() if k.startswith("generator.") and v["exit"] == 0]
        self.assertGreaterEqual(len(ok), 6)       # samples, faults, clock and frame options, file output, graph, defect


class Reg13ConformanceGolden(unittest.TestCase):
    REGRESSION = "REG-13"

    def test_reference_result_and_every_mutant_verdict_equal_the_golden_data(self):
        golden = R.load_golden("conformance.json")
        current = R.collect_conformance()
        self.assertEqual(current["case_ids"], golden["case_ids"], "the harness case list changed")
        self.assertEqual(current["reference"], golden["reference"])
        self.assertEqual(current["mutants"], golden["mutants"])
        self.assertEqual(current, golden)

    def test_the_reference_consumer_passes_and_every_mutant_is_caught(self):
        golden = R.load_golden("conformance.json")
        self.assertEqual((golden["reference"]["verdict"], golden["reference"]["failed"]), ("CONFORMANT", 0))
        self.assertGreaterEqual(len(golden["mutants"]), 15)
        for name, m in golden["mutants"].items():
            with self.subTest(mutant=name):
                self.assertEqual((m["exit"], m["verdict"]), (1, "NOT_CONFORMANT"))
                self.assertTrue(m["failed_cases"], "a mutant that no case catches is a hole in the case set")


if __name__ == "__main__":
    unittest.main()
