# Acceptance Criteria: KOS-SENSE-005

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-005](TASK.md), proposed for baseline v6 (D-087). Status of these criteria: PROPOSED until the task is baselined and approved to start; the accepted criteria of KOS-SENSE-001 to KOS-SENSE-004 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-501 | The stream contract has its own version, document and schema that agree with the validator's constants. Exact fields, required and optional fields (including optional `first_sequence` on `open` and `last_sequence` on `close`), record kinds, versioning and unknown-field behaviour are defined; a malformed document, record, version or unknown field is rejected with a documented `STREAM_` code. | contract review, schema tests |
| AC-502 | Lifecycle: one `open` first, zero or more samples, an optional final `close` are accepted; every invalid ordering (missing, malformed or repeated `open`, sample before `open` or after `close`, repeated `close`, record after `close`, missing `close`) gives its documented diagnostic, the checker continues with the remaining records, and no record is dropped, reordered or repaired. | `make test-unit` |
| AC-503 | Sequence: duplicate (equal), regression (lower), internal gap (with first and last missing number) and the expected first or last sequence not met are each reported with a documented code and record position; the conditions are mutually exclusive, a clean stream reports nothing, and no first or last sample is inferred without a stated bound. | `make test-unit` |
| AC-504 | Timestamps and identity: a sample clock different from the stream clock, a timestamp lower than the previous sample's, and a sensor id or kind change are each reported with a documented code; these remain separate from the sample codes of contract 0.1.0. | `make test-unit` |
| AC-505 | Every embedded sample is validated by the unchanged contract 0.1.0 validator; its violations are reported with the record position and kept distinct from stream diagnostics; a sample with a gap or a different clock stays individually conformant; the document states that stream diagnostics are additional to contract 0.1.0. | `make test-unit` |
| AC-506 | Determinism: diagnostics are sorted by a documented key and identical across runs; the same ordered records give identical results for every partition into batches; a 10,000-record stream is a correctness and scale test (no runtime claim is made); fixtures cover each class alone, in combination and the empty stream. | `make test-unit` |
| AC-507 | A command line reads a stream file and exits 0 (conformant), 1 (not conformant), 2 (usage or read error, unreadable or non-JSON input). The contract, schema, fixtures, worked example and test instructions are documented; `make test-unit` runs from a clean checkout, uses only the standard library, passes in CI on the exact closing commit, and the documents and schemas of Sense contract 0.1.0 and frame graph contract 0.1.0 and the generator are unchanged (pinned by tests). | `make test-unit`, CI, review |

## Test boundaries

All inputs are synthetic. No transport, ROS 2 or external library is required. No coverage threshold is imposed (none is approved, D-080).

## Definition of done

AC-501 to AC-507 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no physical or safety claim is inferred from synthetic validation.
