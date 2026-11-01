# Kritva Sense Telemetry Stream Contract

| Property | Value |
|---|---|
| Document ID | KOS-SENSE-STREAM-001 |
| Repository | `KritvaOS/kritva-sense` |
| Task | KOS-SENSE-005 (Telemetry stream contract and reference validator) |
| Version | Stream contract version: 0.1.0 |
| Status | PROPOSED: implemented for review under KOS-SENSE-005; not approved. A 0.x contract: it may change by the rules of section 13 |
| Owner | Dinesh (interim architecture and safety reviewer, program decision D-047) |
| Related contracts | [SENSE_CONTRACT.md](SENSE_CONTRACT.md) 0.1.0 (accepted, tag `v0.1.0`) and [FRAME_GRAPH_CONTRACT.md](FRAME_GRAPH_CONTRACT.md) 0.1.0; neither is changed by this document |
| Machine-readable form | [stream.schema.json](stream.schema.json) (a structural subset: it describes only the three record kinds, so a record of another kind fails the schema, and the reference validator reports it as `STREAM_UNKNOWN_RECORD`) |
| Reference validator | `src/kritva_sense/stream.py` |
| Criteria | [tasks/KOS-SENSE-005/ACCEPTANCE_CRITERIA.md](../tasks/KOS-SENSE-005/ACCEPTANCE_CRITERIA.md) |

## 1. Purpose and scope

Sense contract 0.1.0 defines one sample and says that sequence continuity needs context: the previous sample (section 6.1 of that contract). This contract adds the missing piece as a separate, versioned interface: a document that carries an ordered run of samples from one sensor with an explicit lifecycle (`open`, samples, `close`), and deterministic rules that report what is wrong with the run.

It defines data and checks. It does not define a transport (no MQTT, DDS, ROS 2, EtherCAT or network protocol), a server, buffering, retransmission, a real-time guarantee, a shared freshness threshold or a sensor-health policy. It says nothing about frames or transforms, about merging or synchronising several streams, or about any consumer. It is software behaviour on synthetic data only and makes no hardware or safety claim.

## 2. Relation to the Sense data contract

The stream contract has its own version and change record. It does not change the sample contract.

- Every sample is carried unchanged inside a `sample` record and is validated by the unchanged contract 0.1.0 validator. Its violations keep their contract 0.1.0 codes and are reported with the record position, separately from the stream diagnostics (section 10).
- Stream diagnostics are additional to contract 0.1.0 and never amend it. A sample whose sequence leaves a gap, or whose clock differs from the stream clock, is still individually conformant under 0.1.0; the stream diagnostic says the run is not consistent, not that the sample is invalid.
- Stream diagnostics use their own code namespace `STREAM_` (section 11), so they cannot be confused with the sample codes. `SEQUENCE_REGRESSION` of contract 0.1.0 is the result of `check_sequence` for two samples; the stream codes `STREAM_SEQUENCE_DUPLICATE`, `STREAM_SEQUENCE_REGRESSION` and `STREAM_SEQUENCE_GAP` are reported by the stream check, and the embedded sample validation never reports a sequence condition on its own.

## 3. Document

A stream document is one JSON object with exactly these fields. Unknown fields are rejected (`STREAM_UNKNOWN_FIELD`).

| Field | Type | Rule |
|---|---|---|
| `stream_version` | string | SemVer of this contract. Supported: `0.1.0`. Otherwise `STREAM_UNSUPPORTED_VERSION`; a value that is not a string is `STREAM_MALFORMED`. |
| `records` | array | The records in stream order (section 4). An empty array is accepted by the schema and is not conformant (`STREAM_OPEN_MISSING`). A value that is not an array is `STREAM_MALFORMED`. |

A document that is not a JSON object is `STREAM_MALFORMED`. A missing field is `STREAM_MISSING_FIELD`.

## 4. Records

Every record is a JSON object with a `record` kind and an `index`. `record` is `open`, `sample` or `close`; a missing `record` is `STREAM_MISSING_FIELD` and any other value is `STREAM_UNKNOWN_RECORD`. A record whose kind is not known has no lifecycle effect and its other fields are not judged. A record that is not an object is `STREAM_MALFORMED`.

`index` is an integer greater than or equal to 0 and must equal the record's 0-based position in `records` (a missing `index` is `STREAM_MISSING_FIELD`, a value that is not such an integer is `STREAM_MALFORMED`, a different value is `STREAM_INDEX_MISMATCH`). The index lets a reader detect a record that was dropped, duplicated or reordered when the records were carried in batches; it is never used to repair the stream.

Each kind has exactly these fields; an undefined field is `STREAM_UNKNOWN_FIELD` and an absent required field is `STREAM_MISSING_FIELD`.

| Kind | Required | Optional | Rules |
|---|---|---|---|
| `open` | `record`, `index`, `stream_id`, `sensor_id`, `kind`, `clock` | `first_sequence` | `stream_id` and `sensor_id` match the sensor identity pattern of SENSE_CONTRACT section 3; `kind` is one of the sensor kinds of that contract; `clock` is `monotonic` or `utc` and is the stream clock, fixed at `open`; `first_sequence`, when present, is an integer >= 0 and states the sequence of the first sample. A value outside these rules is `STREAM_MALFORMED`. |
| `sample` | `record`, `index`, `sample` | none | `sample` is one object that follows contract 0.1.0. A value that is not an object is `STREAM_MALFORMED`, and it is also given to the contract 0.1.0 validator, which reports `MALFORMED_FIELD` at path `$` as a sample violation. |
| `close` | `record`, `index` | `last_sequence` | `last_sequence`, when present, is an integer >= 0 and states the sequence of the last sample. A value that is not such an integer is `STREAM_MALFORMED`. |

The stream identity (`stream_id`, `sensor_id`, `kind`, `clock`) is fixed by the first `open` record. A field of the open record that is malformed is reported and is not used for the checks that need it; those checks are skipped, never guessed.

## 5. Lifecycle

A conformant stream has exactly one `open` record, first; zero or more `sample` records after it; and exactly one `close` record, last. A `close` record is required: a stream without one is reported as unterminated and is never closed on the producer's behalf. The checker reads the records in order with three states: before open, open, closed.

| Record | In state | Diagnostic | Effect on the state |
|---|---|---|---|
| `open` | before open, at position 0 | none | open |
| `open` | before open, at a later position | `STREAM_OPEN_NOT_FIRST` | open |
| `open` | open or closed | `STREAM_OPEN_REPEATED` | none: the first open keeps the identity |
| `sample` | before open | `STREAM_SAMPLE_BEFORE_OPEN` | none |
| `sample` | open | none | none |
| `sample` | closed | `STREAM_SAMPLE_AFTER_CLOSE` | none |
| `close` | before open | `STREAM_CLOSE_BEFORE_OPEN` | none |
| `close` | open | none | closed |
| `close` | closed | `STREAM_CLOSE_REPEATED` | none |

At the end of the records: no open record at all is `STREAM_OPEN_MISSING` (this includes the empty stream), and an open stream that never closed is `STREAM_UNTERMINATED`. Both are reported on the document (position -1, path `records`).

After a lifecycle violation the checker keeps collecting diagnostics for the remaining records. It never drops, reorders or repairs a record: a sample before the open record or after the close record is still checked for sample violations, sequence and timestamps like any other sample. An unterminated stream is reported and not closed on the producer's behalf.

## 6. Sequence

Sequence conditions compare a sample with the previous sample record that has a usable sequence (an integer >= 0), in record order, whatever the lifecycle state of either. For a sample with sequence `c` and previous sequence `p`, exactly one of these applies, so the three conditions are mutually exclusive:

| Condition | Diagnostic |
|---|---|
| `c == p` | `STREAM_SEQUENCE_DUPLICATE` |
| `c < p` | `STREAM_SEQUENCE_REGRESSION` |
| `c > p + 1` | `STREAM_SEQUENCE_GAP`; the message states the first missing number `p + 1` and the last missing number `c - 1` |

`c == p + 1` is correct. The first sample has no previous sample and gets no sequence diagnostic. A sample whose sequence is not an integer >= 0 is reported by the sample validation, does not take part in these comparisons and does not move the previous sequence.

The optional bounds are the only way a first or last sample is judged; the checker never infers a missing first or last sample without them.

- `first_sequence` of the open record is compared with the sequence of the first `sample` record that follows the open record (the first sample seen while the stream is open). A different value is `STREAM_FIRST_SEQUENCE_UNMET` at that sample. If the stream is closed (or ends) with no such sample, the bound cannot be met and is `STREAM_FIRST_SEQUENCE_UNMET` at the close record (or on the document for an unterminated stream).
- `last_sequence` of the close record is compared with the sequence of the last `sample` record seen while the stream was open, that is, the last sample before the close. A different value, or no sample at all, is `STREAM_LAST_SEQUENCE_UNMET` at the close record. A stream with no close record has no last bound to meet.
- A bound is not evaluated against a sample whose sequence is not usable; that sample's own violation is reported by the sample validation.

## 7. Timestamps and identity

- Clock: a sample whose `timestamp.clock` differs from the stream clock is `STREAM_CLOCK_MISMATCH`. The sample itself stays conformant under contract 0.1.0.
- Usable timestamp: a `timestamp` object with a recognised `clock` (`monotonic` or `utc`), the `unit` `ns` and an integer `value` >= 0, the form contract 0.1.0 requires. A sample whose timestamp is not usable does not take part in the timestamp comparison and does not move the previous timestamp; the sample validation reports it. The clock comparison below needs only a recognised `clock`.
- Timestamp regression: a sample whose `timestamp.value` is lower than that of the previous sample record that has a usable timestamp is `STREAM_TIMESTAMP_REGRESSION`. An equal value is not a regression. Values are compared only when both samples use the same clock, because contract 0.1.0 does not define a comparison across clocks; a clock change is reported once, as `STREAM_CLOCK_MISMATCH`.
- Identity: a sample whose `sensor_id` differs from the `sensor_id` of the open record is `STREAM_SENSOR_CHANGE`; a different `kind`, `STREAM_KIND_CHANGE`. Both compare with the identity fixed at open, not with the previous sample.

Independent defects of one record may each be reported: for example a sample with a gap and a different clock has both diagnostics.

## 8. Samples

Each `sample` value, an object or not, is validated by the unchanged contract 0.1.0 validator (`validate_sample`), whatever the lifecycle state. Its violations are returned as sample violations with the record position and the path inside the sample, and keep their contract 0.1.0 codes (`MISSING_FIELD`, `INVALID_UNIT`, and so on). A stream is conformant only when it has no stream diagnostics and no sample violations. The validity states `STALE`, `MISSING` and `INVALID` of contract 0.1.0 are conformant samples and are not diagnostics of this contract; freshness is not evaluated here because it needs a consumer's clock and age limit (SENSE_CONTRACT section 6.1).

## 9. Batching

The records may reach a reader in batches. The reference checker is incremental: it keeps the state described above, takes records in order in batches of any size and gives, for the same ordered records, the same diagnostics and the same positions for every way of splitting them into batches. Positions count records across batches. The end-of-stream diagnostics (section 5) are produced when the reader says the stream is finished.

A batch checked alone, as its own document, is a complete stream of its own: its first record is position 0 and it is expected to open the stream. It says nothing about records before or after it, and cross-batch conditions (a gap or a duplicate between two batches, a record after a close that was in an earlier batch) are not reported for it. Cross-batch conditions are found only by feeding all batches, in order, to one checker.

## 10. Results and ordering

A result has two lists, kept apart: stream diagnostics with `STREAM_` codes, and sample violations with contract 0.1.0 codes. Each entry has a position (the 0-based record position, -1 for the document as a whole), a code, a path and a message. Both lists are sorted by `(position, code, path, message)`, so the result is deterministic and identical across runs and across ways of batching. Paths name the field: `records[3].sample.sequence` for a stream diagnostic on a sample, `sensor_id` for the sample violation of the same record.

## 11. Stream diagnostic codes

| Code | Reported when |
|---|---|
| `STREAM_MALFORMED` | The document, a record or a field has the wrong type, shape or an out-of-range value. |
| `STREAM_MISSING_FIELD` | A required field is absent. |
| `STREAM_UNKNOWN_FIELD` | A field is not defined by this version. |
| `STREAM_UNSUPPORTED_VERSION` | `stream_version` is a string but not a supported version. |
| `STREAM_UNKNOWN_RECORD` | `record` is not `open`, `sample` or `close`. |
| `STREAM_INDEX_MISMATCH` | `index` is not the record's 0-based position. |
| `STREAM_OPEN_MISSING` | The stream has no open record (including the empty stream). |
| `STREAM_OPEN_NOT_FIRST` | The first open record is not the first record. |
| `STREAM_OPEN_REPEATED` | A second or later open record. |
| `STREAM_SAMPLE_BEFORE_OPEN` | A sample record before the open record. |
| `STREAM_SAMPLE_AFTER_CLOSE` | A sample record after the close record. |
| `STREAM_CLOSE_BEFORE_OPEN` | A close record before the open record. |
| `STREAM_CLOSE_REPEATED` | A second or later close record. |
| `STREAM_UNTERMINATED` | The stream has an open record and no close record. |
| `STREAM_SEQUENCE_DUPLICATE` | A sequence equal to the previous sample's. |
| `STREAM_SEQUENCE_REGRESSION` | A sequence lower than the previous sample's. |
| `STREAM_SEQUENCE_GAP` | A sequence greater than the previous sample's plus one. |
| `STREAM_FIRST_SEQUENCE_UNMET` | The stated `first_sequence` is not met. |
| `STREAM_LAST_SEQUENCE_UNMET` | The stated `last_sequence` is not met. |
| `STREAM_TIMESTAMP_REGRESSION` | A timestamp lower than the previous sample's on the same clock. |
| `STREAM_CLOCK_MISMATCH` | A sample clock differs from the stream clock. |
| `STREAM_SENSOR_CHANGE` | A sample's `sensor_id` differs from the stream's. |
| `STREAM_KIND_CHANGE` | A sample's `kind` differs from the stream's. |

## 12. Worked example

A synthetic stream of one IMU, `imu.main`, on the `monotonic` clock, with `first_sequence` 100 and `last_sequence` 102 stated: the fixture `tests/stream/fixtures/valid/worked_example.json` has an open record at index 0, three samples with sequences 100, 101 and 102 at indexes 1 to 3 and a close record at index 4. It is conformant.

Remove the second sample (sequence 101) and renumber the indexes: the remaining samples are 100 and 102 and the checker reports one `STREAM_SEQUENCE_GAP` at the sample with sequence 102, stating that sequence 101 to 101 is missing. Both samples are still conformant under contract 0.1.0. The fixture is `tests/stream/fixtures/invalid/worked_example_gap.json`. Deleting the close record instead gives `STREAM_UNTERMINATED`, and the stated `last_sequence` is then not judged because there is no close record.

## 13. Limitations

- No transport, buffering, loss recovery or real-time property is defined or tested. A 10,000-record stream is a correctness and scale test of the checker; no runtime claim is made.
- The checker reads one stream of one sensor. Merging streams, time synchronisation between them and frame transforms are out of scope.
- No freshness threshold, health policy or consumer behaviour is defined here; those belong to a consumer (KOS-SENSE-006 tests consumers against this contract).
- A conformant stream says only that its records are well formed and consistent under these rules. It does not say that a sensor, a clock or a measurement is physically correct.
- Review is the interim D-047 role, not independent review.

## 14. Versioning and lifecycle

This is stream contract 0.1.0, PROPOSED for approval by the owner through the central review of KOS-SENSE-005. While the major version is 0, a change may be breaking; every change needs a changelog entry in [planning/CHANGELOG.md](../planning/CHANGELOG.md) and a decision, and the supported versions are listed in section 3. Adding a record kind, a field, a diagnostic code or a rule is a change to this contract and updates the schema, the validator and its tests together; `make test-unit` fails if they disagree. A change to the sample, to the frame graph or to the frame vocabulary is a change to those contracts, with their own versions.

## 15. Verification

`make test-unit` runs `tests/stream/`: valid and invalid fixtures (each defect class alone and in combination, the empty stream and generator-made streams), known-answer tests of every code with exact positions, paths and messages for each class, tests with odd types (booleans, floats, very large integers, lists and objects in identity fields), batching invariance for every split of small streams and for random splits of a 2,000-record and of a 10,000-record stream, the schema and constants agreement, the pinned contract documents and the command line. The command line is `python3 -m kritva_sense.stream FILE.json`, reading a stream document; it exits 0 when conformant, 1 when not, 2 on a usage or read error (an unreadable file or input that is not JSON).
