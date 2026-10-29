"""KOS-SENSE-002 unit tests: reference validator against the Sense contract (synthetic data only)."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kritva_sense import validator as V  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def load(group):
    return [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in sorted((FIX / group).glob("*.json"))]


def valid_sample():
    return copy.deepcopy(dict(load("valid"))["imu_valid"]["sample"])


class ValidSamples(unittest.TestCase):  # AC-202
    def test_all_valid_fixtures_pass(self):
        fixtures = load("valid")
        self.assertGreaterEqual(len(fixtures), 4)
        for name, doc in fixtures:
            with self.subTest(name):
                self.assertEqual(V.validate_sample(doc["sample"]), [])

    def test_every_kind_has_a_valid_fixture(self):
        kinds = {doc["sample"]["kind"] for _, doc in load("valid")}
        self.assertEqual(kinds, set(V.KINDS))


class InvalidSamples(unittest.TestCase):  # AC-203
    def test_each_invalid_fixture_is_rejected_with_documented_codes(self):
        fixtures = load("invalid")
        self.assertGreaterEqual(len(fixtures), 20)
        for name, doc in fixtures:
            with self.subTest(name):
                got = sorted({v.code for v in V.validate_sample(doc["sample"])})
                self.assertEqual(got, sorted(doc["expected_codes"]))
                for code in got:
                    self.assertIn(code, V.ERROR_CODES)

    def test_results_are_deterministic(self):
        for _, doc in load("invalid"):
            self.assertEqual(V.validate_sample(doc["sample"]), V.validate_sample(copy.deepcopy(doc["sample"])))

    def test_non_object_sample(self):
        for bad in (None, 5, "x", [], True):
            self.assertEqual([v.code for v in V.validate_sample(bad)], ["MALFORMED_FIELD"])

    def test_multiple_faults_are_all_reported(self):
        s = valid_sample()
        s["sensor_id"] = "BAD ID"
        s["frame_id"] = "map"
        codes = {v.code for v in V.validate_sample(s)}
        self.assertEqual(codes, {"INVALID_SENSOR_ID", "UNKNOWN_FRAME"})


class DataQuality(unittest.TestCase):  # AC-204
    NOW = 2_000_000_000
    MAX_AGE = 500_000_000

    def test_fresh_valid_sample_is_usable(self):
        s = valid_sample()  # timestamp 1_000_000_000
        s["timestamp"]["value"] = 1_800_000_000
        ok, viol = V.usability(s, self.NOW, "monotonic", self.MAX_AGE)
        self.assertTrue(ok)
        self.assertEqual(viol, [])

    def test_old_sample_is_stale(self):
        s = valid_sample()
        ok, viol = V.usability(s, self.NOW, "monotonic", self.MAX_AGE)
        self.assertFalse(ok)
        self.assertEqual([v.code for v in viol], ["STALE_DATA"])

    def test_age_equal_to_limit_is_not_stale(self):
        s = valid_sample()
        s["timestamp"]["value"] = self.NOW - self.MAX_AGE
        self.assertEqual(V.check_freshness(s, self.NOW, "monotonic", self.MAX_AGE), [])

    def test_future_sample_is_invalid_timestamp(self):
        s = valid_sample()
        s["timestamp"]["value"] = self.NOW + 1
        self.assertEqual([v.code for v in V.check_freshness(s, self.NOW, "monotonic", self.MAX_AGE)], ["INVALID_TIMESTAMP"])

    def test_declared_states_map_to_errors(self):
        for name, code in (("missing_declared", "MISSING_DATA"), ("stale_declared", "STALE_DATA"),
                           ("invalid_declared", "INVALID_DATA")):
            with self.subTest(name):
                s = dict(load("valid"))[name]["sample"]
                ok, viol = V.usability(s, self.NOW, "monotonic", self.MAX_AGE)
                self.assertFalse(ok)
                self.assertEqual([v.code for v in viol], [code])

    def test_nonconformant_sample_is_never_usable(self):
        s = valid_sample()
        del s["sensor_id"]
        ok, viol = V.usability(s, self.NOW, "monotonic", self.MAX_AGE)
        self.assertFalse(ok)
        self.assertEqual([v.code for v in viol], ["MISSING_FIELD"])

    def test_clock_mismatch_is_invalid_timestamp_not_fresh(self):
        s = valid_sample()  # monotonic clock
        s["timestamp"]["value"] = self.NOW
        self.assertEqual([v.code for v in V.check_freshness(s, self.NOW, "utc", self.MAX_AGE)], ["INVALID_TIMESTAMP"])
        self.assertEqual([v.code for v in V.check_freshness(s, self.NOW, "gps", self.MAX_AGE)], ["INVALID_TIMESTAMP"])
        ok, viol = V.usability(s, self.NOW, "utc", self.MAX_AGE)
        self.assertFalse(ok)
        self.assertEqual([v.code for v in viol], ["INVALID_TIMESTAMP"])

    def test_context_free_validation_does_not_imply_freshness(self):
        s = valid_sample()
        s["timestamp"]["value"] = 0  # arbitrarily old
        self.assertEqual(V.validate_sample(s), [])
        self.assertEqual([v.code for v in V.check_freshness(s, self.NOW, "monotonic", self.MAX_AGE)], ["STALE_DATA"])

    def test_declared_state_takes_precedence_over_freshness(self):
        s = dict(load("valid"))["stale_declared"]["sample"]
        s = copy.deepcopy(s)
        s["timestamp"]["value"] = self.NOW  # fresh by clock, but producer declared STALE
        ok, viol = V.usability(s, self.NOW, "monotonic", self.MAX_AGE)
        self.assertFalse(ok)
        self.assertEqual([v.code for v in viol], ["STALE_DATA"])

    def test_stale_and_invalid_payloads_carry_every_measurement_of_the_kind(self):
        for name in ("stale_declared", "invalid_declared"):
            with self.subTest(name):
                s = dict(load("valid"))[name]["sample"]
                self.assertEqual(sorted(s["measurements"]), sorted(V.KINDS[s["kind"]]))
        s = copy.deepcopy(dict(load("valid"))["stale_declared"]["sample"])
        del s["measurements"]["gyro_z"]
        self.assertEqual([v.code for v in V.validate_sample(s)], ["MISSING_FIELD"])

    def test_violations_are_ordered_by_path_then_code(self):
        s = valid_sample()
        s["frame_id"] = "map"
        s["sensor_id"] = "BAD ID"
        s["sequence"] = -1
        got = V.validate_sample(s)
        self.assertEqual(got, sorted(got, key=lambda v: (v.path, v.code, v.message)))
        self.assertEqual([v.path for v in got], ["frame_id", "sensor_id", "sequence"])

    def test_freshness_on_nonconformant_sample_is_reported(self):
        s = valid_sample()
        s["frame_id"] = "map"
        self.assertEqual([v.code for v in V.check_freshness(s, self.NOW, "monotonic", self.MAX_AGE)], ["INVALID_DATA"])

    def test_sequence_must_increase_per_sensor(self):
        a, b = valid_sample(), valid_sample()
        b["sequence"] = a["sequence"] + 1
        self.assertEqual(V.check_sequence(a, b), [])
        b["sequence"] = a["sequence"]
        self.assertEqual([v.code for v in V.check_sequence(a, b)], ["SEQUENCE_REGRESSION"])
        b["sequence"] = a["sequence"] - 1
        self.assertEqual([v.code for v in V.check_sequence(a, b)], ["SEQUENCE_REGRESSION"])

    def test_sequence_of_different_sensors_is_independent(self):
        a, b = valid_sample(), valid_sample()
        b["sensor_id"] = "imu.other"
        b["sequence"] = 0
        self.assertEqual(V.check_sequence(a, b), [])


class ContractConsistency(unittest.TestCase):  # AC-201, AC-005 guard
    def test_schema_is_scoped_as_a_structural_subset(self):
        schema = json.loads((ROOT / "contract" / "sense-sample.schema.json").read_text(encoding="utf-8"))
        self.assertIn("Structural subset", schema["description"])
        # Rules the schema cannot express are enforced by the validator, not the schema.
        s = valid_sample()
        s["error_code"] = "STALE_DATA"  # VALID with error_code: schema allows it, validator rejects it
        self.assertEqual([v.code for v in V.validate_sample(s)], ["MALFORMED_FIELD"])
        s = valid_sample()
        s["measurements"]["accel_x"]["unit"] = "g"  # any string is schema-valid; validator rejects the unit
        self.assertEqual([v.code for v in V.validate_sample(s)], ["INVALID_UNIT"])

    def test_schema_mirrors_validator_constants(self):
        schema = json.loads((ROOT / "contract" / "sense-sample.schema.json").read_text(encoding="utf-8"))
        p = schema["properties"]
        self.assertEqual(p["contract_version"]["enum"], list(V.SUPPORTED_VERSIONS))
        self.assertEqual(p["kind"]["enum"], sorted(V.KINDS))
        self.assertEqual(p["frame_id"]["enum"], list(V.FRAMES))
        self.assertEqual(p["validity"]["enum"], list(V.VALIDITY_STATES))
        self.assertEqual(p["error_code"]["enum"], list(V.ERROR_CODES))
        self.assertEqual(p["timestamp"]["properties"]["clock"]["enum"], list(V.CLOCKS))
        self.assertEqual(p["sensor_id"]["pattern"], V.SENSOR_ID_RE.pattern)
        self.assertEqual(sorted(schema["required"]), sorted(V.REQUIRED))

    def test_contract_document_states_the_validator_version_and_codes(self):
        text = (ROOT / "contract" / "SENSE_CONTRACT.md").read_text(encoding="utf-8")
        self.assertIn("Contract version: %s" % V.CONTRACT_VERSION, text)
        for code in V.ERROR_CODES:
            self.assertIn("`%s`" % code, text)
        for kind, spec in V.KINDS.items():
            self.assertIn("`%s`" % kind, text)
            for name, unit in spec.items():
                self.assertIn("`%s`" % name, text)
                self.assertIn("`%s`" % unit, text)

    def test_one_error_code_per_documented_failure_class(self):
        self.assertEqual(len(set(V.ERROR_CODES)), len(V.ERROR_CODES))


if __name__ == "__main__":
    unittest.main()
