# Consumer conformance harness (KOS-SENSE-006)

Status: ACCEPTED (KOS-SENSE-006, central approval D-089; review is the interim D-047 role, not independent). Harness version 0.1.0. Criteria: [AC-601 to AC-607](../../tasks/KOS-SENSE-006/ACCEPTANCE_CRITERIA.md).

A future consumer (Mind, Motion, Skill or another repository) can show with this harness that it handles Sense data as the contracts say. The harness feeds a consumer a deterministic set of synthetic samples, streams and frame graphs, compares its decisions with the outcomes written in the case set, and writes a machine-readable result. It tests the consumer rules of [SENSE_CONTRACT.md](../../contract/SENSE_CONTRACT.md), [STREAM_CONTRACT.md](../../contract/STREAM_CONTRACT.md) and [FRAME_GRAPH_CONTRACT.md](../../contract/FRAME_GRAPH_CONTRACT.md). It integrates with no real consumer, and it changes no contract, schema, validator, generator or stream checker.

Passing proves that a consumer decides the synthetic cases as the contracts say. It does not prove that any real consumer conforms in operation, and it is not a sensor, robot or safety conformance test. No timeout is applied to a consumer: a consumer that never returns blocks the run.

## 1. Consumer interface

A consumer is an object with three operations. They are independent: a consumer need not implement the three rule groups the same way, and each case calls exactly one operation. All inputs are plain JSON values (dict, list, str, int, float, bool, None). A consumer gets a private copy of every input, so it cannot change what later cases see.

| Operation | Inputs | Decision |
|---|---|---|
| `decide_sample(sample, now_ns, now_clock, max_age_ns, previous=None)` | `sample`: one sample, any JSON value. `now_ns`: the consumer's current time in ns. `now_clock`: `monotonic` or `utc`, the clock `now_ns` came from. `max_age_ns`: the age limit in ns. `previous`: the most recent earlier sample with the same `sensor_id` as `sample`, or `None` when there is none. It is not the preceding record or the last item received: a consumer that handles several sensors keeps sequence state per `sensor_id` (SENSE_CONTRACT 6.1). | `{"usable": bool, "codes": [str]}` |
| `decide_stream(document)` | `document`: a stream document of STREAM_CONTRACT (any JSON value), treated as a complete stream. | `{"conformant": bool, "stream": [[position, code]], "samples": [[position, code]]}` |
| `decide_frame(graph, source, target)` | `graph`: a frame graph document; `source`, `target`: frame ids (any JSON value). | `{"ok": bool, "transform": {...} or None, "codes": [str]}` |

Decision values are the codes of the contracts, never new ones:

- Sample decision: `usable` is true exactly when `codes` is empty. Codes are the Sense contract 0.1.0 codes (`STALE_DATA`, `MISSING_DATA`, `INVALID_DATA`, `INVALID_TIMESTAMP`, `SEQUENCE_REGRESSION` and the structural codes such as `INVALID_UNIT`). A non-conformant sample is not usable and its codes are its structural errors, sorted without repetition.
- Stream decision: `stream` holds the `STREAM_` diagnostics and `samples` the sample violations (contract 0.1.0 codes), each as `[record position, code]`; position `-1` is the document. `conformant` is true exactly when both lists are empty. Order inside the lists does not matter; it is normalised before comparison.
- Frame decision: `transform` is `{"translation": {x, y, z}, "translation_unit": "m", "rotation": {w, x, y, z}}` with finite numbers and is present exactly when `ok` is true; then `codes` is empty. Otherwise `transform` is `None` and `codes` holds the `FG_` codes, sorted without repetition. A successful transform must also be canonical (FRAME_GRAPH_CONTRACT sections 5 and 7): unit quaternion within 1e-9, sign chosen so that the first component of `w, x, y, z` with magnitude of at least 1e-12 is positive, and no negative zero in the translation or the rotation; otherwise the decision is undefined. Translations and rotations are then compared with the expected ones with an absolute tolerance of 1e-9.

Rules the sample decision follows (SENSE_CONTRACT sections 4, 6 and 6.1): a non-conformant sample is rejected with its structural errors and nothing else is evaluated; otherwise a declared `MISSING`, `STALE` or `INVALID` state decides (`MISSING_DATA`, `STALE_DATA`, `INVALID_DATA`); otherwise freshness: a different clock or a sample newer than `now_ns` is `INVALID_TIMESTAMP`, an age above `max_age_ns` is `STALE_DATA`, and an age equal to the limit is fresh. Sequence continuity needs `previous`: a conformant sample of the same `sensor_id` whose sequence does not exceed the previous one is `SEQUENCE_REGRESSION`; a jump ahead is conformant; samples of different sensors are independent. The contracts do not state where the sequence check falls relative to the declared state and freshness, so this interface fixes it as a convention of the harness, not as a contract clause: sequence continuity is evaluated last, only for a sample that is otherwise usable. A sample that is stale (by age or declared) and also regresses is therefore `STALE_DATA`, and a non-conformant sample gets only its structural errors. The three cases that depend on this order (`sample.sequence.after_freshness`, `after_declared_state`, `after_structure`) state `CONFORMANCE 1 (interface convention, not a contract clause)` as their clause, and the mutant `sequence_before_freshness` breaks it. Fixing the order in SENSE_CONTRACT 6.1 would be a contract change (new version and approved decision) and is outside this task; until then the convention applies to this harness only. When `now_ns`, `now_clock` or `max_age_ns` is absent (`None`) freshness is not evaluated (SENSE_CONTRACT 6.1); the case set always supplies all three.

Nothing is assumed about the connection of `world`, `base` and `sensor`: frames are connected only by the transform records of the graph. The identity is a valid answer only for a frame of the graph resolved to itself.

An undefined decision is any other return value: a wrong shape, an unknown code, a code that is not defined for the operation, `usable` or `ok` that disagrees with the codes, a non-finite number, a wrong type. It fails the case.

## 2. Reference consumer and mutants

`ReferenceConsumer` implements these rules with the validators of the accepted tasks. It is the implementation under test. It is never asked for an expected result.

`MUTANTS` holds 15 deliberately non-conforming consumers, each wrong in exactly one rule: `freshness_limit_exclusive`, `freshness_clock_ignored`, `freshness_future_accepted` (freshness); `precedence_freshness_first`, `precedence_structure_unchecked`, `precedence_declared_stale_ignored` (validity precedence); `sequence_equal_accepted`, `sequence_sensors_mixed`, `sequence_gap_rejected`, `sequence_before_freshness` (sequence); `stream_gap_ignored`, `stream_gap_as_regression` (stream gap handling); `frame_unknown_gets_identity`, `frame_no_path_gets_identity`, `frame_self_identity_unchecked` (frame identity assumption). Each fails at least one named case and still passes a named control case of the same operation, so it fails because of its declared rule; none passes the whole set (tests).

## 3. Case set

`build_cases(seed)` returns the cases sorted by id. A case has `id`, `operation`, `clause` (the contract clause it comes from), `input` and `expected`. Inputs are built with the generator (`make_sample`, `generate_samples` with faults, fixed timestamps) and written stream and graph documents. Expected outcomes are literals written by hand from the contract text. They are never produced by calling the reference consumer, the validators or the stream checker; a test builds the case set with all of them disabled. A second test compares the literals with the accepted reference code as a consistency check only: it is not the oracle, and a reading of a clause shared by the literals and the code would not show up there. The literals are the authority; the audit table below records how the highest-risk ones follow from the contract text.

The seed changes only generated measurement values. Ids, clauses and expected outcomes do not depend on it. The case set covers:

- samples: valid, declared stale, missing and invalid; freshness boundaries (age 0, age equal to the limit is fresh, one ns over the limit is stale, limit 0, a timestamp 1 ns in the future, clock mismatch in both directions); declared state before freshness; structural errors before declared state and freshness; version mismatch; non-object samples; extreme valid numbers; sequence (next, gap, equal, lower, no previous, another sensor);
- streams: lifecycle (empty, no open, open not first, repeated open, sample after close, repeated close, unterminated), sequence (gap, duplicate, regression, bounds, no inference of a missing first sample), timestamp regression and equal timestamps, clock mismatch, sensor and kind change, declared states inside a stream, a sample violation, document-level errors;
- frames: chains, rotations, the inverse lookup, siblings through a common ancestor, graph-local ids, identity for a frame in the graph and not for a frame outside it, a frame missing from the graph, frames in different components, no connection assumed between `world`, `base` and `sensor`, invalid frame ids, cycle, duplicate edge, multiple parents, non-unit rotation and unsupported version (a non-conformant graph resolves nothing).

`python3 -m kritva_sense.conformance --list-cases` prints the ids, operations and clauses; it takes only `--seed`.

Audit of the highest-risk expected outcomes (hand derivation from the contract text):

| Case | Expected | Derivation |
|---|---|---|
| `sample.precedence.declared_stale_before_future` | `STALE_DATA` | SENSE_CONTRACT 6.1: a declared state decides before freshness, so the future timestamp is never evaluated |
| `sample.fresh.age_equal_to_limit` | usable | SENSE_CONTRACT 6: only an age that exceeds the limit is stale |
| `sample.structural.before_declared` | `INVALID_UNIT` | SENSE_CONTRACT 6.1: a non-conformant sample is rejected with its structural errors |
| `sample.sequence.after_freshness` | `STALE_DATA` | CONFORMANCE 1 convention (not in the contracts): sequence is evaluated last |
| `frame.resolve.rotation_up` | translation (1, 1, 0), rotation (cos 45°, 0, 0, sin 45°) | FRAME_GRAPH_CONTRACT 5: `p_parent = R p_child + t`; composing world-base (t = (1, 0, 0), 90° about z) with base-sensor (t = (1, 0, 0)) gives t = (1, 0, 0) + R (1, 0, 0) = (1, 1, 0) |
| `frame.resolve.rotation_down_is_inverse` | translation (-1, 1, 0), rotation (cos 45°, 0, 0, -sin 45°) | section 7: the reverse lookup is the inverse, `-R^-1 t`, and `R^-1` turns (1, 1, 0) into (1, -1, 0) |
| `frame.resolve.siblings_via_ancestor` | translation (1, -2, 0) | section 7: `inverse(T_world_sensor) o T_world_base` with identity rotations |
| `frame.graph.multiple_parents` | `FG_MULTIPLE_PARENTS` only | section 6: a non-conformant graph resolves nothing, even for a frame pair the conflict does not touch |
| `frame.identity.frame_not_in_graph` | `FG_FRAME_NOT_IN_GRAPH` | section 7: the identity only for a frame of the graph to itself |
| `stream.sequence.gap` | `[3, STREAM_SEQUENCE_GAP]` | STREAM_CONTRACT 6: sequence 0, 1, 5 gives c = 5 > p + 1 = 2 at record 3 (open is record 0) |
| `stream.valid.declared_states_are_conformant` | conformant | STREAM_CONTRACT 8: `STALE`, `MISSING` and `INVALID` samples are not diagnostics |

## 4. Running a consumer and failure isolation

`run_consumers({name: consumer}, seed)` runs every consumer on every case. A consumer that raises or returns an undefined decision fails that case; the other cases and the other consumers still run, and the verdict is `NOT_CONFORMANT`. Only `Exception` is caught. The exception message is not copied into the result, only its type name.

## 5. Result format

JSON with sorted keys, two-space indent and one trailing newline, byte-identical across runs for the same consumers and seed:

```
{"case_count": N, "consumers": [{"failed": n, "name": ..., "passed": n, "results": [{"actual": ..., "clause": ..., "expected": ..., "id": ..., "operation": ..., "outcome": "PASS"|"FAIL", "reason": ...}], "verdict": "CONFORMANT"|"NOT_CONFORMANT"}], "harness_version": "0.1.0", "seed": 1, "verdict": ...}
```

Consumers are in name order and results in case id order. `reason` is empty for a pass, otherwise `decision differs`, `undefined decision` (`actual` is `{"undefined_decision": <type name>}`) or `consumer raised` (`actual` is `{"error": <exception type name>}`). The overall verdict is `CONFORMANT` only when at least one consumer ran and all are conformant.

## 6. Command line

```
python3 -m kritva_sense.conformance [--consumer SPEC]... [--seed N] [--output FILE]
python3 -m kritva_sense.conformance --list-cases
```

`SPEC` is `reference` (the default), `mutant:NAME`, or `MODULE:ATTR`, a consumer object, class or zero-argument function returning one, importable from `PYTHONPATH`. The result goes to stdout or to `FILE`. Exit codes: exit 0 conformant; exit 1 not conformant; exit 2 usage or load error (unknown option, bad seed, a consumer that cannot be loaded or lacks an operation, unwritable output).

## 7. Tests

`make test-unit` runs `tests/conformance` from a clean checkout with the standard library only. The tests pin every existing contract, schema, validator, generator, frame graph and stream document by SHA-256 (change one deliberately by updating the pin in the same pull request and recording it in `planning/CHANGELOG.md`), check the interface, the case set, the reference, every mutant, the result format, failure isolation and the command line. No coverage threshold is imposed (none is approved, D-080).
