"""Synthetic consumer conformance harness for the Sense contracts (KOS-SENSE-006).

A consumer is an object with three operations (see CONFORMANCE.md):

    decide_sample(sample, now_ns, now_clock, max_age_ns, previous=None) -> {"usable", "codes"}
    decide_stream(document)                                              -> {"conformant", "stream", "samples"}
    decide_frame(graph, source, target)                                  -> {"ok", "transform", "codes"}

The harness feeds a consumer a deterministic case set and compares its decisions with the outcomes written in the
case set. Every expected outcome is a literal derived by hand from a clause of the contracts. The reference
consumer is the implementation under test; it is never asked for an expected result. Standard library only.
It tests the consumer rules of the contracts on synthetic data; it integrates with no real consumer.
"""
import copy
import importlib
import json
import math
import sys

from . import frame_graph as FG
from . import generator as G
from . import stream as S
from . import validator as V

HARNESS_VERSION = "0.1.0"
DEFAULT_SEED = 1
FRAME_TOLERANCE = 1e-9          # absolute, FRAME_GRAPH_CONTRACT section 7

OPERATIONS = ("sample", "stream", "frame")
CONFORMANT = "CONFORMANT"
NOT_CONFORMANT = "NOT_CONFORMANT"

NOW = 10_000_000_000            # the consumer's "now" in the sample cases, ns
MAX_AGE = 100_000_000           # the consumer's age limit in the sample cases, ns
H = 0.7071067811865476          # cos(45 degrees): the quaternion of a 90 degree turn about z is (H, 0, 0, H)


# ---------------------------------------------------------------------------------------------------------
# Case set. Inputs are built with the generator; expected outcomes are literals taken from the contracts.
# ---------------------------------------------------------------------------------------------------------

def _case(cases, cid, operation, clause, inp, expected):
    cases.append({"id": cid, "operation": operation, "clause": clause, "input": inp, "expected": expected})


def _one(seed, sequence=0, ts=NOW, validity="VALID", clock="monotonic", kind="range", sensor="range_front"):
    sample = G.make_sample(kind, sensor, sequence, ts, G.SplitMix64(seed), clock=clock, validity=validity)
    return sample


def _faulty(seed, fault, ts=NOW):
    doc = G.generate_samples("range", "range_front", 1, seed, start_ns=ts, faults={0: fault})
    return doc["samples"][0]


def _sctx(sample, now_ns=NOW, now_clock="monotonic", max_age_ns=MAX_AGE, previous=None):
    return {"sample": sample, "now_ns": now_ns, "now_clock": now_clock, "max_age_ns": max_age_ns,
            "previous": previous}


def _ok():
    return {"usable": True, "codes": []}


def _no(*codes):
    return {"usable": False, "codes": sorted(codes)}


def _sample_cases(cases, seed):
    c6 = "SENSE_CONTRACT 6 (validity and freshness)"
    c61 = "SENSE_CONTRACT 6.1 (checks that need context)"
    c4 = "SENSE_CONTRACT 4 (time)"
    # freshness
    _case(cases, "sample.fresh.age_zero", "sample", c6 + ": a VALID, fresh sample is usable",
          _sctx(_one(seed)), _ok())
    _case(cases, "sample.fresh.within_limit", "sample", c6,
          _sctx(_one(seed, ts=NOW - MAX_AGE // 2)), _ok())
    _case(cases, "sample.fresh.age_equal_to_limit", "sample", c6 + ": an age equal to the limit is fresh",
          _sctx(_one(seed, ts=NOW - MAX_AGE)), _ok())
    _case(cases, "sample.stale.one_over_limit", "sample", c6 + ": an age above the limit is STALE_DATA",
          _sctx(_one(seed, ts=NOW - MAX_AGE - 1)), _no("STALE_DATA"))
    _case(cases, "sample.stale.far_over_limit", "sample", c6,
          _sctx(_one(seed, ts=0)), _no("STALE_DATA"))
    _case(cases, "sample.fresh.zero_limit_zero_age", "sample", c6 + ": limit 0, age 0 is fresh",
          _sctx(_one(seed), max_age_ns=0), _ok())
    _case(cases, "sample.stale.zero_limit_age_one", "sample", c6,
          _sctx(_one(seed, ts=NOW - 1), max_age_ns=0), _no("STALE_DATA"))
    _case(cases, "sample.future.one_ns_ahead", "sample", c6 + ": a sample newer than the consumer's clock is INVALID_TIMESTAMP",
          _sctx(_one(seed, ts=NOW + 1)), _no("INVALID_TIMESTAMP"))
    _case(cases, "sample.clock.monotonic_sample_utc_now", "sample", c61 + ", " + c4 + ": clocks differ",
          _sctx(_one(seed), now_clock="utc"), _no("INVALID_TIMESTAMP"))
    _case(cases, "sample.clock.utc_sample_monotonic_now", "sample", c61 + ", " + c4,
          _sctx(_one(seed, clock="utc"), now_clock="monotonic"), _no("INVALID_TIMESTAMP"))
    _case(cases, "sample.clock.utc_fresh", "sample", c4 + ": the same clock is compared (utc)",
          _sctx(_one(seed, clock="utc"), now_clock="utc"), _ok())
    # declared validity and its precedence over freshness
    _case(cases, "sample.declared.stale_fresh_age", "sample", c6 + ": declared STALE is STALE_DATA even when the age is fresh",
          _sctx(_one(seed, validity="STALE")), _no("STALE_DATA"))
    _case(cases, "sample.declared.missing", "sample", c6 + ": declared MISSING is MISSING_DATA",
          _sctx(_one(seed, validity="MISSING")), _no("MISSING_DATA"))
    _case(cases, "sample.declared.invalid", "sample", c6 + ": declared INVALID is INVALID_DATA",
          _sctx(_one(seed, validity="INVALID")), _no("INVALID_DATA"))
    _case(cases, "sample.precedence.declared_stale_before_future", "sample",
          c61 + ": a declared state decides before freshness (future timestamp)",
          _sctx(_one(seed, ts=NOW + 5, validity="STALE")), _no("STALE_DATA"))
    _case(cases, "sample.precedence.declared_invalid_before_clock", "sample",
          c61 + ": a declared state decides before freshness (clock mismatch)",
          _sctx(_one(seed, validity="INVALID"), now_clock="utc"), _no("INVALID_DATA"))
    _case(cases, "sample.precedence.declared_missing_before_age", "sample",
          c61 + ": a declared state decides before freshness (old sample)",
          _sctx(_one(seed, ts=0, validity="MISSING")), _no("MISSING_DATA"))
    # non-conformant samples: rejected with the structural error, freshness not evaluated
    for fault, code in (("bad_unit", "INVALID_UNIT"), ("unknown_frame", "UNKNOWN_FRAME"),
                        ("missing_measurement", "MISSING_FIELD"), ("bad_timestamp", "INVALID_TIMESTAMP"),
                        ("bad_version", "UNSUPPORTED_CONTRACT_VERSION")):
        _case(cases, "sample.structural.%s" % fault, "sample",
              c61 + ": a non-conformant sample is rejected with its structural error",
              _sctx(_faulty(seed, fault)), _no(code))
    _case(cases, "sample.structural.before_age", "sample",
          c61 + ": structural errors come before freshness (old sample with a bad unit)",
          _sctx(_faulty(seed, "bad_unit", ts=0)), _no("INVALID_UNIT"))
    _case(cases, "sample.structural.before_future", "sample",
          c61 + ": structural errors come before freshness (future sample with a bad unit)",
          _sctx(_faulty(seed, "bad_unit", ts=NOW + 5)), _no("INVALID_UNIT"))
    bad_decl = _faulty(seed, "bad_unit")
    bad_decl["validity"], bad_decl["error_code"] = "STALE", "STALE_DATA"
    _case(cases, "sample.structural.before_declared", "sample",
          c61 + ": structural errors come before the declared state",
          _sctx(bad_decl), _no("INVALID_UNIT"))
    _case(cases, "sample.structural.not_an_object", "sample", "SENSE_CONTRACT 3 (a sample is an object)",
          _sctx([1, 2, 3]), _no("MALFORMED_FIELD"))
    _case(cases, "sample.valid.boundary_numbers", "sample", "SENSE_CONTRACT 3, 4: extreme but valid numbers are usable",
          _sctx(G.generate_samples("range", "range_front", 2, seed, faults={1: "boundary"})["samples"][1],
                now_ns=G.MAX_BOUNDARY_TS), _ok())
    # sequence context
    prev = _one(seed, sequence=5, ts=NOW - 20_000_000)
    for cid, seq, expected, why in (
            ("sample.sequence.next", 6, _ok(), "an increasing sequence is usable"),
            ("sample.sequence.gap_is_conformant", 9, _ok(), "a jump ahead is conformant: the contract only requires an increase"),
            ("sample.sequence.equal", 5, _no("SEQUENCE_REGRESSION"), "a sequence that does not increase is SEQUENCE_REGRESSION"),
            ("sample.sequence.lower", 4, _no("SEQUENCE_REGRESSION"), "a lower sequence is SEQUENCE_REGRESSION")):
        _case(cases, cid, "sample", c61 + ": " + why, _sctx(_one(seed, sequence=seq), previous=prev), expected)
    conv = ("CONFORMANCE 1 (interface convention, not a contract clause: the contracts do not fix where sequence "
            "continuity falls; this harness evaluates it last)")
    _case(cases, "sample.sequence.after_freshness", "sample", conv + ": stale and regressing is STALE_DATA",
          _sctx(_one(seed, sequence=5, ts=NOW - MAX_AGE - 1), previous=prev), _no("STALE_DATA"))
    _case(cases, "sample.sequence.after_declared_state", "sample", conv + ": declared STALE and regressing is STALE_DATA",
          _sctx(_one(seed, sequence=5, validity="STALE"), previous=prev), _no("STALE_DATA"))
    _case(cases, "sample.sequence.after_structure", "sample", conv + ": a non-conformant regressing sample gets its structural error",
          _sctx(_faulty(seed, "bad_unit"), previous=_one(seed, sequence=7, ts=NOW - 20_000_000)), _no("INVALID_UNIT"))
    _case(cases, "sample.sequence.no_previous", "sample", c61 + ": without a previous sample continuity is not evaluated",
          _sctx(_one(seed, sequence=0), previous=None), _ok())
    _case(cases, "sample.sequence.other_sensor_independent", "sample",
          c61 + ": samples of different sensors are independent",
          _sctx(_one(seed, sequence=1, sensor="range_rear"), previous=prev), _ok())
    _case(cases, "sample.sequence.other_sensor_equal_independent", "sample", c61,
          _sctx(_one(seed, sequence=5, sensor="range_rear"), previous=prev), _ok())


# --- streams ---------------------------------------------------------------------------------------------

def _open(first=None, sensor="range_front", kind="range", clock="monotonic"):
    rec = {"record": "open", "stream_id": "stream_a", "sensor_id": sensor, "kind": kind, "clock": clock}
    if first is not None:
        rec["first_sequence"] = first
    return rec


def _close(last=None):
    rec = {"record": "close"}
    if last is not None:
        rec["last_sequence"] = last
    return rec


def _doc(records, version="0.1.0"):
    out = []
    for i, rec in enumerate(records):
        rec = dict(rec)
        rec["index"] = i
        out.append(rec)
    return {"stream_version": version, "records": out}


def _sr(sample):
    return {"record": "sample", "sample": sample}


def _stream_samples(seed, count=4, faults=None, start_sequence=0):
    return G.generate_samples("range", "range_front", count, seed, start_sequence=start_sequence,
                              start_ns=1_000_000_000, faults=faults)["samples"]


def _full(samples, first=None, last=None):
    return _doc([_open(first=first)] + [_sr(s) for s in samples] + [_close(last=last)])


def _sx(stream=(), samples=()):
    return {"conformant": not stream and not samples, "stream": [list(p) for p in sorted(stream)],
            "samples": [list(p) for p in sorted(samples)]}


def _stream_cases(cases, seed):
    c5 = "STREAM_CONTRACT 5 (lifecycle)"
    c6 = "STREAM_CONTRACT 6 (sequence)"
    c7 = "STREAM_CONTRACT 7 (timestamps and identity)"
    c8 = "STREAM_CONTRACT 8 (samples)"
    ok = _sx()
    base = _stream_samples(seed)
    _case(cases, "stream.valid.four_samples", "stream", c5 + ": open, samples, close is conformant", _full(base), ok)
    _case(cases, "stream.valid.no_samples", "stream", c5 + ": zero samples are allowed", _doc([_open(), _close()]), ok)
    _case(cases, "stream.valid.bounds_met", "stream", c6 + ": stated first and last sequence match",
          _full(base, first=0, last=3), ok)
    _case(cases, "stream.valid.no_bounds_no_inference", "stream",
          c6 + ": without bounds the checker never infers a missing first sample",
          _full(_stream_samples(seed, start_sequence=5)), ok)
    _case(cases, "stream.valid.equal_timestamps", "stream", c7 + ": an equal timestamp is not a regression",
          _full(_with(base, 2, ts=base[1]["timestamp"]["value"])), ok)
    _case(cases, "stream.valid.declared_states_are_conformant", "stream",
          c8 + ": STALE, MISSING and INVALID samples are conformant and not diagnostics",
          _full(_stream_samples(seed, faults={1: "stale", 2: "missing", 3: "invalid"})), ok)
    # lifecycle
    _case(cases, "stream.lifecycle.empty", "stream", c5 + ": no open record at all (empty stream)",
          _doc([]), _sx(stream=[(-1, "STREAM_OPEN_MISSING")]))
    _case(cases, "stream.lifecycle.unterminated", "stream", c5 + ": a stream without a close record is unterminated",
          _doc([_open()] + [_sr(s) for s in base]), _sx(stream=[(-1, "STREAM_UNTERMINATED")]))
    _case(cases, "stream.lifecycle.no_open", "stream", c5 + ": records before any open record",
          _doc([_sr(base[0]), _sr(base[1]), _close()]),
          _sx(stream=[(-1, "STREAM_OPEN_MISSING"), (0, "STREAM_SAMPLE_BEFORE_OPEN"),
                      (1, "STREAM_SAMPLE_BEFORE_OPEN"), (2, "STREAM_CLOSE_BEFORE_OPEN")]))
    _case(cases, "stream.lifecycle.open_not_first", "stream", c5 + ": an open record at a later position",
          _doc([_sr(base[0]), _open(), _sr(base[1]), _close()]),
          _sx(stream=[(0, "STREAM_SAMPLE_BEFORE_OPEN"), (1, "STREAM_OPEN_NOT_FIRST")]))
    _case(cases, "stream.lifecycle.open_repeated", "stream", c5 + ": a second open record",
          _doc([_open(), _sr(base[0]), _open(), _sr(base[1]), _close()]),
          _sx(stream=[(2, "STREAM_OPEN_REPEATED")]))
    _case(cases, "stream.lifecycle.sample_after_close", "stream", c5 + ": a sample after the close record",
          _doc([_open(), _sr(base[0]), _close(), _sr(base[1])]),
          _sx(stream=[(3, "STREAM_SAMPLE_AFTER_CLOSE")]))
    _case(cases, "stream.lifecycle.close_repeated", "stream", c5 + ": a second close record",
          _doc([_open(), _sr(base[0]), _close(), _close()]),
          _sx(stream=[(3, "STREAM_CLOSE_REPEATED")]))
    # sequence
    _case(cases, "stream.sequence.gap", "stream", c6 + ": c > p + 1 is STREAM_SEQUENCE_GAP",
          _full(_with(base[:3], 2, sequence=5)), _sx(stream=[(3, "STREAM_SEQUENCE_GAP")]))
    _case(cases, "stream.sequence.gap_from_generator", "stream", c6 + ": a gap made by the generator",
          _full(_stream_samples(seed, count=5, faults={2: "gap"})), _sx(stream=[(3, "STREAM_SEQUENCE_GAP")]))
    _case(cases, "stream.sequence.duplicate", "stream", c6 + ": c == p is STREAM_SEQUENCE_DUPLICATE",
          _full(_with(base[:3], 2, sequence=1)), _sx(stream=[(3, "STREAM_SEQUENCE_DUPLICATE")]))
    _case(cases, "stream.sequence.regression", "stream", c6 + ": c < p is STREAM_SEQUENCE_REGRESSION",
          _full(_with(base, 3, sequence=1)), _sx(stream=[(4, "STREAM_SEQUENCE_REGRESSION")]))
    _case(cases, "stream.sequence.first_unmet", "stream", c6 + ": first_sequence differs from the first sample",
          _full(base, first=1), _sx(stream=[(1, "STREAM_FIRST_SEQUENCE_UNMET")]))
    _case(cases, "stream.sequence.last_unmet", "stream", c6 + ": last_sequence differs from the last sample",
          _full(base, last=99), _sx(stream=[(5, "STREAM_LAST_SEQUENCE_UNMET")]))
    _case(cases, "stream.sequence.last_bound_without_samples", "stream", c6 + ": a last bound with no sample cannot be met",
          _doc([_open(), _close(last=0)]), _sx(stream=[(1, "STREAM_LAST_SEQUENCE_UNMET")]))
    # timestamps and identity
    _case(cases, "stream.timestamp.regression", "stream", c7 + ": a lower timestamp than the previous sample",
          _full(_with(base, 2, ts=base[0]["timestamp"]["value"])), _sx(stream=[(3, "STREAM_TIMESTAMP_REGRESSION")]))
    other_clock = _with(base, 2)
    other_clock[2]["timestamp"]["clock"] = "utc"
    _case(cases, "stream.clock.mismatch", "stream", c7 + ": a sample clock that differs from the stream clock",
          _full(other_clock), _sx(stream=[(3, "STREAM_CLOCK_MISMATCH")]))
    _case(cases, "stream.identity.sensor_change", "stream", c7 + ": a different sensor_id than the open record",
          _full(_with(base, 2, sensor_id="range_rear")), _sx(stream=[(3, "STREAM_SENSOR_CHANGE")]))
    changed = _with(base, 2)
    changed[2] = G.make_sample("temperature", "range_front", base[2]["sequence"], base[2]["timestamp"]["value"],
                               G.SplitMix64(seed))
    _case(cases, "stream.identity.kind_change", "stream", c7 + ": a different kind than the open record",
          _full(changed), _sx(stream=[(3, "STREAM_KIND_CHANGE")]))
    both = _with(base[:3], 2, sequence=5)
    both[2]["timestamp"]["clock"] = "utc"
    _case(cases, "stream.combination.gap_and_clock", "stream", c7 + ": independent defects of one record are each reported",
          _full(both), _sx(stream=[(3, "STREAM_CLOCK_MISMATCH"), (3, "STREAM_SEQUENCE_GAP")]))
    # samples and document
    _case(cases, "stream.sample.bad_unit", "stream", c8 + ": a sample violation keeps its contract 0.1.0 code",
          _full(_stream_samples(seed, faults={2: "bad_unit"})), _sx(samples=[(3, "INVALID_UNIT")]))
    _case(cases, "stream.document.unsupported_version", "stream", "STREAM_CONTRACT 3 (document)",
          _full(base, ) | {"stream_version": "9.9.9"}, _sx(stream=[(-1, "STREAM_UNSUPPORTED_VERSION")]))
    _case(cases, "stream.document.not_an_object", "stream", "STREAM_CONTRACT 3 (document)",
          [], _sx(stream=[(-1, "STREAM_MALFORMED")]))


def _with(samples, index, ts=None, sequence=None, sensor_id=None):
    out = copy.deepcopy(list(samples))
    if ts is not None:
        out[index]["timestamp"]["value"] = ts
    if sequence is not None:
        out[index]["sequence"] = sequence
    if sensor_id is not None:
        out[index]["sensor_id"] = sensor_id
    return out


# --- frames ----------------------------------------------------------------------------------------------

def _edge(parent, child, t=(0.0, 0.0, 0.0), q=(1.0, 0.0, 0.0, 0.0)):
    return {"parent": parent, "child": child,
            "translation": dict(zip("xyz", t)), "translation_unit": "m",
            "rotation": dict(zip("wxyz", q))}


def _graph(*edges, version="0.1.0"):
    return {"contract_version": version, "transforms": list(edges)}


def _fx(t, q=(1.0, 0.0, 0.0, 0.0)):
    return {"ok": True, "transform": {"translation": dict(zip("xyz", t)), "translation_unit": "m",
                                      "rotation": dict(zip("wxyz", q))}, "codes": []}


def _fno(*codes):
    return {"ok": False, "transform": None, "codes": sorted(codes)}


def _fin(graph, source, target):
    return {"graph": graph, "source": source, "target": target}


def _frame_cases(cases):
    c5 = "FRAME_GRAPH_CONTRACT 5 (convention)"
    c6 = "FRAME_GRAPH_CONTRACT 6 (graph rules)"
    c7 = "FRAME_GRAPH_CONTRACT 7 (resolution)"
    chain = _graph(_edge("world", "base", (1.0, 2.0, 3.0)), _edge("base", "sensor", (0.5, 0.0, 0.0)))
    _case(cases, "frame.resolve.chain_up", "frame", c7 + ": translations compose along the path",
          _fin(chain, "sensor", "world"), _fx((1.5, 2.0, 3.0)))
    _case(cases, "frame.resolve.chain_down_is_inverse", "frame", c7 + ": the reverse lookup is the inverse transform",
          _fin(chain, "world", "sensor"), _fx((-1.5, -2.0, -3.0)))
    turned = _graph(_edge("world", "base", (1.0, 0.0, 0.0), (H, 0.0, 0.0, H)), _edge("base", "sensor", (1.0, 0.0, 0.0)))
    _case(cases, "frame.resolve.rotation_up", "frame", c5 + ": a 90 degree turn about z moves (1, 0, 0) to (0, 1, 0)",
          _fin(turned, "sensor", "world"), _fx((1.0, 1.0, 0.0), (H, 0.0, 0.0, H)))
    _case(cases, "frame.resolve.rotation_down_is_inverse", "frame", c7 + ": inverse of a rotated pose",
          _fin(turned, "world", "sensor"), _fx((-1.0, 1.0, 0.0), (H, 0.0, 0.0, -H)))
    siblings = _graph(_edge("world", "base", (1.0, 0.0, 0.0)), _edge("world", "sensor", (0.0, 2.0, 0.0)))
    _case(cases, "frame.resolve.siblings_via_ancestor", "frame", c7 + ": the path goes through the nearest common ancestor",
          _fin(siblings, "base", "sensor"), _fx((1.0, -2.0, 0.0)))
    local = _graph(_edge("world", "base", (1.0, 2.0, 3.0)), _edge("base", "arm_link", (0.0, 0.0, 0.25)))
    _case(cases, "frame.resolve.graph_local_frame", "frame",
          "FRAME_GRAPH_CONTRACT 4 (a graph-local frame id is valid inside its graph)",
          _fin(local, "arm_link", "world"), _fx((1.0, 2.0, 3.25)))
    _case(cases, "frame.identity.frame_in_graph", "frame", c7 + ": the identity is returned for a frame of the graph to itself",
          _fin(chain, "world", "world"), _fx((0.0, 0.0, 0.0)))
    _case(cases, "frame.identity.graph_local_frame", "frame", c7,
          _fin(local, "arm_link", "arm_link"), _fx((0.0, 0.0, 0.0)))
    _case(cases, "frame.identity.frame_not_in_graph", "frame",
          c7 + ": no identity is invented for a frame the graph does not contain",
          _fin(_graph(_edge("world", "base")), "sensor", "sensor"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    _case(cases, "frame.identity.empty_graph", "frame", c7 + ": an empty graph contains no frame",
          _fin(_graph(), "world", "world"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    # no assumed connection between world, base and sensor
    only_wb = _graph(_edge("world", "base", (1.0, 0.0, 0.0)))
    _case(cases, "frame.connection.sensor_not_in_graph", "frame",
          "SENSE_CONTRACT 5 and FRAME_GRAPH_CONTRACT 6: nothing is assumed about world, base and sensor",
          _fin(only_wb, "base", "sensor"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    _case(cases, "frame.connection.world_not_in_graph", "frame", "SENSE_CONTRACT 5",
          _fin(_graph(_edge("base", "sensor")), "sensor", "world"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    _case(cases, "frame.connection.missing_frame", "frame", c7 + ": a frame without a transform in the graph",
          _fin(chain, "world", "ghost"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    _case(cases, "frame.connection.both_missing", "frame", c7,
          _fin(chain, "ghost", "phantom"), _fno("FG_FRAME_NOT_IN_GRAPH"))
    split = _graph(_edge("world", "base", (1.0, 0.0, 0.0)), _edge("sensor", "tool", (0.0, 0.0, 0.1)))
    _case(cases, "frame.connection.disconnected", "frame", c7 + ": frames in different components have no path",
          _fin(split, "world", "sensor"), _fno("FG_NO_PATH"))
    _case(cases, "frame.connection.disconnected_other_pair", "frame", c7,
          _fin(split, "tool", "base"), _fno("FG_NO_PATH"))
    _case(cases, "frame.input.invalid_frame_id", "frame", c7 + ": a source or target must be a frame id",
          _fin(chain, "World", "base"), _fno("FG_INVALID_FRAME_ID"))
    _case(cases, "frame.input.frame_not_a_string", "frame", c7,
          _fin(chain, None, "base"), _fno("FG_MALFORMED"))
    # a non-conformant graph resolves nothing
    cycle = _graph(_edge("world", "base"), _edge("base", "sensor"), _edge("sensor", "world"))
    _case(cases, "frame.graph.cycle", "frame", c6 + ": rule 3, no cycle; a non-conformant graph resolves nothing",
          _fin(cycle, "base", "world"), _fno("FG_CYCLE"))
    twice = _graph(_edge("world", "base"), _edge("world", "base"))
    _case(cases, "frame.graph.duplicate_edge", "frame", c6 + ": rule 1, no duplicate pair",
          _fin(twice, "base", "world"), _fno("FG_DUPLICATE_EDGE"))
    two_parents = _graph(_edge("world", "base"), _edge("base", "sensor"), _edge("world", "sensor"))
    _case(cases, "frame.graph.multiple_parents", "frame",
          c6 + ": rule 2, at most one parent; no partial graph is resolved",
          _fin(two_parents, "base", "world"), _fno("FG_MULTIPLE_PARENTS"))
    _case(cases, "frame.graph.non_unit_rotation", "frame", c5 + ": the rotation must be a unit quaternion",
          _fin(_graph(_edge("world", "base", q=(2.0, 0.0, 0.0, 0.0))), "base", "world"), _fno("FG_NOT_UNIT_QUATERNION"))
    _case(cases, "frame.graph.unsupported_version", "frame", "FRAME_GRAPH_CONTRACT 3 (document)",
          _fin(_graph(_edge("world", "base"), version="9.9.9"), "base", "world"), _fno("FG_UNSUPPORTED_VERSION"))


def build_cases(seed=DEFAULT_SEED):
    """The case set for a seed: a list of cases sorted by id. The seed changes only the generated measurement
    values of the inputs; case ids, clauses and expected outcomes do not depend on it."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be an integer >= 0")
    cases = []
    _sample_cases(cases, seed)
    _stream_cases(cases, seed)
    _frame_cases(cases)
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate case id")
    return sorted(cases, key=lambda c: c["id"])


# ---------------------------------------------------------------------------------------------------------
# Reference consumer (the implementation under test) and mutants
# ---------------------------------------------------------------------------------------------------------

_DECLARED = {"MISSING": "MISSING_DATA", "STALE": "STALE_DATA", "INVALID": "INVALID_DATA"}


def _unusable(codes):
    return {"usable": False, "codes": sorted(set(codes))}


class ReferenceConsumer:
    """Implements the consumer rules of the accepted contracts. The steps are separate methods so that the
    mutants below can break exactly one rule."""

    def decide_sample(self, sample, now_ns, now_clock, max_age_ns, previous=None):
        return self._decide(sample, (
            lambda: self._structural(sample), lambda: self._declared(sample),
            lambda: self._freshness(sample, now_ns, now_clock, max_age_ns), lambda: self._sequence(previous, sample)))

    @staticmethod
    def _decide(sample, steps):
        for step in steps:                                # in order; a later step never sees a rejected sample
            codes = step()
            if codes:
                return _unusable(codes)
        return {"usable": True, "codes": []}

    def decide_stream(self, document):
        result = S.check_stream(document)
        return {"conformant": result.conformant,
                "stream": [[d.position, d.code] for d in result.stream],
                "samples": [[v.position, v.code] for v in result.samples]}

    def decide_frame(self, graph, source, target):
        transform, codes = self._resolve(graph, source, target)
        if transform is None:
            return {"ok": False, "transform": None, "codes": sorted(set(codes))}
        return {"ok": True, "transform": transform, "codes": []}

    # steps
    def _structural(self, sample):
        return [v.code for v in V.validate_sample(sample)]

    def _declared(self, sample):
        return [_DECLARED[sample["validity"]]] if sample["validity"] in _DECLARED else []

    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        if now_ns is None or now_clock is None or max_age_ns is None:
            return []                                  # SENSE_CONTRACT 6.1: absent context, not evaluated
        if now_clock != sample["timestamp"]["clock"]:
            return ["INVALID_TIMESTAMP"]
        age = now_ns - sample["timestamp"]["value"]
        if age < 0:
            return ["INVALID_TIMESTAMP"]
        if age > max_age_ns:
            return ["STALE_DATA"]
        return []

    def _sequence(self, previous, sample):
        if not isinstance(previous, dict) or not isinstance(previous.get("sequence"), int):
            return []
        if previous.get("sensor_id") != sample["sensor_id"]:
            return []
        return ["SEQUENCE_REGRESSION"] if sample["sequence"] <= previous["sequence"] else []

    def _resolve(self, graph, source, target):
        transform, violations = FG.resolve(graph, source, target)
        return transform, [v.code for v in violations]


_IDENTITY_TRANSFORM = {"translation": {"x": 0.0, "y": 0.0, "z": 0.0}, "translation_unit": "m",
                       "rotation": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}}


class _M(ReferenceConsumer):
    pass


class _FreshnessLimitExclusive(_M):          # an age equal to the limit is wrongly stale
    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        if now_clock == sample["timestamp"]["clock"] and 0 <= now_ns - sample["timestamp"]["value"] >= max_age_ns:
            return ["STALE_DATA"]
        return super()._freshness(sample, now_ns, now_clock, max_age_ns)


class _ClockIgnored(_M):                      # compares values across clocks
    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        return super()._freshness(sample, now_ns, sample["timestamp"]["clock"], max_age_ns)


class _FutureAccepted(_M):                    # a sample from the future counts as fresh
    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        if now_clock == sample["timestamp"]["clock"] and now_ns - sample["timestamp"]["value"] < 0:
            return []
        return super()._freshness(sample, now_ns, now_clock, max_age_ns)


class _FreshnessBeforeDeclared(_M):           # freshness decides before the declared state
    def decide_sample(self, sample, now_ns, now_clock, max_age_ns, previous=None):
        return self._decide(sample, (
            lambda: self._structural(sample), lambda: self._freshness(sample, now_ns, now_clock, max_age_ns),
            lambda: self._declared(sample), lambda: self._sequence(previous, sample)))


class _StructureUnchecked(_M):                # trusts a conformant-looking sample without validating it
    def _structural(self, sample):
        return [] if isinstance(sample, dict) and "validity" in sample else super()._structural(sample)


class _DeclaredStaleIgnored(_M):              # a producer-declared STALE sample is used when its age is fresh
    def _declared(self, sample):
        return [] if sample["validity"] == "STALE" else super()._declared(sample)


class _SequenceEqualAccepted(_M):             # a repeated sequence number is accepted
    def _sequence(self, previous, sample):
        if isinstance(previous, dict) and previous.get("sensor_id") == sample["sensor_id"] \
                and sample["sequence"] == previous["sequence"]:
            return []
        return super()._sequence(previous, sample)


class _SequenceIgnoresSensor(_M):             # compares sequences of different sensors
    def _sequence(self, previous, sample):
        if isinstance(previous, dict) and isinstance(previous.get("sequence"), int):
            return ["SEQUENCE_REGRESSION"] if sample["sequence"] <= previous["sequence"] else []
        return []


class _SequenceBeforeFreshness(_M):           # sequence continuity decided before freshness
    def decide_sample(self, sample, now_ns, now_clock, max_age_ns, previous=None):
        return self._decide(sample, (
            lambda: self._structural(sample), lambda: self._declared(sample),
            lambda: self._sequence(previous, sample), lambda: self._freshness(sample, now_ns, now_clock, max_age_ns)))


class _SequenceGapRejected(_M):               # a jump ahead is wrongly rejected
    def _sequence(self, previous, sample):
        if isinstance(previous, dict) and previous.get("sensor_id") == sample["sensor_id"] \
                and sample["sequence"] > previous["sequence"] + 1:
            return ["SEQUENCE_REGRESSION"]
        return super()._sequence(previous, sample)


def _restream(decision, drop=(), rename=None):
    rename = rename or {}
    stream = [[p, rename.get(c, c)] for p, c in decision["stream"] if c not in drop]
    return {"conformant": not stream and not decision["samples"], "stream": stream, "samples": decision["samples"]}


class _StreamGapIgnored(_M):                  # gaps are never reported
    def decide_stream(self, document):
        return _restream(super().decide_stream(document), drop=("STREAM_SEQUENCE_GAP",))


class _StreamGapAsRegression(_M):             # a gap is reported as a regression
    def decide_stream(self, document):
        return _restream(super().decide_stream(document), rename={"STREAM_SEQUENCE_GAP": "STREAM_SEQUENCE_REGRESSION"})


class _FrameUnknownGetsIdentity(_M):          # an unknown frame is assumed to coincide with the other one
    def _resolve(self, graph, source, target):
        transform, codes = super()._resolve(graph, source, target)
        if transform is None and "FG_FRAME_NOT_IN_GRAPH" in codes and not set(codes) - {"FG_FRAME_NOT_IN_GRAPH"}:
            return copy.deepcopy(_IDENTITY_TRANSFORM), []
        return transform, codes


class _FrameNoPathGetsIdentity(_M):           # unconnected frames are assumed to be connected
    def _resolve(self, graph, source, target):
        transform, codes = super()._resolve(graph, source, target)
        if transform is None and codes == ["FG_NO_PATH"]:
            return copy.deepcopy(_IDENTITY_TRANSFORM), []
        return transform, codes


class _FrameSelfIdentityUnchecked(_M):        # identity for any frame to itself, in the graph or not
    def _resolve(self, graph, source, target):
        if source == target and isinstance(source, str):
            return copy.deepcopy(_IDENTITY_TRANSFORM), []
        return super()._resolve(graph, source, target)


# name -> (rule class, consumer class, one line of what is wrong)
MUTANTS = {
    "freshness_limit_exclusive": ("freshness", _FreshnessLimitExclusive, "age equal to the limit treated as stale"),
    "freshness_clock_ignored": ("freshness", _ClockIgnored, "clock mismatch not detected"),
    "freshness_future_accepted": ("freshness", _FutureAccepted, "sample newer than now treated as fresh"),
    "precedence_freshness_first": ("validity_precedence", _FreshnessBeforeDeclared, "freshness decided before the declared state"),
    "precedence_structure_unchecked": ("validity_precedence", _StructureUnchecked, "non-conformant sample not rejected"),
    "precedence_declared_stale_ignored": ("validity_precedence", _DeclaredStaleIgnored, "declared STALE sample used when fresh"),
    "sequence_equal_accepted": ("sequence", _SequenceEqualAccepted, "repeated sequence number accepted"),
    "sequence_sensors_mixed": ("sequence", _SequenceIgnoresSensor, "sequences of different sensors compared"),
    "sequence_before_freshness": ("sequence", _SequenceBeforeFreshness, "sequence decided before freshness (interface convention)"),
    "sequence_gap_rejected": ("sequence", _SequenceGapRejected, "gap in the sequence rejected as a regression"),
    "stream_gap_ignored": ("stream_gap_handling", _StreamGapIgnored, "sequence gaps never reported"),
    "stream_gap_as_regression": ("stream_gap_handling", _StreamGapAsRegression, "sequence gap reported as a regression"),
    "frame_unknown_gets_identity": ("frame_identity_assumption", _FrameUnknownGetsIdentity, "identity invented for an unknown frame"),
    "frame_no_path_gets_identity": ("frame_identity_assumption", _FrameNoPathGetsIdentity, "unconnected frames assumed connected"),
    "frame_self_identity_unchecked": ("frame_identity_assumption", _FrameSelfIdentityUnchecked, "identity for a frame not in the graph"),
}
RULE_CLASSES = ("freshness", "validity_precedence", "sequence", "stream_gap_handling", "frame_identity_assumption")


# ---------------------------------------------------------------------------------------------------------
# Running a consumer
# ---------------------------------------------------------------------------------------------------------

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _codes(value, allowed):
    if not isinstance(value, (list, tuple)) or not all(isinstance(c, str) and c in allowed for c in value):
        return None
    return sorted(set(value))


def _pairs(value, allowed):
    if not isinstance(value, (list, tuple)):
        return None
    out = []
    for p in value:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not _is_int(p[0]) \
                or not isinstance(p[1], str) or p[1] not in allowed:
            return None
        out.append([p[0], p[1]])
    return sorted(out)


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _norm_sample(d):
    if not isinstance(d, dict) or set(d) != {"usable", "codes"} or not isinstance(d["usable"], bool):
        return None
    codes = _codes(d["codes"], V.ERROR_CODES)
    if codes is None or d["usable"] != (not codes):
        return None
    return {"usable": d["usable"], "codes": codes}


def _norm_stream(d):
    if not isinstance(d, dict) or set(d) != {"conformant", "stream", "samples"} or not isinstance(d["conformant"], bool):
        return None
    stream = _pairs(d["stream"], S.STREAM_ERROR_CODES)
    samples = _pairs(d["samples"], V.ERROR_CODES)
    if stream is None or samples is None or d["conformant"] != (not stream and not samples):
        return None
    return {"conformant": d["conformant"], "stream": stream, "samples": samples}


def _norm_transform(t):
    if not isinstance(t, dict) or set(t) != {"translation", "translation_unit", "rotation"} or t["translation_unit"] != "m":
        return None
    out = {"translation_unit": "m"}
    for key, names in (("translation", "xyz"), ("rotation", "wxyz")):
        part = t[key]
        if not isinstance(part, dict) or set(part) != set(names) or not all(_finite(part[n]) for n in names):
            return None
        out[key] = {n: float(part[n]) for n in names}
        if any(v == 0 and math.copysign(1.0, v) < 0 for v in out[key].values()):
            return None                                   # negative zero: not canonical (section 7)
    q = out["rotation"]
    if abs(math.sqrt(sum(q[n] ** 2 for n in "wxyz")) - 1.0) > FG.QUAT_TOLERANCE:
        return None                                       # not a unit quaternion (section 5)
    first = next((q[n] for n in "wxyz" if abs(q[n]) >= FG.SIGN_EPSILON), None)
    if first is not None and first < 0:
        return None                                       # sign not canonical (section 7)
    return out


def _norm_frame(d):
    if not isinstance(d, dict) or set(d) != {"ok", "transform", "codes"} or not isinstance(d["ok"], bool):
        return None
    codes = _codes(d["codes"], FG.ERROR_CODES)
    if codes is None:
        return None
    if d["ok"]:
        transform = _norm_transform(d["transform"])
        return {"ok": True, "transform": transform, "codes": []} if transform is not None and not codes else None
    if d["transform"] is not None or not codes:
        return None
    return {"ok": False, "transform": None, "codes": codes}


_NORMALISE = {"sample": _norm_sample, "stream": _norm_stream, "frame": _norm_frame}


def _same(operation, expected, actual):
    if operation != "frame":
        return expected == actual
    if expected["ok"] != actual["ok"] or expected["codes"] != actual["codes"]:
        return False
    if not expected["ok"]:
        return True
    for key in ("translation", "rotation"):
        for n, v in expected["transform"][key].items():
            if abs(v - actual["transform"][key][n]) > FRAME_TOLERANCE:
                return False
    return True


def _call(consumer, case):
    inp = copy.deepcopy(case["input"])               # a consumer cannot damage the inputs of later cases
    if case["operation"] == "sample":
        return consumer.decide_sample(inp["sample"], inp["now_ns"], inp["now_clock"], inp["max_age_ns"],
                                      previous=inp["previous"])
    if case["operation"] == "stream":
        return consumer.decide_stream(inp)
    return consumer.decide_frame(inp["graph"], inp["source"], inp["target"])


def run_case(consumer, case):
    """Run one case. A consumer that raises or returns an undefined decision fails this case only."""
    base = {"id": case["id"], "operation": case["operation"], "clause": case["clause"], "expected": case["expected"]}
    try:
        decision = _call(consumer, case)
    except (Exception, SystemExit) as exc:            # noqa: BLE001 - isolation is the point; SystemExit must not end the run
        return dict(base, actual={"error": type(exc).__name__}, outcome="FAIL", reason="consumer raised")
    try:
        actual = _NORMALISE[case["operation"]](decision)
    except (Exception, SystemExit):                   # noqa: BLE001 - a hostile decision object
        actual = None
    if actual is None:
        return dict(base, actual={"undefined_decision": type(decision).__name__}, outcome="FAIL",
                    reason="undefined decision")
    if _same(case["operation"], case["expected"], actual):
        return dict(base, actual=actual, outcome="PASS", reason="")
    return dict(base, actual=actual, outcome="FAIL", reason="decision differs")


def run_consumer(name, consumer, cases):
    results = [run_case(consumer, c) for c in cases]
    failed = sum(1 for r in results if r["outcome"] != "PASS")
    return {"name": name, "verdict": CONFORMANT if not failed else NOT_CONFORMANT,
            "passed": len(results) - failed, "failed": failed, "results": results}


def run_consumers(consumers, seed=DEFAULT_SEED):
    """Run every consumer ({name: consumer}) on the case set for a seed and return the result document.
    Consumers are reported in name order and cases in id order; one consumer's failure never stops another."""
    cases = build_cases(seed)
    entries = [run_consumer(name, consumers[name], cases) for name in sorted(consumers)]
    verdict = CONFORMANT if entries and all(e["verdict"] == CONFORMANT for e in entries) else NOT_CONFORMANT
    return {"harness_version": HARNESS_VERSION, "seed": seed, "case_count": len(cases),
            "consumers": entries, "verdict": verdict}


def dumps(result):
    """Deterministic JSON: sorted keys, two-space indent, one trailing newline."""
    return json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"


# ---------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------

USAGE = ("usage: python3 -m kritva_sense.conformance [--consumer SPEC]... [--seed N] [--output FILE] | [--seed N] --list-cases\n"
         "  SPEC: reference | mutant:NAME | MODULE:ATTR (a consumer object, or a function returning one)\n"
         "  mutants: %s" % ", ".join(sorted(MUTANTS)))

_METHODS = ("decide_sample", "decide_stream", "decide_frame")


def load_consumer(spec):
    """Resolve a consumer spec. Raises ValueError with a message when it cannot be loaded."""
    if spec == "reference":
        return ReferenceConsumer()
    if spec.startswith("mutant:"):
        name = spec[len("mutant:"):]
        if name not in MUTANTS:
            raise ValueError("unknown mutant %r" % name)
        return MUTANTS[name][1]()
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError("%r is not reference, mutant:NAME or MODULE:ATTR" % spec)
    try:
        obj = importlib.import_module(module_name)
        for part in attr.split("."):
            obj = getattr(obj, part)
        if isinstance(obj, type) or (callable(obj) and not all(hasattr(obj, m) for m in _METHODS)):
            obj = obj()                               # a class or a factory: make the consumer
    except (Exception, SystemExit) as exc:            # noqa: BLE001 - a module that calls sys.exit() is a load error
        raise ValueError("cannot load %r: %s: %s" % (spec, type(exc).__name__, exc))
    missing = [m for m in _METHODS if not callable(getattr(obj, m, None))]
    if missing:
        raise ValueError("%r is not a consumer: missing %s" % (spec, ", ".join(missing)))
    return obj


def main(argv):
    args = list(argv[1:])
    specs, seed, output, list_cases = [], DEFAULT_SEED, None, False
    try:
        while args:
            a = args.pop(0)
            if a == "--consumer":
                specs.append(args.pop(0))
            elif a == "--seed":
                text = args.pop(0)
                if not text.isdigit():
                    raise ValueError("--seed needs an integer >= 0")
                seed = int(text)
            elif a == "--output":
                output = args.pop(0)
            elif a == "--list-cases":
                list_cases = True
            else:
                raise ValueError("unknown argument %r" % a)
        if list_cases and (specs or output):
            raise ValueError("--list-cases cannot be combined with --consumer or --output")
        if list_cases:
            for c in build_cases(seed):
                print("%s\t%s\t%s" % (c["id"], c["operation"], c["clause"]))
            return 0
        specs = specs or ["reference"]
        if len(set(specs)) != len(specs):
            raise ValueError("a consumer is named twice")
        consumers = {s: load_consumer(s) for s in specs}
    except (IndexError, ValueError) as exc:
        message = "missing value for the last option" if isinstance(exc, IndexError) else str(exc)
        print("%s\n%s" % (message, USAGE), file=sys.stderr)
        return 2
    text = dumps(run_consumers(consumers, seed))
    if output:
        try:
            with open(output, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print("cannot write result: %s" % exc, file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return 0 if json.loads(text)["verdict"] == CONFORMANT else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
