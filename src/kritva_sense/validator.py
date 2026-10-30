"""Reference validator for the Sense data contract v0.1.0 (contract/SENSE_CONTRACT.md).

It implements the contract; it never defines or alters it. Standard library only.
Results are deterministic: violations are sorted by (path, code).
"""
import math
import re
from collections import namedtuple

CONTRACT_VERSION = "0.1.0"
SUPPORTED_VERSIONS = (CONTRACT_VERSION,)

Violation = namedtuple("Violation", "code path message")

ERROR_CODES = (
    "MISSING_FIELD",
    "MALFORMED_FIELD",
    "UNKNOWN_FIELD",
    "UNSUPPORTED_CONTRACT_VERSION",
    "INVALID_SENSOR_ID",
    "INVALID_TIMESTAMP",
    "INVALID_UNIT",
    "UNKNOWN_FRAME",
    "INVALID_VALIDITY",
    "NON_FINITE_VALUE",
    "SEQUENCE_REGRESSION",
    "STALE_DATA",
    "MISSING_DATA",
    "INVALID_DATA",
)

FRAMES = ("world", "base", "sensor")
CLOCKS = ("monotonic", "utc")
TIMESTAMP_UNIT = "ns"
VALIDITY_STATES = ("VALID", "STALE", "MISSING", "INVALID")

# kind -> {measurement name: required unit}. One unit system: SI.
KINDS = {
    "imu": {
        "accel_x": "m/s^2", "accel_y": "m/s^2", "accel_z": "m/s^2",
        "gyro_x": "rad/s", "gyro_y": "rad/s", "gyro_z": "rad/s",
    },
    "range": {"distance": "m"},
    "encoder": {"position": "rad"},
    "temperature": {"temperature": "K"},
}

REQUIRED = ("contract_version", "sensor_id", "kind", "sequence", "timestamp",
            "frame_id", "validity", "measurements")
OPTIONAL = ("error_code",)
SENSOR_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}(\.[a-z0-9_]{1,32}){0,3}$")


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sorted(vs):
    return sorted(vs, key=lambda v: (v.path, v.code, v.message))


def validate_sample(sample):
    """Return a sorted list of Violation for structural conformance; [] means conformant."""
    out = []
    if not isinstance(sample, dict):
        return [Violation("MALFORMED_FIELD", "$", "sample must be an object")]
    for f in REQUIRED:
        if f not in sample:
            out.append(Violation("MISSING_FIELD", f, "required field is absent"))
    for f in sample:
        if f not in REQUIRED and f not in OPTIONAL:
            out.append(Violation("UNKNOWN_FIELD", f, "field is not defined by contract %s" % CONTRACT_VERSION))

    ver = sample.get("contract_version")
    if "contract_version" in sample:
        if not isinstance(ver, str):
            out.append(Violation("MALFORMED_FIELD", "contract_version", "must be a string"))
        elif ver not in SUPPORTED_VERSIONS:
            out.append(Violation("UNSUPPORTED_CONTRACT_VERSION", "contract_version",
                                 "%s is not supported (supported: %s)" % (ver, ", ".join(SUPPORTED_VERSIONS))))

    sid = sample.get("sensor_id")
    if "sensor_id" in sample:
        if not isinstance(sid, str):
            out.append(Violation("MALFORMED_FIELD", "sensor_id", "must be a string"))
        elif not SENSOR_ID_RE.match(sid):
            out.append(Violation("INVALID_SENSOR_ID", "sensor_id", "does not match the stable identity pattern"))

    kind = sample.get("kind")
    kind_ok = False
    if "kind" in sample:
        if not isinstance(kind, str):
            out.append(Violation("MALFORMED_FIELD", "kind", "must be a string"))
        elif kind not in KINDS:
            out.append(Violation("MALFORMED_FIELD", "kind", "unknown kind %r" % kind))
        else:
            kind_ok = True

    if "sequence" in sample and (not _is_int(sample["sequence"]) or sample["sequence"] < 0):
        out.append(Violation("MALFORMED_FIELD", "sequence", "must be an integer >= 0"))

    if "timestamp" in sample:
        out.extend(_check_timestamp(sample["timestamp"]))

    if "frame_id" in sample:
        fr = sample["frame_id"]
        if not isinstance(fr, str):
            out.append(Violation("MALFORMED_FIELD", "frame_id", "must be a string"))
        elif fr not in FRAMES:
            out.append(Violation("UNKNOWN_FRAME", "frame_id", "%r is not a defined frame (%s)" % (fr, ", ".join(FRAMES))))

    validity = sample.get("validity")
    validity_ok = False
    if "validity" in sample:
        if validity not in VALIDITY_STATES:
            out.append(Violation("INVALID_VALIDITY", "validity", "must be one of %s" % ", ".join(VALIDITY_STATES)))
        else:
            validity_ok = True

    if "error_code" in sample and sample["error_code"] not in ERROR_CODES:
        out.append(Violation("MALFORMED_FIELD", "error_code", "not a code defined by the contract"))
    if validity_ok and validity != "VALID" and "error_code" not in sample:
        out.append(Violation("MISSING_FIELD", "error_code", "required when validity is not VALID"))
    if validity_ok and validity == "VALID" and "error_code" in sample:
        out.append(Violation("MALFORMED_FIELD", "error_code", "must be absent when validity is VALID"))

    if "measurements" in sample:
        out.extend(_check_measurements(sample["measurements"], kind if kind_ok else None, validity if validity_ok else None))
    return _sorted(out)


def _check_timestamp(ts):
    if not isinstance(ts, dict):
        return [Violation("INVALID_TIMESTAMP", "timestamp", "must be an object {clock, unit, value}")]
    out = []
    for f in ("clock", "unit", "value"):
        if f not in ts:
            out.append(Violation("INVALID_TIMESTAMP", "timestamp.%s" % f, "required field is absent"))
    for f in ts:
        if f not in ("clock", "unit", "value"):
            out.append(Violation("UNKNOWN_FIELD", "timestamp.%s" % f, "field is not defined by the contract"))
    if "clock" in ts and ts["clock"] not in CLOCKS:
        out.append(Violation("INVALID_TIMESTAMP", "timestamp.clock", "must be one of %s" % ", ".join(CLOCKS)))
    if "unit" in ts and ts["unit"] != TIMESTAMP_UNIT:
        out.append(Violation("INVALID_TIMESTAMP", "timestamp.unit", "must be %r" % TIMESTAMP_UNIT))
    if "value" in ts and (not _is_int(ts["value"]) or ts["value"] < 0):
        out.append(Violation("INVALID_TIMESTAMP", "timestamp.value", "must be an integer >= 0"))
    return out


def _check_measurements(meas, kind, validity):
    if not isinstance(meas, dict):
        return [Violation("MALFORMED_FIELD", "measurements", "must be an object")]
    out = []
    if validity == "MISSING":
        if meas:
            out.append(Violation("MALFORMED_FIELD", "measurements", "must be empty when validity is MISSING"))
        return out
    spec = KINDS.get(kind) if kind else None
    if spec is not None:
        for name in spec:
            if name not in meas:
                out.append(Violation("MISSING_FIELD", "measurements.%s" % name, "required for kind %s" % kind))
    for name, m in meas.items():
        path = "measurements.%s" % name
        if spec is not None and name not in spec:
            out.append(Violation("UNKNOWN_FIELD", path, "not a measurement of kind %s" % kind))
            continue
        if not isinstance(m, dict):
            out.append(Violation("MALFORMED_FIELD", path, "must be an object {value, unit}"))
            continue
        for f in ("value", "unit"):
            if f not in m:
                out.append(Violation("MISSING_FIELD", "%s.%s" % (path, f), "required field is absent"))
        for f in m:
            if f not in ("value", "unit"):
                out.append(Violation("UNKNOWN_FIELD", "%s.%s" % (path, f), "field is not defined by the contract"))
        if "value" in m:
            v = m["value"]
            if not _is_num(v):
                out.append(Violation("MALFORMED_FIELD", path + ".value", "must be a number"))
            elif isinstance(v, float) and not math.isfinite(v):
                out.append(Violation("NON_FINITE_VALUE", path + ".value", "NaN and infinity are not allowed"))
        if "unit" in m and spec is not None and m["unit"] != spec[name]:
            out.append(Violation("INVALID_UNIT", path + ".unit", "must be %r for %s" % (spec[name], name)))
    return out


def check_freshness(sample, now_ns, now_clock, max_age_ns):
    """Freshness check; needs the consumer's context (contract section 6.1).

    now_ns is the consumer's current time in ns and now_clock the clock it came from ("monotonic" or "utc").
    Returns [] when fresh, STALE_DATA when age exceeds max_age_ns, INVALID_TIMESTAMP when the clocks differ or
    the sample is newer than now_ns, INVALID_DATA when the sample is not conformant. Age equal to the limit is fresh.
    Context-free validation (validate_sample) never evaluates freshness.
    """
    if validate_sample(sample):
        return [Violation("INVALID_DATA", "$", "sample is not conformant; freshness not evaluated")]
    if now_clock not in CLOCKS or now_clock != sample["timestamp"]["clock"]:
        return [Violation("INVALID_TIMESTAMP", "timestamp.clock",
                          "sample clock %s differs from the consumer clock %s" % (sample["timestamp"]["clock"], now_clock))]
    age = now_ns - sample["timestamp"]["value"]
    if age < 0:
        return [Violation("INVALID_TIMESTAMP", "timestamp.value", "sample is newer than the supplied clock")]
    if age > max_age_ns:
        return [Violation("STALE_DATA", "timestamp.value", "age %d ns exceeds %d ns" % (age, max_age_ns))]
    return []


def check_sequence(previous, current):
    """SEQUENCE_REGRESSION if the sequence does not increase for the same sensor_id.

    Needs the previous sample of that sensor (contract section 6.1); samples of different sensors are independent.
    """
    if previous["sensor_id"] != current["sensor_id"]:
        return []
    if current["sequence"] <= previous["sequence"]:
        return [Violation("SEQUENCE_REGRESSION", "sequence",
                          "%d does not follow %d" % (current["sequence"], previous["sequence"]))]
    return []


def usability(sample, now_ns, now_clock, max_age_ns):
    """Consumer decision: (usable, violations). Only conformant, VALID, fresh samples are usable.

    Precedence (contract section 6.1): structural errors, then the declared MISSING/STALE/INVALID state, then freshness.
    """
    v = validate_sample(sample)
    if v:
        return False, v
    state = sample["validity"]
    if state == "MISSING":
        return False, [Violation("MISSING_DATA", "validity", "producer reported no data")]
    if state == "STALE":
        return False, [Violation("STALE_DATA", "validity", "producer reported stale data")]
    if state == "INVALID":
        return False, [Violation("INVALID_DATA", "validity", "producer reported invalid data")]
    fresh = check_freshness(sample, now_ns, now_clock, max_age_ns)
    return (not fresh), fresh
