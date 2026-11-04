"""INT-06 and INT-07: the synthetic fixture consumer through the conformance harness."""
import json
import unittest

import fixture as F
import helpers as H
from kritva_sense import conformance as C

# The cases the age-limit fault must fail: each needs an age above the limit (CONFORMANCE 1, SENSE_CONTRACT 6).
# sample.sequence.after_freshness is one of them because a sample that is too old and also regresses is STALE_DATA by
# the harness convention, so a consumer that ignores the age limit reports SEQUENCE_REGRESSION instead.
EXPECTED_FAILURES = ["sample.sequence.after_freshness", "sample.stale.far_over_limit", "sample.stale.one_over_limit",
                     "sample.stale.zero_limit_age_one"]


def failed_ids(entry):
    return sorted(r["id"] for r in entry["results"] if r["outcome"] == "FAIL")


class Int06ConformingConsumer(unittest.TestCase):
    SCENARIO = "INT-06"

    def test_module_interface(self):
        result = C.run_consumers({"fixture": F.FixtureConsumer()}, F.SEED)
        entry = result["consumers"][0]
        self.assertEqual(result["verdict"], "CONFORMANT")
        self.assertGreater(result["case_count"], 0)
        self.assertEqual((entry["failed"], entry["passed"]), (0, result["case_count"]))

    def test_command_line(self):
        with H.TempDir() as d:
            out = d / "result.json"
            p = H.run(["-m", "kritva_sense.conformance", "--consumer", "fixture:FixtureConsumer", "--output", out],
                      cwd=d, PYTHONPATH=str(H.HERE) + ":" + str(H.SRC))
            self.assertEqual((p.returncode, p.stderr), (0, ""), p.stdout)
            self.assertEqual(json.loads(out.read_text())["verdict"], "CONFORMANT")

    def test_the_fixture_says_it_is_a_reference_fixture(self):
        self.assertIn("REFERENCE FIXTURE", F.__doc__)
        self.assertIn("not a Mind, Motion or Skill consumer", F.__doc__)
        self.assertIn("not a Mind, Motion or Skill consumer", F.FixtureConsumer.notice)
        self.assertIn("reference fixture", (H.HERE / "SCENARIOS.md").read_text(encoding="utf-8").lower())

    def test_producer_samples_meet_consumer_decisions(self):
        consumer = F.FixtureConsumer()
        samples = F.produce_samples(count=4, faults={2: "stale"})["samples"]
        good = consumer.decide_sample(samples[0], F.NOW_NS, "monotonic", F.MAX_AGE_NS)
        self.assertEqual(good, {"usable": True, "codes": []})
        declared = consumer.decide_sample(samples[2], F.NOW_NS, "monotonic", F.MAX_AGE_NS, previous=samples[1])
        self.assertEqual(declared, {"usable": False, "codes": ["STALE_DATA"]})
        repeat = F.produce_samples(count=3, faults={2: "regression"})["samples"]
        self.assertEqual(consumer.decide_sample(repeat[2], F.NOW_NS, "monotonic", F.MAX_AGE_NS, previous=repeat[1]),
                         {"usable": False, "codes": ["SEQUENCE_REGRESSION"]})


class Int07FaultyConsumer(unittest.TestCase):
    SCENARIO = "INT-07"

    def test_module_interface(self):
        result = C.run_consumers({"faulty": F.FaultyFixtureConsumer()}, F.SEED)
        entry = result["consumers"][0]
        self.assertEqual(result["verdict"], "NOT_CONFORMANT")
        self.assertEqual(failed_ids(entry), EXPECTED_FAILURES)

    def test_command_line_exit_code(self):
        with H.TempDir() as d:
            out = d / "result.json"
            p = H.run(["-m", "kritva_sense.conformance", "--consumer", "fixture:FaultyFixtureConsumer", "--output", out],
                      cwd=d, PYTHONPATH=str(H.HERE) + ":" + str(H.SRC))
            self.assertEqual((p.returncode, p.stderr), (1, ""), p.stdout)
            result = json.loads(out.read_text())
            self.assertEqual(result["verdict"], "NOT_CONFORMANT")
            self.assertEqual(failed_ids(result["consumers"][0]), EXPECTED_FAILURES)


if __name__ == "__main__":
    unittest.main()
