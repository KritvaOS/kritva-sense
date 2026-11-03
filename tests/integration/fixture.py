"""Synthetic producer and consumer for the integration scenarios (KOS-SENSE-009).

REFERENCE FIXTURE. This is a synthetic producer and consumer built from the accepted Sense contracts, to exercise the
boundaries between the Sense components. It is not a Mind, Motion or Skill consumer and shows nothing about any real
consumer, sensor or robot. Standard library only; every input is generated from a fixed seed.
"""
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kritva_sense import frame_graph as FG  # noqa: E402
from kritva_sense import generator as G  # noqa: E402
from kritva_sense import stream as S  # noqa: E402
from kritva_sense import validator as V  # noqa: E402

FIXTURE_NOTICE = ("REFERENCE FIXTURE: synthetic producer and consumer built from the accepted Sense contracts; "
                  "not a Mind, Motion or Skill consumer, and it shows nothing about any real consumer.")

SEED = 20260109
START_NS = 1_000_000_000
MAX_AGE_NS = 50_000_000
NOW_NS = START_NS + 40_000_000   # not earlier than the newest of the five generated samples (step 10 ms)


# ---- producer ---------------------------------------------------------------------------------------------

def produce_samples(kind="range", sensor_id="range_front", count=5, seed=SEED, faults=None, **kw):
    """The generator document for a fixed seed (the producer side of every boundary)."""
    kw.setdefault("start_ns", START_NS)
    return G.generate_samples(kind, sensor_id, count, seed, faults=faults, **kw)


def produce_stream(samples, sensor_id="range_front", kind="range", clock="monotonic", first=None, last=None,
                   with_open=True, with_close=True):
    """Wrap samples into a stream document of STREAM_CONTRACT 0.1.0 (record indices are assigned in order)."""
    records = []
    if with_open:
        opening = {"record": "open", "stream_id": "stream_fixture", "sensor_id": sensor_id, "kind": kind, "clock": clock}
        if first is not None:
            opening["first_sequence"] = first
        records.append(opening)
    records.extend({"record": "sample", "sample": s} for s in samples)
    if with_close:
        closing = {"record": "close"}
        if last is not None:
            closing["last_sequence"] = last
        records.append(closing)
    return {"stream_version": "0.1.0", "records": [dict(r, index=i) for i, r in enumerate(records)]}


def produce_graph(seed=SEED, extra_frames=2, defect=None):
    return G.generate_graph(seed, extra_frames=extra_frames, defect=defect)


def write_json(path, doc):
    Path(path).write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return str(path)


# ---- consumer ---------------------------------------------------------------------------------------------

_DECLARED = {"MISSING": "MISSING_DATA", "STALE": "STALE_DATA", "INVALID": "INVALID_DATA"}


class FixtureConsumer:
    """A consumer written from the contract text for this fixture. It is deliberately separate from
    kritva_sense.conformance.ReferenceConsumer, so the harness is not run against its own reference. REFERENCE
    FIXTURE, see FIXTURE_NOTICE."""

    notice = FIXTURE_NOTICE

    def decide_sample(self, sample, now_ns, now_clock, max_age_ns, previous=None):
        codes = sorted({v.code for v in V.validate_sample(sample)})
        if not codes and sample["validity"] in _DECLARED:
            codes = [_DECLARED[sample["validity"]]]
        if not codes:
            codes = self._freshness(sample, now_ns, now_clock, max_age_ns)
        if not codes and previous and previous.get("sensor_id") == sample["sensor_id"] \
                and sample["sequence"] <= previous["sequence"]:
            codes = ["SEQUENCE_REGRESSION"]
        return {"usable": not codes, "codes": codes}

    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        if now_clock != sample["timestamp"]["clock"]:
            return ["INVALID_TIMESTAMP"]
        age = now_ns - sample["timestamp"]["value"]
        if age < 0:
            return ["INVALID_TIMESTAMP"]
        return ["STALE_DATA"] if age > max_age_ns else []

    def decide_stream(self, document):
        result = S.check_stream(document)
        return {"conformant": result.conformant,
                "stream": [[d.position, d.code] for d in result.stream],
                "samples": [[v.position, v.code] for v in result.samples]}

    def decide_frame(self, graph, source, target):
        transform, violations = FG.resolve(graph, source, target)
        if transform is None:
            return {"ok": False, "transform": None, "codes": sorted({v.code for v in violations})}
        return {"ok": True, "transform": transform, "codes": []}


class FaultyFixtureConsumer(FixtureConsumer):
    """Deliberately faulty: it never applies the age limit, so a sample that is too old is used."""

    def _freshness(self, sample, now_ns, now_clock, max_age_ns):
        codes = super()._freshness(sample, now_ns, now_clock, max_age_ns)
        return [c for c in codes if c != "STALE_DATA"]
