"""Reference validator of the Sense telemetry stream contract (contract/STREAM_CONTRACT.md).

It implements the stream contract; it never defines or alters it, and it does not change the Sense data
contract 0.1.0: every embedded sample is validated by the unchanged `validator.validate_sample`. Standard library
only. Software behaviour on synthetic data only: no transport, clock source or sensor is involved.

Results are deterministic: stream diagnostics and sample violations are each sorted by
(position, code, path, message), where position is the 0-based record position (-1 for the document as a whole).

    python3 -m kritva_sense.stream FILE.json      validate a stream document
Exit 0 conformant, 1 not conformant, 2 usage or read error.
"""
import json
import sys
from collections import namedtuple

from .validator import CLOCKS, KINDS, SENSOR_ID_RE, TIMESTAMP_UNIT, validate_sample

STREAM_VERSION = "0.1.0"
SUPPORTED_VERSIONS = (STREAM_VERSION,)

STREAM_ERROR_CODES = (
    "STREAM_MALFORMED",
    "STREAM_MISSING_FIELD",
    "STREAM_UNKNOWN_FIELD",
    "STREAM_UNSUPPORTED_VERSION",
    "STREAM_UNKNOWN_RECORD",
    "STREAM_INDEX_MISMATCH",
    "STREAM_OPEN_MISSING",
    "STREAM_OPEN_NOT_FIRST",
    "STREAM_OPEN_REPEATED",
    "STREAM_SAMPLE_BEFORE_OPEN",
    "STREAM_SAMPLE_AFTER_CLOSE",
    "STREAM_CLOSE_BEFORE_OPEN",
    "STREAM_CLOSE_REPEATED",
    "STREAM_UNTERMINATED",
    "STREAM_SEQUENCE_DUPLICATE",
    "STREAM_SEQUENCE_REGRESSION",
    "STREAM_SEQUENCE_GAP",
    "STREAM_FIRST_SEQUENCE_UNMET",
    "STREAM_LAST_SEQUENCE_UNMET",
    "STREAM_TIMESTAMP_REGRESSION",
    "STREAM_CLOCK_MISMATCH",
    "STREAM_SENSOR_CHANGE",
    "STREAM_KIND_CHANGE",
)

RECORD_KINDS = ("open", "sample", "close")
DOCUMENT_FIELDS = ("stream_version", "records")
# record kind -> (required fields, optional fields); `record` and `index` are required for every kind
RECORD_FIELDS = {
    "open": (("record", "index", "stream_id", "sensor_id", "kind", "clock"), ("first_sequence",)),
    "sample": (("record", "index", "sample"), ()),
    "close": (("record", "index"), ("last_sequence",)),
}
STREAM_ID_RE = SENSOR_ID_RE

StreamDiagnostic = namedtuple("StreamDiagnostic", "position code path message")
SampleViolation = namedtuple("SampleViolation", "position code path message")


class StreamResult:
    """Stream diagnostics (STREAM_ codes) and sample violations (contract 0.1.0 codes), kept apart."""

    def __init__(self, stream, samples):
        self.stream = sorted(stream, key=_key)
        self.samples = sorted(samples, key=_key)

    @property
    def conformant(self):
        return not self.stream and not self.samples

    def __repr__(self):
        return "StreamResult(stream=%r, samples=%r)" % (self.stream, self.samples)


def _key(d):
    return (d.position, d.code, d.path, d.message)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_seq(v):
    return _is_int(v) and v >= 0


class StreamChecker:
    """Incremental checker. `feed` takes the next records in order, in batches of any size; `finish` ends the
    stream. The same ordered records give the same result for every split into batches. A new checker treats its
    first record as position 0, so a batch checked alone is a complete stream of its own."""

    def __init__(self):
        self._position = 0
        self._finished = False
        self._state = "NONE"          # NONE (no open yet), OPEN, CLOSED
        self._have_open = False
        self._ident = {}              # valid identity fields fixed by the first open record
        self._first_bound = None
        self._open_samples = 0        # sample records seen while the stream was open
        self._last_open_seq = None    # sequence of the latest of them when usable, else None
        self._prev_seq = None
        self._prev_ts = None          # (clock, value) of the latest sample with a usable timestamp
        self._stream = []
        self._samples = []

    # -- public ---------------------------------------------------------------------------------------------
    def feed(self, records):
        if self._finished:
            raise ValueError("the stream is finished; no more records can be fed")
        if not isinstance(records, (list, tuple)):
            raise ValueError("records must be a list")
        before = (len(self._stream), len(self._samples))
        for rec in records:
            self._record(rec)
        return StreamResult(self._stream[before[0]:], self._samples[before[1]:])

    def finish(self):
        if self._finished:
            raise ValueError("the stream is already finished")
        before = (len(self._stream), len(self._samples))
        self._finished = True
        if not self._have_open:
            self._add(-1, "STREAM_OPEN_MISSING", "records", "the stream has no open record")
        elif self._state != "CLOSED":
            self._add(-1, "STREAM_UNTERMINATED", "records", "the stream has no close record; it is not repaired")
            if self._first_bound is not None and self._open_samples == 0:
                self._add(-1, "STREAM_FIRST_SEQUENCE_UNMET", "records",
                          "first_sequence %d was stated but no sample followed the open record" % self._first_bound)
        return StreamResult(self._stream[before[0]:], self._samples[before[1]:])

    def result(self):
        return StreamResult(self._stream, self._samples)

    # -- internals ------------------------------------------------------------------------------------------
    def _add(self, position, code, path, message):
        self._stream.append(StreamDiagnostic(position, code, path, message))

    def _record(self, rec):
        pos = self._position
        self._position += 1
        path = "records[%d]" % pos
        if not isinstance(rec, dict):
            self._add(pos, "STREAM_MALFORMED", path, "a record must be an object")
            return
        kind = None
        if "record" not in rec:
            self._add(pos, "STREAM_MISSING_FIELD", path + ".record", "required field is absent")
        elif not isinstance(rec["record"], str) or rec["record"] not in RECORD_KINDS:
            self._add(pos, "STREAM_UNKNOWN_RECORD", path + ".record",
                      "must be one of %s" % ", ".join(RECORD_KINDS))
        else:
            kind = rec["record"]
        # index: required for every record kind, and equal to the 0-based position
        if "index" not in rec:
            self._add(pos, "STREAM_MISSING_FIELD", path + ".index", "required field is absent")
        elif not _is_seq(rec["index"]):
            self._add(pos, "STREAM_MALFORMED", path + ".index", "must be an integer >= 0")
        elif rec["index"] != pos:
            self._add(pos, "STREAM_INDEX_MISMATCH", path + ".index",
                      "index %d at position %d" % (rec["index"], pos))
        if kind is None:
            return                       # no lifecycle effect; fields cannot be judged without a kind
        required, optional = RECORD_FIELDS[kind]
        for f in required:
            if f not in rec and f not in ("record", "index"):
                self._add(pos, "STREAM_MISSING_FIELD", "%s.%s" % (path, f), "required field is absent")
        for f in rec:
            if f not in required and f not in optional:
                self._add(pos, "STREAM_UNKNOWN_FIELD", "%s.%s" % (path, f), "field is not defined by the contract")
        getattr(self, "_" + kind)(pos, path, rec)

    # open
    def _open(self, pos, path, rec):
        ident = {}
        if "stream_id" in rec:
            if isinstance(rec["stream_id"], str) and STREAM_ID_RE.match(rec["stream_id"]):
                ident["stream_id"] = rec["stream_id"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".stream_id", "must match the identity pattern")
        if "sensor_id" in rec:
            if isinstance(rec["sensor_id"], str) and SENSOR_ID_RE.match(rec["sensor_id"]):
                ident["sensor_id"] = rec["sensor_id"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".sensor_id", "must match the sensor identity pattern")
        if "kind" in rec:
            if isinstance(rec["kind"], str) and rec["kind"] in KINDS:
                ident["kind"] = rec["kind"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".kind", "must be one of %s" % ", ".join(KINDS))
        if "clock" in rec:
            if isinstance(rec["clock"], str) and rec["clock"] in CLOCKS:
                ident["clock"] = rec["clock"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".clock", "must be one of %s" % ", ".join(CLOCKS))
        first = None
        if "first_sequence" in rec:
            if _is_seq(rec["first_sequence"]):
                first = rec["first_sequence"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".first_sequence", "must be an integer >= 0")
        if self._state == "NONE":
            if pos != 0:
                self._add(pos, "STREAM_OPEN_NOT_FIRST", path, "the open record must be the first record")
            self._state = "OPEN"
            self._have_open = True
            self._ident = ident
            self._first_bound = first
        else:
            self._add(pos, "STREAM_OPEN_REPEATED", path, "the stream is already open; this record changes nothing")

    # sample
    def _sample(self, pos, path, rec):
        if self._state == "NONE":
            self._add(pos, "STREAM_SAMPLE_BEFORE_OPEN", path, "no open record precedes this sample")
        elif self._state == "CLOSED":
            self._add(pos, "STREAM_SAMPLE_AFTER_CLOSE", path, "the stream is closed")
        if "sample" not in rec:
            return
        s = rec["sample"]
        # every embedded value goes to the unchanged validator, objects or not
        for v in validate_sample(s):
            self._samples.append(SampleViolation(pos, v.code, v.path, v.message))
        if not isinstance(s, dict):
            self._add(pos, "STREAM_MALFORMED", path + ".sample", "must be an object")
            return
        seq = s.get("sequence") if _is_seq(s.get("sequence")) else None
        ts = s.get("timestamp")
        # a recognised clock is enough to compare with the stream clock; a usable timestamp (for the regression
        # check) also needs the unit ns and an integer value >= 0, as the sample contract requires
        clock_ok = isinstance(ts, dict) and isinstance(ts.get("clock"), str) and ts["clock"] in CLOCKS
        ts_ok = clock_ok and ts.get("unit") == TIMESTAMP_UNIT and _is_seq(ts.get("value"))
        # identity and clock, against the values fixed by the open record
        if "sensor_id" in self._ident and isinstance(s.get("sensor_id"), str) \
                and s["sensor_id"] != self._ident["sensor_id"]:
            self._add(pos, "STREAM_SENSOR_CHANGE", path + ".sample.sensor_id",
                      "%r differs from the stream sensor %r" % (s["sensor_id"], self._ident["sensor_id"]))
        if "kind" in self._ident and isinstance(s.get("kind"), str) and s["kind"] != self._ident["kind"]:
            self._add(pos, "STREAM_KIND_CHANGE", path + ".sample.kind",
                      "%r differs from the stream kind %r" % (s["kind"], self._ident["kind"]))
        if "clock" in self._ident and clock_ok and ts["clock"] != self._ident["clock"]:
            self._add(pos, "STREAM_CLOCK_MISMATCH", path + ".sample.timestamp.clock",
                      "%s differs from the stream clock %s" % (ts["clock"], self._ident["clock"]))
        # sequence continuity against the previous sample record with a usable sequence
        if seq is not None:
            if self._prev_seq is not None:
                p = self._prev_seq
                if seq == p:
                    self._add(pos, "STREAM_SEQUENCE_DUPLICATE", path + ".sample.sequence",
                              "%d equals the previous sequence" % seq)
                elif seq < p:
                    self._add(pos, "STREAM_SEQUENCE_REGRESSION", path + ".sample.sequence",
                              "%d is lower than the previous sequence %d" % (seq, p))
                elif seq > p + 1:
                    self._add(pos, "STREAM_SEQUENCE_GAP", path + ".sample.sequence",
                              "sequence %d to %d missing (previous %d, this %d)" % (p + 1, seq - 1, p, seq))
            self._prev_seq = seq
        # timestamps: comparable only on the same clock
        if ts_ok:
            if self._prev_ts is not None and self._prev_ts[0] == ts["clock"] and ts["value"] < self._prev_ts[1]:
                self._add(pos, "STREAM_TIMESTAMP_REGRESSION", path + ".sample.timestamp.value",
                          "%d is lower than the previous timestamp %d" % (ts["value"], self._prev_ts[1]))
            self._prev_ts = (ts["clock"], ts["value"])
        if self._state == "OPEN":
            self._open_samples += 1
            if self._open_samples == 1 and self._first_bound is not None and seq is not None \
                    and seq != self._first_bound:
                self._add(pos, "STREAM_FIRST_SEQUENCE_UNMET", path + ".sample.sequence",
                          "first sample has sequence %d, the open record states first_sequence %d"
                          % (seq, self._first_bound))
            self._last_open_seq = seq

    # close
    def _close(self, pos, path, rec):
        last = None
        if "last_sequence" in rec:
            if _is_seq(rec["last_sequence"]):
                last = rec["last_sequence"]
            else:
                self._add(pos, "STREAM_MALFORMED", path + ".last_sequence", "must be an integer >= 0")
        if self._state == "NONE":
            self._add(pos, "STREAM_CLOSE_BEFORE_OPEN", path, "no open record precedes this close")
        elif self._state == "CLOSED":
            self._add(pos, "STREAM_CLOSE_REPEATED", path, "the stream is already closed")
        else:
            self._state = "CLOSED"
            if self._open_samples == 0:
                if self._first_bound is not None:
                    self._add(pos, "STREAM_FIRST_SEQUENCE_UNMET", path,
                              "first_sequence %d was stated but no sample followed the open record"
                              % self._first_bound)
                if last is not None:
                    self._add(pos, "STREAM_LAST_SEQUENCE_UNMET", path,
                              "last_sequence %d was stated but no sample followed the open record" % last)
            elif last is not None and self._last_open_seq is not None and self._last_open_seq != last:
                self._add(pos, "STREAM_LAST_SEQUENCE_UNMET", path + ".last_sequence",
                          "last sample has sequence %d, the close record states last_sequence %d"
                          % (self._last_open_seq, last))


def check_stream(doc):
    """Validate a stream document and return a StreamResult. The document is treated as a complete stream."""
    if not isinstance(doc, dict):
        return StreamResult([StreamDiagnostic(-1, "STREAM_MALFORMED", "$", "the document must be an object")], [])
    checker = StreamChecker()
    for f in DOCUMENT_FIELDS:
        if f not in doc:
            checker._add(-1, "STREAM_MISSING_FIELD", f, "required field is absent")
    for f in doc:
        if f not in DOCUMENT_FIELDS:
            checker._add(-1, "STREAM_UNKNOWN_FIELD", f, "field is not defined by stream contract %s" % STREAM_VERSION)
    if "stream_version" in doc:
        ver = doc["stream_version"]
        if not isinstance(ver, str):
            checker._add(-1, "STREAM_MALFORMED", "stream_version", "must be a string")
        elif ver not in SUPPORTED_VERSIONS:
            checker._add(-1, "STREAM_UNSUPPORTED_VERSION", "stream_version",
                         "%s is not supported (supported: %s)" % (ver, ", ".join(SUPPORTED_VERSIONS)))
    if "records" in doc:
        if not isinstance(doc["records"], list):
            checker._add(-1, "STREAM_MALFORMED", "records", "must be an array")
        else:
            checker.feed(doc["records"])
            checker.finish()
    return checker.result()


def main(argv):
    if len(argv) != 2:
        print("usage: python3 -m kritva_sense.stream FILE.json", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("cannot read stream: %s" % exc, file=sys.stderr)
        return 2
    result = check_stream(doc)
    for d in result.stream:
        print("%s record %d %s: %s" % (d.code, d.position, d.path, d.message))
    for v in result.samples:
        print("SAMPLE %s record %d %s: %s" % (v.code, v.position, v.path, v.message))
    print("conformant" if result.conformant else "not conformant")
    return 0 if result.conformant else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
