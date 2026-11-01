# KOS-SENSE-005: Versioned telemetry stream contract

| Property | Value |
|---|---|
| Milestone | V2-M7-SENSE-001 |
| Status | IN_PROGRESS (baselined in v6, D-087) |
| Weight | 4 (initial planning weight, 4 to 5 effort days; baseline v6, D-087) |
| Depends on | KOS-SENSE-001, KOS-SENSE-002 (Sense contract 0.1.0) and KOS-SENSE-004 (generator, used for fixtures) |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-501 to AC-507) |
| Deliverables | `contract/STREAM_CONTRACT.md`, `contract/stream.schema.json`, `src/kritva_sense/stream.py`, `tests/stream/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

Contract 0.1.0 defines one sample and says that sequence continuity needs context (the previous sample). This task adds a separate, versioned, transport-independent stream contract: a document that carries an ordered run of samples from one sensor with an explicit lifecycle, and deterministic rules that report what is wrong with the run. It defines data and checks, not a transport.

## Scope

- A versioned stream document: stream id, sensor id and kind, a stream clock fixed at `open`, and records. Records are `open`, `sample` (a contract 0.1.0 sample carried unchanged) and `close`, each with a record index. `open` may state the expected `first_sequence` and `close` the expected `last_sequence`; they are optional and the checker never infers a missing first or last sample without them.
- Lifecycle rules: exactly one `open`, first; samples only between `open` and `close`; at most one `close`, last. A stream without `close` is reported as unterminated and is not repaired. After a lifecycle violation the checker keeps collecting diagnostics for the remaining records and never drops, reorders or repairs a record.
- Stream diagnostics in their own namespace `STREAM_`, separate from the sample error codes: duplicate sequence (equal to the previous), sequence regression (lower than the previous), sequence gap (greater than the previous plus one, with the first and last missing number), expected first or last sequence not met, timestamp regression, clock mismatch with the stream clock, sensor id or kind change, record index errors, malformed records and lifecycle errors. The conditions for duplicate, regression and gap are mutually exclusive; independent defects on one record may each be reported.
- Stream diagnostics are additional to contract 0.1.0 and never amend it: a sample with a sequence gap or a clock different from the stream clock stays individually conformant under 0.1.0, and sample violations are reported separately from stream violations, with the record position.
- Batching: the same ordered records give the same diagnostics however they are split into input batches; a batch alone is not checked for cross-batch conditions.
- A schema, a reference validator (standard library only), synthetic fixtures (valid and invalid, partly made with KOS-SENSE-004), known-answer tests and a command line.

## Non-goals

No change to Sense contract 0.1.0, frame graph contract 0.1.0 or the generator; no MQTT, DDS, ROS 2, EtherCAT or any network transport; no server, buffering, retransmission or real-time guarantee; no shared freshness threshold or sensor-health policy; no frame transform handling; no multi-sensor merge or time synchronisation between streams; no integration with Mind, Motion or Skill.

## Completion boundary

Acceptance proves deterministic software behaviour on synthetic streams only. It does not prove behaviour on any real transport or sensor. Review stays the interim D-047 role, not independent, and acceptance is recorded centrally by the authorized approver.
