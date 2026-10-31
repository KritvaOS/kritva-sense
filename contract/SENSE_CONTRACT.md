# Kritva Sense Data Contract

| Property | Value |
|---|---|
| Document ID | KOS-SENSE-CONTRACT-001 |
| Repository | `KritvaOS/kritva-sense` |
| Task | KOS-SENSE-001 (Sense architecture and data contract) |
| Version | Contract version: 0.1.0 |
| Status | APPROVED: contract 0.1.0 approved by the owner (Dinesh; interim D-047 review, not independent); KOS-SENSE-001 ACCEPTED (central approval A076). Release tag `v0.1.0` is created by the owner after merge. Still a 0.x contract: it may change with a changelog entry and a decision. |
| Owner | Dinesh (interim architecture and safety reviewer, program decision D-047) |
| Machine-readable form | [sense-sample.schema.json](sense-sample.schema.json) |
| Reference validator | `src/kritva_sense/validator.py` (KOS-SENSE-002) |
| Criteria | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) |

## 1. Purpose and scope

This contract defines what one Sense sample is, so that consumers (kritva-mind and others) rely on a versioned contract and never on Sense internals. It covers sensor identity, timestamps, units, frame conventions, validity and stale-data behaviour, errors and versioning (AC-001 to AC-005).

It does not define transport, device drivers, calibration, inference, motion commands or any physical or safety validation. Software conformance to this contract is never a hardware or safety claim.

## 2. Architecture position

Producers (drivers and simulators, outside this repository) emit samples. This repository owns the contract and the reference validator only. Consumers read samples through the contract. No component imports Mind, Skill or Motion internals, and Sense imports nothing from them. The platform foundation (kritva-core) is not required by contract 0.1.0; no Core or Community version is pinned. A pin is recorded here only when a normative dependency on an approved contract is introduced.

## 3. Sample

A sample is one JSON object with exactly these fields. Unknown fields are rejected (`UNKNOWN_FIELD`), so every extension is a contract change under section 9.

| Field | Type | Rule |
|---|---|---|
| `contract_version` | string | SemVer of this contract. Supported: `0.1.0`. Otherwise `UNSUPPORTED_CONTRACT_VERSION`. |
| `sensor_id` | string | Stable identity of the stream, lower case, dot-separated, pattern `^[a-z][a-z0-9_]{0,31}(\.[a-z0-9_]{1,32}){0,3}$`. It never changes for the same physical or simulated sensor. Otherwise `INVALID_SENSOR_ID`. |
| `kind` | string | One of `imu`, `range`, `encoder`, `temperature`. |
| `sequence` | integer | Per `sensor_id`, greater than or equal to 0, strictly increasing. |
| `timestamp` | object | `{clock, unit, value}`, see section 4. |
| `frame_id` | string | One of the frames in section 5. |
| `validity` | string | One of `VALID`, `STALE`, `MISSING`, `INVALID`, see section 6. |
| `error_code` | string | Required when `validity` is not `VALID`; absent when it is `VALID`. One of the codes in section 7. |
| `measurements` | object | Per-kind measurements, see section 3.1. |

### 3.1 Measurements by kind

Each measurement is `{value, unit}`. `value` is a finite JSON number (not a boolean, string, NaN or infinity). `unit` must equal the unit below. The unit system is SI and is the only one in this version.

| Kind | Measurement | Unit |
|---|---|---|
| `imu` | `accel_x`, `accel_y`, `accel_z` | `m/s^2` |
| `imu` | `gyro_x`, `gyro_y`, `gyro_z` | `rad/s` |
| `range` | `distance` | `m` |
| `encoder` | `position` | `rad` |
| `temperature` | `temperature` | `K` |

A sample with validity other than `MISSING` carries every measurement of its kind and no others.

## 4. Time

`timestamp.clock` is `monotonic` (non-decreasing clock with an undefined epoch, comparable only with itself) or `utc` (nanoseconds since the Unix epoch). `timestamp.unit` is always `ns`. `timestamp.value` is an integer greater than or equal to 0. Any other form is `INVALID_TIMESTAMP`. Samples and the consumer's "now" used for freshness must come from the same clock; comparing across clocks is not defined.

## 5. Frames and coordinates

Frames are defined once, here, and referenced by name; none is implied.

| Frame | Meaning |
|---|---|
| `world` | Fixed external frame. Z is opposite to gravity. Its origin and heading are set by the deployment and are not defined here. |
| `base` | Rigidly attached to the robot body, X toward the robot's forward direction. Its origin is the robot reference point named by the robot description, outside this contract. |
| `sensor` | Rigidly attached to the sensor, origin at the sensor reference point. Mounting offset and rotation relative to `base` are outside this contract. |

`frame_id` names the coordinate frame in which the sample's axis-bearing values are expressed. The producer maps the sensor's native axes into the convention below before emitting, so a consumer never needs a datasheet. Scalar kinds (`range`, `encoder`, `temperature`) are not rotated by `frame_id`; it names the frame of the sensor's reference point. This version defines no transform between frames, so a consumer must not assume `world`, `base` and `sensor` are related until a transform is provided outside this contract.

All frames are right-handed with X forward, Y left, Z up. Rotation about an axis is positive counter-clockwise looking from the positive axis toward the origin. Transforms between frames are outside this version.

Example: an `imu` sample with `frame_id` `base` reports `accel_x` as acceleration along the robot's forward axis in `m/s^2`. `accel` is specific force (what an accelerometer measures), so a robot at rest on level ground reports `accel_z` of about +9.81 `m/s^2`. `gyro_z` is positive for a counter-clockwise turn seen from above. This convention is part of the draft under review. A `frame_id` not in the table is `UNKNOWN_FRAME`.

## 6. Validity and stale data

| `validity` | Meaning | Consumer behaviour |
|---|---|---|
| `VALID` | Producer asserts a good reading. | Usable if fresh. |
| `STALE` | Producer asserts the reading is old. | Not usable: `STALE_DATA`. |
| `MISSING` | No reading; `measurements` is empty. | Not usable: `MISSING_DATA`. |
| `INVALID` | Reading present but not trustworthy. | Not usable: `INVALID_DATA`. |

Freshness: a consumer declares `max_age_ns` per stream. A `VALID` sample whose age (now minus `timestamp.value`, same clock) exceeds `max_age_ns` is `STALE_DATA`. An age equal to the limit is fresh. A sample newer than the consumer's clock is `INVALID_TIMESTAMP`. A non-conformant sample is never usable and freshness is not evaluated for it (`INVALID_DATA`).

### 6.1 Checks that need context

Checking one sample against sections 3 to 5 proves structural conformance only. It does not prove freshness or sequence continuity, and a consumer must not treat a conformant sample as fresh or in order on that basis.

- Freshness needs the consumer's `now` value in nanoseconds, the clock it came from (`monotonic` or `utc`) and `max_age_ns`. If any is absent, freshness is not evaluated. If the clock differs from the sample's `timestamp.clock`, the result is `INVALID_TIMESTAMP`.
- Sequence continuity needs the previous sample of the same `sensor_id`. Without it, continuity is not evaluated. Samples of different sensors are independent.
- For a `STALE` or `INVALID` sample the measurements are the last known values, present for diagnosis. A consumer must not use them as readings.
- Precedence for a consumer: a non-conformant sample is rejected with its structural errors; otherwise a declared `MISSING`, `STALE` or `INVALID` state decides; otherwise freshness is evaluated.

## 7. Errors

| Code | Raised when |
|---|---|
| `MISSING_FIELD` | A required field or measurement is absent. |
| `MALFORMED_FIELD` | A field has the wrong type or an out-of-range value. |
| `UNKNOWN_FIELD` | A field or measurement is not defined by this version. |
| `UNSUPPORTED_CONTRACT_VERSION` | `contract_version` is not supported. |
| `INVALID_SENSOR_ID` | `sensor_id` does not match the identity pattern. |
| `INVALID_TIMESTAMP` | The timestamp object, clock, unit or value is wrong, or the sample is from the future. |
| `INVALID_UNIT` | A measurement unit differs from section 3.1. |
| `UNKNOWN_FRAME` | `frame_id` is not a defined frame. |
| `INVALID_VALIDITY` | `validity` is not a defined state. |
| `NON_FINITE_VALUE` | A measurement is NaN or infinite. |
| `SEQUENCE_REGRESSION` | `sequence` does not increase for the same `sensor_id`. |
| `STALE_DATA` | Data is older than allowed or declared `STALE`. |
| `MISSING_DATA` | Producer declared `MISSING`. |
| `INVALID_DATA` | Producer declared `INVALID`, or freshness was asked of a non-conformant sample. |

Validation reports every violation, sorted by path then code, so results are deterministic. JSON itself cannot carry NaN or infinity; `NON_FINITE_VALUE` guards parsers and in-memory producers that can.

## 8. Lifecycle

This is contract 0.1.0. The owner approved it as v0.1.0 (relayed in chat, 2026-10-31; interim D-047 review) and KOS-SENSE-001 is ACCEPTED (central approval A076). It is tagged `v0.1.0` (annotated) by the owner after this status change is merged. Being 0.x, it may still change; each change needs a changelog entry and a decision (section 9).

## 9. Versioning and compatibility

The contract is versioned independently of program phases. Within a MAJOR version, a MINOR change may only add something optional and a PATCH change may only clarify. While MAJOR is 0, a MINOR change may also be breaking, and the validator supports exactly the versions it lists. A breaking change needs a new MAJOR version (or MINOR while 0.x), a changelog entry in `planning/CHANGELOG.md` and an approved decision (AC-005). The JSON Schema is a structural subset of this contract. It does not express the per-kind measurement sets and units, the coupling between `validity`, `error_code` and `measurements`, or the context checks in section 6.1. A sample that passes the schema is not thereby conformant; this document and the reference validator are normative where they are stricter. Adding a kind, frame, unit, error code or field is a contract change and updates the schema, the validator and its tests together; `make test-unit` fails if they disagree.
