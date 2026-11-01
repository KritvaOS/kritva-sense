# KOS-SENSE-006: Synthetic consumer conformance harness

| Property | Value |
|---|---|
| Milestone | V2-M7-SENSE-001 |
| Status | IN_PROGRESS (baselined in v6, D-087; KOS-SENSE-005 accepted, D-088) |
| Weight | 5 (initial planning weight, 5 effort days; baseline v6, D-087; effort risk: three interfaces, an independent oracle, mutants and failure isolation) |
| Depends on | KOS-SENSE-001 to KOS-SENSE-004 and KOS-SENSE-005 |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-601 to AC-607) |
| Deliverables | `src/kritva_sense/conformance.py`, `tests/conformance/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

A future consumer (Mind, Motion, Skill or another repository) must be able to show that it handles Sense data as the contracts say. This task adds a consumer interface and a conformance harness inside kritva-sense: given a consumer (Python callables following a documented interface), the harness feeds it deterministic synthetic samples, frame graphs and streams, compares its decisions with the decisions the contracts define, and writes a machine-readable result. It tests the contracts' consumer rules; it integrates with no real consumer.

## Scope

- A documented consumer interface of three separate operations: sample decision (conformance, declared validity, freshness and sequence context; usable, or not usable with the contract code), stream decision (lifecycle, sequence and clock rules of the stream contract) and frame resolution (a transform or the frame graph error). Inputs include `now_ns`, `now_clock` and `max_age_ns` per case.
- A reference consumer implementing the approved rules, which is the implementation under test and never the source of expected results.
- A case set derived from the contracts, not from the reference consumer: each case states its expected outcome and the contract clause it comes from. Cases are built deterministically with the generator (KOS-SENSE-004) and the stream fixtures (KOS-SENSE-005) and cover valid, stale, missing and invalid samples, freshness boundaries (age equal to the limit is fresh, future timestamp, clock mismatch, declared state before freshness), sequence and timestamp problems, version mismatch, stream lifecycle and gap cases, and frame cases (graph-local ids, missing frame, disconnected frames, cycle, non-unit rotation, identity only for a frame present in the graph, no assumed connection between `world`, `base` and `sensor`).
- Deliberately non-conforming consumers (mutants), at least one per rule class: freshness, validity precedence, sequence, stream gap handling and frame identity assumption. Each must fail at least one named case.
- Failure isolation: a consumer that raises or returns an undefined decision fails that case, and the remaining cases and consumers still run.
- A machine-readable result (JSON with sorted keys and stable ordering: case id, expected, actual, pass or fail, overall verdict) and a command line.

## Non-goals

No integration with any real Mind, Motion, Skill or other repository and no cross-repository runtime dependency; no ROS 2, hardware or hardware-in-loop; no change to any existing contract, schema, validator, generator or stream contract (the generator is reused, not modified); no shared freshness or health policy; no performance or real-time claim; the harness is not a physical sensor, robot or safety conformance test.

## Completion boundary

Acceptance proves that the harness deterministically separates conforming from non-conforming consumers on synthetic cases. It does not prove that any real consumer conforms. The task is independently testable and independently accepted: it earns no partial credit from KOS-SENSE-005. Review stays the interim D-047 role, not independent, and acceptance is recorded centrally by the authorized approver.
