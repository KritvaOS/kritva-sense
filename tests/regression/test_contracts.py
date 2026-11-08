"""REG-01 to REG-05: the accepted Sense, frame graph and stream contracts 0.1.0 (AC-1003). Standard library only."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import regression_support as R
from kritva_sense import frame_graph as FG
from kritva_sense import stream as S
from kritva_sense import validator as V

CONTRACT_FILES = {"contract/FRAME_GRAPH_CONTRACT.md", "contract/SENSE_CONTRACT.md", "contract/STREAM_CONTRACT.md",
                  "contract/frame-transform.schema.json", "contract/sense-sample.schema.json",
                  "contract/stream.schema.json"}
CHANGE_RULE = ("A protected file changed. Follow tests/regression/README.md: decide the change centrally, update the "
               "contract version where the rule requires one, add a planning/CHANGELOG.md entry, then update the pin "
               "table in tests/packaging/test_packaging.py and the golden data with "
               "scripts/regenerate_regression_golden.py in the same pull request.")


class Reg01ContractPins(unittest.TestCase):
    REGRESSION = "REG-01"

    def test_every_contract_document_and_schema_is_pinned_and_unchanged(self):
        table = R.pins()
        self.assertEqual({k for k in table if k.startswith("contract/")}, CONTRACT_FILES,
                         "a contract file is missing from the pin table or an unexpected one was added")
        for name in sorted(CONTRACT_FILES):
            with self.subTest(file=name):
                actual = hashlib.sha256((R.ROOT / name).read_bytes()).hexdigest()
                self.assertEqual(actual, table[name], "%s: %s" % (name, CHANGE_RULE))

    def test_the_pin_table_equals_the_golden_copy(self):
        """Changing the pin table alone is not enough: the golden copy must be regenerated in the same change."""
        self.assertEqual(R.pins(), R.load_golden("contract_pins.json"), CHANGE_RULE)

    def test_the_reference_modules_of_the_contracts_are_pinned_and_unchanged(self):
        table = R.pins()
        modules = {k for k in table if k.startswith("src/kritva_sense/")}
        self.assertTrue({"src/kritva_sense/validator.py", "src/kritva_sense/frame_graph.py",
                         "src/kritva_sense/stream.py", "src/kritva_sense/generator.py",
                         "src/kritva_sense/conformance.py"} <= modules)
        for name in sorted(modules):
            with self.subTest(file=name):
                actual = hashlib.sha256((R.ROOT / name).read_bytes()).hexdigest()
                self.assertEqual(actual, table[name], "%s: %s" % (name, CHANGE_RULE))


class Reg02ContractVersions(unittest.TestCase):
    REGRESSION = "REG-02"

    def test_the_three_contracts_declare_version_0_1_0_in_code_documents_and_schemas(self):
        with R.TempDir() as d:
            r = R.run_module("kritva_sense.version", ["--check"], d)
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout.decode().split("\nversions consistent")[0])
        for key in ("sense_contract_version", "frame_graph_contract_version", "stream_contract_version"):
            self.assertEqual(report[key], "0.1.0", key)
        self.assertEqual(set(report["shipped_contract_files"].values()), {"0.1.0"})
        self.assertEqual((V.CONTRACT_VERSION, FG.FRAME_GRAPH_VERSION, S.STREAM_VERSION), ("0.1.0",) * 3)
        self.assertEqual((V.SUPPORTED_VERSIONS, FG.SUPPORTED_VERSIONS), (("0.1.0",), ("0.1.0",)))


class Reg03SenseCases(unittest.TestCase):
    REGRESSION = "REG-03"

    def test_every_sense_fixture_gives_the_golden_violations(self):
        golden = R.load_golden("contract_cases.json")["sense"]
        current = R.collect_contract_cases()["sense"]
        self.assertGreaterEqual(len(golden), 30)
        self.assertEqual(current, golden, "Sense validator behaviour or fixtures changed. " + CHANGE_RULE)

    def test_golden_codes_agree_with_the_hand_written_expectation_inside_each_fixture(self):
        golden = R.load_golden("contract_cases.json")["sense"]
        for name, violations in golden.items():
            doc = json.loads((R.ROOT / name).read_text(encoding="utf-8"))
            with self.subTest(fixture=name):
                if "/invalid/" in name:
                    self.assertEqual(sorted({c for c, _ in violations}), sorted(doc["expected_codes"]))
                else:
                    self.assertEqual(violations, [])


class Reg04FrameGraphCases(unittest.TestCase):
    REGRESSION = "REG-04"

    def test_every_frame_graph_fixture_gives_the_golden_violations(self):
        golden = R.load_golden("contract_cases.json")["frame_graph"]
        current = R.collect_contract_cases()["frame_graph"]
        self.assertGreaterEqual(len(golden), 30)
        self.assertEqual(current, golden, "frame graph behaviour or fixtures changed. " + CHANGE_RULE)

    def test_golden_codes_agree_with_the_hand_written_expectation_inside_each_fixture(self):
        golden = R.load_golden("contract_cases.json")["frame_graph"]
        for name, violations in golden.items():
            doc = json.loads((R.ROOT / name).read_text(encoding="utf-8"))
            with self.subTest(fixture=name):
                if "/invalid/" in name:
                    self.assertEqual(sorted({c for c, _ in violations}), sorted(doc["expected_codes"]))
                else:
                    self.assertEqual(violations, [])


class Reg05StreamCases(unittest.TestCase):
    REGRESSION = "REG-05"

    def test_every_stream_fixture_gives_the_hand_written_diagnostics(self):
        """The golden data of the stream contract are the hand-written tests/stream/fixtures/expected.json; they are
        never regenerated."""
        fixtures = R.ROOT / "tests" / "stream" / "fixtures"
        expected = json.loads((fixtures / "expected.json").read_text(encoding="utf-8"))
        invalid = sorted((fixtures / "invalid").glob("*.json"))
        valid = sorted((fixtures / "valid").glob("*.json"))
        self.assertGreaterEqual(len(invalid), 40)
        self.assertEqual(sorted(p.stem for p in invalid), sorted(expected))
        for p in valid:
            with self.subTest(valid=p.stem):
                self.assertTrue(S.check_stream(json.loads(p.read_text(encoding="utf-8"))).conformant)
        for p in invalid:
            with self.subTest(invalid=p.stem):
                result = S.check_stream(json.loads(p.read_text(encoding="utf-8")))
                self.assertEqual(sorted([d.position, d.code] for d in result.stream), sorted(expected[p.stem]["stream"]))
                self.assertEqual(sorted([d.position, d.code] for d in result.samples), sorted(expected[p.stem]["samples"]))

    def test_the_stream_error_codes_are_the_accepted_set(self):
        expected = json.loads((R.ROOT / "tests" / "stream" / "fixtures" / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual({c for e in expected.values() for _, c in e["stream"]}, set(S.STREAM_ERROR_CODES))


if __name__ == "__main__":
    unittest.main()
