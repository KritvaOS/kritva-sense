"""KOS-SENSE-006 unit tests: consumer conformance harness (synthetic data only)."""
import ast
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kritva_sense import conformance as C  # noqa: E402
from kritva_sense import frame_graph as FG  # noqa: E402
from kritva_sense import stream as S  # noqa: E402
from kritva_sense import validator as V  # noqa: E402

# Everything the harness builds on is pinned (AC-607). A change to any of these files, even wording, is a
# deliberate change: update the pin in the same pull request and record it in planning/CHANGELOG.md.
PINS = {
    "contract/SENSE_CONTRACT.md": "f8935feb9efb10dd482e4b7386239295b2180412dbbcbc177aa7a6f86d75abcf",
    "contract/FRAME_GRAPH_CONTRACT.md": "a3ded6d06222a7f554127c16265e718f350eef58f0550737be425561c6f10210",
    "contract/STREAM_CONTRACT.md": "ac6aafea196224509a673c6f4e71c6a983575a24b816cb794669b17e1ff62bf4",
    "contract/sense-sample.schema.json": "1f6f0824af55237b0b3e90ddd413ddef8c48e2eb3cd19a7f4244295bd2b9bc6b",
    "contract/frame-transform.schema.json": "ae644360dc5ba0e679a9e616022b4261b2e95fe967da8af1e4d440f718a099e2",
    "contract/stream.schema.json": "12f2003ab9144d820ea6f8aeb629e85fcbc888c6933c60060dd49162fee0ff51",
    "src/kritva_sense/validator.py": "cc758f474c21d1963ebbc3c8629a2f59584ce7f463935064f46e5b98061ccaa6",
    "src/kritva_sense/generator.py": "9c2e2dcbaf0f2e643f0e7dc1ba27ab2585c29852f1f44c038596b52591c07c2a",
    "src/kritva_sense/frame_graph.py": "4aef1f86a853bf66582b25471f568c421ed41b17f6f7148e5efdb9e5a2e49a6a",
    "src/kritva_sense/stream.py": "2d8b3bb95f506baf17648c0f9ee5ed6367a57ce6d0e127e788062d0004439c47",
}
DOC = ROOT / "src" / "kritva_sense" / "CONFORMANCE.md"

# the cases each mutant must fail (AC-604): the named case is the reason the mutant exists
MUTANT_MUST_FAIL = {
    "freshness_limit_exclusive": "sample.fresh.age_equal_to_limit",
    "freshness_clock_ignored": "sample.clock.monotonic_sample_utc_now",
    "freshness_future_accepted": "sample.future.one_ns_ahead",
    "precedence_freshness_first": "sample.precedence.declared_stale_before_future",
    "precedence_structure_unchecked": "sample.structural.bad_unit",
    "precedence_declared_stale_ignored": "sample.declared.stale_fresh_age",
    "sequence_equal_accepted": "sample.sequence.equal",
    "sequence_sensors_mixed": "sample.sequence.other_sensor_independent",
    "sequence_before_freshness": "sample.sequence.after_freshness",
    "sequence_gap_rejected": "sample.sequence.gap_is_conformant",
    "stream_gap_ignored": "stream.sequence.gap",
    "stream_gap_as_regression": "stream.sequence.gap",
    "frame_unknown_gets_identity": "frame.connection.missing_frame",
    "frame_no_path_gets_identity": "frame.connection.disconnected",
    "frame_self_identity_unchecked": "frame.identity.frame_not_in_graph",
}


# a control case per mutant: same operation, different rule detail; the mutant must still pass it, which shows it
# fails because of its declared rule and not because it is broken more widely
MUTANT_CONTROL = {
    "freshness_limit_exclusive": "sample.fresh.within_limit",
    "freshness_clock_ignored": "sample.clock.utc_fresh",
    "freshness_future_accepted": "sample.stale.one_over_limit",
    "precedence_freshness_first": "sample.declared.stale_fresh_age",
    "precedence_structure_unchecked": "sample.declared.invalid",
    "precedence_declared_stale_ignored": "sample.declared.missing",
    "sequence_equal_accepted": "sample.sequence.lower",
    "sequence_before_freshness": "sample.sequence.equal",
    "sequence_sensors_mixed": "sample.sequence.next",
    "sequence_gap_rejected": "sample.sequence.next",
    "stream_gap_ignored": "stream.sequence.regression",
    "stream_gap_as_regression": "stream.sequence.duplicate",
    "frame_unknown_gets_identity": "frame.connection.disconnected",
    "frame_no_path_gets_identity": "frame.connection.missing_frame",
    "frame_self_identity_unchecked": "frame.identity.frame_in_graph",
}


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def failed_ids(consumer, seed=1):
    r = C.run_consumers({"c": consumer}, seed)
    return {x["id"] for x in r["consumers"][0]["results"] if x["outcome"] != "PASS"}


def run_cli(*args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, "-m", "kritva_sense.conformance", *args], cwd=ROOT / "src",
                          capture_output=True, text=True, env=e)


class Pins(unittest.TestCase):
    def test_existing_contracts_schemas_and_code_are_unchanged(self):
        for path, digest in PINS.items():
            with self.subTest(path=path):
                self.assertEqual(sha(path), digest, "%s changed; the harness does not change existing files" % path)


class Interface(unittest.TestCase):
    """AC-601: three operations with explicit inputs and decision values equal to the codes of the contracts."""

    def test_documented(self):
        text = DOC.read_text(encoding="utf-8")
        for needle in ("decide_sample", "decide_stream", "decide_frame", "now_ns", "now_clock", "max_age_ns",
                       "previous", "same `sensor_id`", "interface convention", "not a contract clause", "AC-601", "AC-607", "python3 -m kritva_sense.conformance", "make test-unit",
                       "undefined decision", "mutant", "exit 0", "exit 1", "exit 2"):
            self.assertIn(needle, text)

    def test_every_code_documented_exists_in_a_contract(self):
        text = DOC.read_text(encoding="utf-8")
        for code in re.findall(r"`((?:STREAM_|FG_)[A-Z_]+)`", text):
            self.assertIn(code, S.STREAM_ERROR_CODES + FG.ERROR_CODES)

    def test_methods_exist_with_documented_parameters(self):
        import inspect
        ref = C.ReferenceConsumer()
        self.assertEqual(list(inspect.signature(ref.decide_sample).parameters),
                         ["sample", "now_ns", "now_clock", "max_age_ns", "previous"])
        self.assertEqual(list(inspect.signature(ref.decide_stream).parameters), ["document"])
        self.assertEqual(list(inspect.signature(ref.decide_frame).parameters), ["graph", "source", "target"])

    def test_decision_values_are_contract_codes(self):
        r = C.run_consumers({"reference": C.ReferenceConsumer()})
        for res in r["consumers"][0]["results"]:
            a = res["actual"]
            if res["operation"] == "sample":
                self.assertTrue(set(a["codes"]) <= set(V.ERROR_CODES))
            elif res["operation"] == "stream":
                self.assertTrue({c for _, c in a["stream"]} <= set(S.STREAM_ERROR_CODES))
                self.assertTrue({c for _, c in a["samples"]} <= set(V.ERROR_CODES))
            else:
                self.assertTrue(set(a["codes"]) <= set(FG.ERROR_CODES))


class CaseSet(unittest.TestCase):
    """AC-603."""

    def test_ids_unique_sorted_and_complete(self):
        cases = C.build_cases()
        ids = [c["id"] for c in cases]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        for c in cases:
            self.assertEqual(set(c), {"id", "operation", "clause", "input", "expected"})
            self.assertIn(c["operation"], C.OPERATIONS)
            self.assertRegex(c["clause"], r"^(SENSE_CONTRACT|STREAM_CONTRACT|FRAME_GRAPH_CONTRACT|CONFORMANCE) \d")
            if c["clause"].startswith("CONFORMANCE"):
                self.assertIn("not a contract clause", c["clause"])    # a convention is never passed off as a contract clause
            self.assertTrue(c["id"].startswith(c["operation"] + "."))

    def test_expected_values_are_literals_of_the_documented_shape(self):
        for c in C.build_cases():
            norm = C._NORMALISE[c["operation"]](copy.deepcopy(c["expected"]))
            self.assertIsNotNone(norm, c["id"])
            json.dumps(c["expected"], allow_nan=False)

    def test_coverage_of_the_listed_situations(self):
        ids = {c["id"] for c in C.build_cases()}
        need = [
            "sample.fresh.age_zero", "sample.fresh.age_equal_to_limit", "sample.stale.one_over_limit",
            "sample.future.one_ns_ahead", "sample.clock.monotonic_sample_utc_now", "sample.clock.utc_sample_monotonic_now",
            "sample.declared.stale_fresh_age", "sample.declared.missing", "sample.declared.invalid",
            "sample.precedence.declared_stale_before_future", "sample.structural.before_declared",
            "sample.structural.bad_timestamp", "sample.structural.bad_version", "sample.structural.bad_unit",
            "sample.sequence.equal", "sample.sequence.lower", "sample.sequence.gap_is_conformant",
            "sample.sequence.other_sensor_independent", "sample.valid.boundary_numbers",
            "stream.valid.four_samples", "stream.lifecycle.unterminated", "stream.lifecycle.no_open",
            "stream.lifecycle.sample_after_close", "stream.sequence.gap", "stream.sequence.gap_from_generator",
            "stream.sequence.duplicate", "stream.sequence.regression", "stream.timestamp.regression",
            "stream.clock.mismatch", "stream.identity.sensor_change", "stream.identity.kind_change",
            "stream.valid.declared_states_are_conformant", "stream.valid.no_bounds_no_inference",
            "frame.resolve.chain_up", "frame.resolve.chain_down_is_inverse", "frame.resolve.graph_local_frame",
            "frame.connection.missing_frame", "frame.connection.disconnected", "frame.graph.cycle",
            "frame.graph.non_unit_rotation", "frame.identity.frame_in_graph", "frame.identity.frame_not_in_graph",
            "frame.connection.sensor_not_in_graph", "frame.connection.world_not_in_graph",
        ]
        for i in need:
            self.assertIn(i, ids)
        for op in C.OPERATIONS:
            self.assertGreaterEqual(sum(1 for i in ids if i.startswith(op + ".")), 15)

    def test_deterministic_and_seed_changes_only_inputs(self):
        a, b = C.build_cases(1), C.build_cases(1)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        other = C.build_cases(2)
        self.assertEqual([(c["id"], c["clause"], c["expected"]) for c in a],
                         [(c["id"], c["clause"], c["expected"]) for c in other])
        self.assertNotEqual(json.dumps(a, sort_keys=True), json.dumps(other, sort_keys=True))

    def test_seed_is_validated(self):
        for bad in (-1, 1.5, "1", True, None):
            with self.assertRaises(ValueError):
                C.build_cases(bad)

    def test_expected_outcomes_do_not_come_from_any_consumer_or_checker(self):
        """Building the cases must not call the reference consumer, nor the validators the reference relies on."""
        def boom(*a, **k):
            raise AssertionError("the case set called an implementation")
        with mock.patch.object(C.ReferenceConsumer, "decide_sample", boom), \
                mock.patch.object(C.ReferenceConsumer, "decide_stream", boom), \
                mock.patch.object(C.ReferenceConsumer, "decide_frame", boom), \
                mock.patch.object(V, "validate_sample", boom), mock.patch.object(V, "usability", boom), \
                mock.patch.object(V, "check_freshness", boom), mock.patch.object(V, "check_sequence", boom), \
                mock.patch.object(S, "check_stream", boom), mock.patch.object(FG, "resolve", boom), \
                mock.patch.object(FG, "validate_graph", boom):
            self.assertEqual(len(C.build_cases()), len(C.build_cases(3)))

    def test_expected_outcomes_agree_with_the_accepted_implementations(self):
        """A consistency check only, not the oracle: the hand-written literals (derived from the contract text,
        see the audit table in CONFORMANCE.md) agree with the accepted reference code. A shared misreading of a
        contract clause would not show here; the literals stay the authority."""
        for c in C.build_cases():
            i, e = copy.deepcopy(c["input"]), c["expected"]
            with self.subTest(case=c["id"]):
                if c["operation"] == "sample":
                    usable, viol = V.usability(i["sample"], i["now_ns"], i["now_clock"], i["max_age_ns"])
                    codes = sorted({v.code for v in viol})
                    if usable and i["previous"] is not None:
                        viol = V.check_sequence(i["previous"], i["sample"])
                        usable, codes = not viol, sorted({v.code for v in viol})
                    self.assertEqual(e, {"usable": usable, "codes": codes})
                elif c["operation"] == "stream":
                    r = S.check_stream(i)
                    self.assertEqual(e, {"conformant": r.conformant,
                                         "stream": sorted([d.position, d.code] for d in r.stream),
                                         "samples": sorted([v.position, v.code] for v in r.samples)})
                else:
                    tf, viol = FG.resolve(i["graph"], i["source"], i["target"])
                    self.assertEqual(e["ok"], tf is not None)
                    self.assertEqual(e["codes"], sorted({v.code for v in viol}))
                    if tf is not None:
                        for key in ("translation", "rotation"):
                            for n, v in e["transform"][key].items():
                                self.assertAlmostEqual(v, tf[key][n], delta=1e-9)

    def test_boundary_cases_state_the_numbers(self):
        by_id = {c["id"]: c for c in C.build_cases()}
        eq = by_id["sample.fresh.age_equal_to_limit"]["input"]
        self.assertEqual(eq["now_ns"] - eq["sample"]["timestamp"]["value"], eq["max_age_ns"])
        over = by_id["sample.stale.one_over_limit"]["input"]
        self.assertEqual(over["now_ns"] - over["sample"]["timestamp"]["value"], over["max_age_ns"] + 1)
        fut = by_id["sample.future.one_ns_ahead"]["input"]
        self.assertEqual(fut["sample"]["timestamp"]["value"] - fut["now_ns"], 1)


class Reference(unittest.TestCase):
    def test_passes_every_case(self):
        r = C.run_consumers({"reference": C.ReferenceConsumer()})
        entry = r["consumers"][0]
        self.assertEqual([x["id"] for x in entry["results"] if x["outcome"] != "PASS"], [])
        self.assertEqual((entry["verdict"], entry["failed"], entry["passed"]), ("CONFORMANT", 0, r["case_count"]))
        self.assertEqual(r["verdict"], "CONFORMANT")

    def test_passes_for_other_seeds(self):
        for seed in (0, 2, 7, 12345):
            with self.subTest(seed=seed):
                self.assertEqual(C.run_consumers({"r": C.ReferenceConsumer()}, seed)["verdict"], "CONFORMANT")

    def test_does_not_need_freshness_context_when_absent(self):
        ref = C.ReferenceConsumer()
        sample = next(c for c in C.build_cases() if c["id"] == "sample.fresh.age_zero")["input"]["sample"]
        self.assertEqual(ref.decide_sample(sample, None, None, None), {"usable": True, "codes": []})


class Mutants(unittest.TestCase):
    """AC-604."""

    def test_each_rule_class_has_a_mutant(self):
        classes = {rc for rc, _, _ in C.MUTANTS.values()}
        self.assertEqual(classes, set(C.RULE_CLASSES))
        self.assertEqual(set(C.RULE_CLASSES), {"freshness", "validity_precedence", "sequence",
                                                "stream_gap_handling", "frame_identity_assumption"})

    def test_every_mutant_is_listed_with_a_case(self):
        self.assertEqual(set(MUTANT_MUST_FAIL), set(C.MUTANTS))

    def test_every_mutant_has_a_control_case_it_still_passes(self):
        self.assertEqual(set(MUTANT_CONTROL), set(C.MUTANTS))
        for name, (_, cls, _) in sorted(C.MUTANTS.items()):
            with self.subTest(mutant=name):
                failed = failed_ids(cls())
                self.assertIn(MUTANT_CONTROL[name], {c["id"] for c in C.build_cases()})
                self.assertNotIn(MUTANT_CONTROL[name], failed)
                self.assertIn(MUTANT_MUST_FAIL[name], failed)

    def test_each_mutant_fails_its_named_case_and_not_everything(self):
        total = len(C.build_cases())
        for name, (_, cls, why) in sorted(C.MUTANTS.items()):
            with self.subTest(mutant=name):
                self.assertTrue(why)
                failed = failed_ids(cls())
                self.assertIn(MUTANT_MUST_FAIL[name], failed)
                self.assertGreater(len(failed), 0)
                self.assertLess(len(failed), total)

    def test_a_mutant_fails_only_cases_of_its_own_operation(self):
        ops = {"freshness": "sample", "validity_precedence": "sample", "sequence": "sample",
               "stream_gap_handling": "stream", "frame_identity_assumption": "frame"}
        for name, (rc, cls, _) in sorted(C.MUTANTS.items()):
            with self.subTest(mutant=name):
                self.assertTrue(all(i.startswith(ops[rc] + ".") for i in failed_ids(cls())))

    def test_mutants_pass_cases_of_the_other_rule_classes(self):
        # a mutant is wrong in one rule: the rest of the case set must still pass for it
        for name, (_, cls, _) in sorted(C.MUTANTS.items()):
            with self.subTest(mutant=name):
                self.assertLess(len(failed_ids(cls())), 12)

    def test_no_mutant_passes_under_other_seeds(self):
        for seed in (0, 5):
            for name, (_, cls, _) in C.MUTANTS.items():
                self.assertTrue(failed_ids(cls(), seed), name)


class Result(unittest.TestCase):
    """AC-605."""

    def consumers(self):
        d = {"reference": C.ReferenceConsumer()}
        d.update({n: cls() for n, (_, cls, _) in C.MUTANTS.items()})
        return d

    def test_byte_identical_across_runs(self):
        a = C.dumps(C.run_consumers(self.consumers(), 4))
        b = C.dumps(C.run_consumers(self.consumers(), 4))
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("}\n"))

    def test_order_does_not_depend_on_how_consumers_are_given(self):
        d = self.consumers()
        rev = dict(reversed(list(d.items())))
        self.assertEqual(C.dumps(C.run_consumers(d)), C.dumps(C.run_consumers(rev)))

    def test_sorted_keys_and_stable_ordering(self):
        text = C.dumps(C.run_consumers(self.consumers()))
        doc = json.loads(text)
        self.assertEqual(text, json.dumps(doc, sort_keys=True, indent=2) + "\n")
        names = [c["name"] for c in doc["consumers"]]
        self.assertEqual(names, sorted(names))
        for c in doc["consumers"]:
            ids = [r["id"] for r in c["results"]]
            self.assertEqual(ids, sorted(ids))
            for r in c["results"]:
                self.assertEqual(set(r), {"id", "operation", "clause", "expected", "actual", "outcome", "reason"})
                self.assertIn(r["outcome"], ("PASS", "FAIL"))
        self.assertEqual(set(doc), {"harness_version", "seed", "case_count", "consumers", "verdict"})
        self.assertEqual(doc["verdict"], "NOT_CONFORMANT")

    def test_overall_verdict(self):
        ok = C.run_consumers({"a": C.ReferenceConsumer(), "b": C.ReferenceConsumer()})
        self.assertEqual(ok["verdict"], "CONFORMANT")
        mixed = C.run_consumers({"a": C.ReferenceConsumer(), "b": C.MUTANTS["sequence_equal_accepted"][1]()})
        self.assertEqual([c["verdict"] for c in mixed["consumers"]], ["CONFORMANT", "NOT_CONFORMANT"])
        self.assertEqual(mixed["verdict"], "NOT_CONFORMANT")
        self.assertEqual(C.run_consumers({})["verdict"], "NOT_CONFORMANT")

    def test_counts_add_up(self):
        r = C.run_consumers({"m": C.MUTANTS["stream_gap_ignored"][1]()})
        e = r["consumers"][0]
        self.assertEqual(e["passed"] + e["failed"], r["case_count"])
        self.assertEqual(e["failed"], sum(1 for x in e["results"] if x["outcome"] == "FAIL"))


class Isolation(unittest.TestCase):
    """AC-606."""

    class Raises(C.ReferenceConsumer):
        def decide_stream(self, document):
            raise RuntimeError("boom")

    def test_raising_consumer_fails_only_those_cases(self):
        r = C.run_consumers({"raises": self.Raises(), "reference": C.ReferenceConsumer()})
        by = {c["name"]: c for c in r["consumers"]}
        streams = [x for x in by["raises"]["results"] if x["operation"] == "stream"]
        self.assertTrue(streams)
        self.assertTrue(all(x["outcome"] == "FAIL" and x["actual"] == {"error": "RuntimeError"} and
                            x["reason"] == "consumer raised" for x in streams))
        others = [x for x in by["raises"]["results"] if x["operation"] != "stream"]
        self.assertTrue(all(x["outcome"] == "PASS" for x in others))
        self.assertEqual(by["reference"]["verdict"], "CONFORMANT")
        self.assertEqual(by["raises"]["verdict"], "NOT_CONFORMANT")
        self.assertEqual(r["verdict"], "NOT_CONFORMANT")
        self.assertEqual(len(by["raises"]["results"]), r["case_count"])

    def test_exception_message_does_not_enter_the_result(self):
        r = C.run_consumers({"raises": self.Raises()})
        self.assertNotIn("boom", C.dumps(r))

    def test_missing_methods_fail_each_case(self):
        r = C.run_consumers({"empty": object()})
        e = r["consumers"][0]
        self.assertEqual(e["failed"], r["case_count"])
        self.assertTrue(all(x["actual"] == {"error": "AttributeError"} for x in e["results"]))

    def test_undefined_decisions(self):
        bad_sample = [None, 5, "usable", [], {}, {"usable": True}, {"usable": True, "codes": ["STALE_DATA"]},
                      {"usable": False, "codes": []}, {"usable": 1, "codes": []},
                      {"usable": False, "codes": ["NOT_A_CODE"]}, {"usable": False, "codes": "STALE_DATA"},
                      {"usable": True, "codes": [], "extra": 1}]
        bad_stream = [None, {}, {"conformant": True, "stream": [[0, "STREAM_SEQUENCE_GAP"]], "samples": []},
                      {"conformant": False, "stream": [], "samples": []},
                      {"conformant": False, "stream": [[0, "NOPE"]], "samples": []},
                      {"conformant": False, "stream": [["0", "STREAM_SEQUENCE_GAP"]], "samples": []},
                      {"conformant": False, "stream": [[True, "STREAM_SEQUENCE_GAP"]], "samples": []},
                      {"conformant": False, "stream": [[0]], "samples": []}]
        nan = float("nan")
        tf = {"translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "translation_unit": "m",
              "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}}
        bad_frame = [None, {}, {"ok": True, "transform": None, "codes": []},
                     {"ok": True, "transform": dict(tf, translation_unit="cm"), "codes": []},
                     {"ok": True, "transform": dict(tf, translation={"x": nan, "y": 0.0, "z": 0.0}), "codes": []},
                     {"ok": True, "transform": dict(tf, rotation={"w": 1.0}), "codes": []},
                     {"ok": True, "transform": tf, "codes": ["FG_NO_PATH"]},
                     {"ok": False, "transform": tf, "codes": ["FG_NO_PATH"]},
                     {"ok": False, "transform": None, "codes": []},
                     {"ok": False, "transform": None, "codes": ["SOMETHING"]}]
        for op, values in (("sample", bad_sample), ("stream", bad_stream), ("frame", bad_frame)):
            case = next(c for c in C.build_cases() if c["operation"] == op)
            for value in values:
                with self.subTest(op=op, value=repr(value)[:40]):
                    class K:
                        def decide_sample(self, *a, **k):
                            return copy.deepcopy(value)
                        decide_stream = decide_frame = decide_sample
                    res = C.run_case(K(), case)
                    self.assertEqual(res["outcome"], "FAIL")
                    self.assertEqual(res["reason"], "undefined decision")
                    self.assertEqual(res["actual"], {"undefined_decision": type(value).__name__})

    def test_undefined_decision_on_every_case_is_not_conformant_and_serialises(self):
        class K:
            def decide_sample(self, *a, **k):
                return object()
            decide_stream = decide_frame = decide_sample
        r = C.run_consumers({"k": K()})
        self.assertEqual(r["consumers"][0]["failed"], r["case_count"])
        json.loads(C.dumps(r))
        self.assertNotIn("0x", C.dumps(r))

    def test_hostile_decision_object_is_contained(self):
        class Evil(dict):
            def __iter__(self):
                raise RuntimeError("no iteration")
        class K(C.ReferenceConsumer):
            def decide_sample(self, *a, **k):
                return Evil(usable=True, codes=[])
        r = C.run_consumers({"k": K(), "ref": C.ReferenceConsumer()})
        by = {c["name"]: c for c in r["consumers"]}
        self.assertEqual(by["ref"]["verdict"], "CONFORMANT")
        self.assertEqual(by["k"]["verdict"], "NOT_CONFORMANT")

    def test_a_consumer_cannot_damage_the_inputs_of_later_cases(self):
        class Vandal(C.ReferenceConsumer):
            def decide_sample(self, sample, now_ns, now_clock, max_age_ns, previous=None):
                if isinstance(sample, dict):
                    sample.clear()
                if isinstance(previous, dict):
                    previous.clear()
                return super().decide_sample(sample, now_ns, now_clock, max_age_ns, previous)

            def decide_stream(self, document):
                if isinstance(document, dict):
                    document.clear()
                return super().decide_stream(document)

            def decide_frame(self, graph, source, target):
                graph.clear()
                return super().decide_frame(graph, source, target)
        before = json.dumps(C.build_cases(), sort_keys=True)
        r = C.run_consumers({"vandal": Vandal(), "reference": C.ReferenceConsumer()})
        self.assertEqual(json.dumps(C.build_cases(), sort_keys=True), before)
        self.assertEqual({c["name"]: c["verdict"] for c in r["consumers"]}["reference"], "CONFORMANT")

    def test_frame_tolerance(self):
        class Near(C.ReferenceConsumer):
            delta = 0.0

            def decide_frame(self, graph, source, target):
                d = super().decide_frame(graph, source, target)
                if d["ok"]:
                    d["transform"]["translation"]["x"] += self.delta
                return d

        class Close(Near):
            delta = 1e-12

        class Far(Near):
            delta = 1e-6
        self.assertEqual(failed_ids(Close()), set())
        self.assertTrue(all(i.startswith("frame.") for i in failed_ids(Far())))
        self.assertTrue(failed_ids(Far()))

    def test_non_canonical_frame_results_are_undefined(self):
        case = next(c for c in C.build_cases() if c["id"] == "frame.resolve.rotation_down_is_inverse")
        for label, edit in (
                ("non-unit", lambda t: t["rotation"].update(w=1.0, z=-1.0)),
                ("negative sign", lambda t: t["rotation"].update(w=-C.H, z=C.H)),
                ("negative zero", lambda t: t["translation"].update(y=-0.0)),
                ("negative zero rotation", lambda t: t["rotation"].update(x=-0.0)),
                ("unit in the wrong unit", lambda t: t.update(translation_unit="mm"))):
            class K(C.ReferenceConsumer):
                def decide_frame(self, graph, source, target, _edit=edit):
                    d = super().decide_frame(graph, source, target)
                    _edit(d["transform"])
                    return d
            with self.subTest(label=label):
                res = C.run_case(K(), case)
                self.assertEqual((res["outcome"], res["reason"]), ("FAIL", "undefined decision"))

    def test_canonical_form_edge_cases_are_accepted(self):
        # first non-zero component positive, magnitudes below 1e-12 count as zero (FRAME_GRAPH_CONTRACT 7)
        t = {"translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "translation_unit": "m",
             "rotation": {"w": -1e-13, "x": 1.0, "y": 0.0, "z": 0.0}}
        self.assertIsNotNone(C._norm_transform(t))
        t["rotation"] = {"w": 0.0, "x": -1.0, "y": 0.0, "z": 0.0}
        self.assertIsNone(C._norm_transform(t))

    def test_unsorted_but_equal_decisions_pass(self):
        class Shuffled(C.ReferenceConsumer):
            def decide_stream(self, document):
                d = super().decide_stream(document)
                d["stream"] = list(reversed(d["stream"]))
                return d
        self.assertEqual(failed_ids(Shuffled()), set())


class CommandLine(unittest.TestCase):
    """AC-607."""

    def test_reference_exits_0(self):
        p = run_cli()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["verdict"], "CONFORMANT")

    def test_mutant_exits_1(self):
        p = run_cli("--consumer", "mutant:stream_gap_ignored")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertEqual(json.loads(p.stdout)["verdict"], "NOT_CONFORMANT")

    def test_several_consumers_one_run(self):
        p = run_cli("--consumer", "reference", "--consumer", "mutant:sequence_gap_rejected")
        self.assertEqual(p.returncode, 1)
        doc = json.loads(p.stdout)
        self.assertEqual([c["name"] for c in doc["consumers"]], ["mutant:sequence_gap_rejected", "reference"])

    def test_usage_and_load_errors_exit_2(self):
        for args in (["--list-cases", "--consumer", "reference"], ["--list-cases", "--output", "x.json"],
                     ["--bogus"], ["--seed"], ["--seed", "x"], ["--seed", "-1"], ["--consumer"],
                     ["--consumer", "nonsense"], ["--consumer", "mutant:nope"],
                     ["--consumer", "no_such_module_xyz:thing"], ["--consumer", "kritva_sense.conformance:NOPE"],
                     ["--consumer", "kritva_sense.conformance:HARNESS_VERSION"],
                     ["--consumer", "reference", "--consumer", "reference"],
                     ["--output", "/nonexistent_dir_xyz/out.json"]):
            with self.subTest(args=args):
                p = run_cli(*args)
                self.assertEqual(p.returncode, 2, p.stdout[:200])
                self.assertIn("usage:", p.stderr + ("usage:" if "--output" in args else ""))

    def test_named_callable_from_a_module(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "my_consumer.py").write_text(
                "from kritva_sense.conformance import ReferenceConsumer\n"
                "def make():\n    return ReferenceConsumer()\n"
                "OBJECT = ReferenceConsumer()\n"
                "class Mine(ReferenceConsumer):\n    pass\n", encoding="utf-8")
            env = {"PYTHONPATH": d + os.pathsep + str(ROOT / "src")}
            for spec in ("my_consumer:make", "my_consumer:OBJECT", "my_consumer:Mine"):
                with self.subTest(spec=spec):
                    p = run_cli("--consumer", spec, env=env)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(json.loads(p.stdout)["consumers"][0]["name"], spec)

    def test_output_file_matches_stdout_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, "r.json")
            p = run_cli("--seed", "3", "--output", str(out))
            self.assertEqual((p.returncode, p.stdout), (0, ""))
            q = run_cli("--seed", "3")
            self.assertEqual(out.read_text(encoding="utf-8"), q.stdout)

    def test_byte_identical_across_processes(self):
        self.assertEqual(run_cli("--consumer", "mutant:freshness_limit_exclusive").stdout,
                         run_cli("--consumer", "mutant:freshness_limit_exclusive").stdout)

    def test_seed_is_recorded(self):
        self.assertEqual(json.loads(run_cli("--seed", "9").stdout)["seed"], 9)

    def test_list_cases(self):
        p = run_cli("--list-cases")
        self.assertEqual(p.returncode, 0)
        lines = p.stdout.splitlines()
        self.assertEqual(len(lines), len(C.build_cases()))
        self.assertTrue(all(len(l.split("\t")) == 3 for l in lines))

    def test_list_cases_accepts_a_seed(self):
        self.assertEqual(run_cli("--list-cases", "--seed", "4").returncode, 0)

    def test_a_broken_consumer_module_does_not_exit_0(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "broken_consumer.py").write_text(
                "class K:\n    def decide_sample(self, *a, **k):\n        raise ValueError('x')\n"
                "    decide_stream = decide_frame = decide_sample\nOBJ = K()\n", encoding="utf-8")
            p = run_cli("--consumer", "broken_consumer:OBJ", env={"PYTHONPATH": d + os.pathsep + str(ROOT / "src")})
            self.assertEqual(p.returncode, 1)
            self.assertEqual(json.loads(p.stdout)["consumers"][0]["failed"], len(C.build_cases()))


class Packaging(unittest.TestCase):
    def test_standard_library_only(self):
        tree = ast.parse((ROOT / "src/kritva_sense/conformance.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [] if node.level else [node.module.split(".")[0]]
            else:
                continue
            for n in names:
                self.assertIn(n, sys.stdlib_module_names)

    def test_make_test_unit_runs_these_tests(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s tests/conformance", makefile)

    def test_no_real_consumer_dependency(self):
        text = (ROOT / "src/kritva_sense/conformance.py").read_text(encoding="utf-8")
        for word in ("kritva_mind", "kritva_motion", "kritva_skill", "rclpy", "requests"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
