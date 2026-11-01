# KOS-SENSE-004: Deterministic synthetic sensor sample generator

| Property | Value |
|---|---|
| Milestone | V2-M2-SENSE-001 |
| Status | NOT_STARTED (proposed; to be baselined in v5 by the owner-run freeze after decision D-083) |
| Weight | 4 (initial planning weight, 4 to 5 effort days; proposed for baseline v5, D-083) |
| Depends on | KOS-SENSE-001, KOS-SENSE-002 (Sense contract 0.1.0, tag `v0.1.0`) and KOS-SENSE-003 (frame graph contract 0.1.0) |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-401 to AC-407) |
| Deliverables | `src/kritva_sense/generator.py`, `tests/generator/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

Tests of Sense contract 0.1.0 and of the frame graph contract 0.1.0 use hand-written fixtures. This task adds a standard-library generator that produces reproducible synthetic samples and frame graphs from a seed, so later tasks (a stream contract, a consumer conformance harness) can share one source of synthetic data instead of each writing its own. The generator produces data; it does not define or change any contract.

## Scope

- A documented pseudo-random generator that is implemented in this repository (not Python's `random` module), so the same seed gives byte-identical output on every supported Python version and platform.
- Generation of valid samples for every sensor kind of contract 0.1.0 (`imu`, `range`, `encoder`, `temperature`) with configurable sensor id, start sequence, timestamps (clock and step in nanoseconds) and frame.
- Generation of sample sequences with deliberately introduced conditions, each chosen explicitly and never at random by default: stale, missing and invalid validity states, sequence regression and sequence gaps, and boundary values.
- Generation of conformant frame graphs and of graphs with a stated defect (cycle, duplicate edge, multiple parents, non-unit rotation), using the frame graph contract 0.1.0.
- A reusable Python API and a command line that writes JSON, with a documented output format.
- Every generated artefact is checked by the reference validators: generated valid data must pass, and generated defective data must be rejected with the code the generator states for it.

## Non-goals

No change to Sense contract 0.1.0 or to the frame graph contract 0.1.0, or to their schemas, validators or accepted criteria; no real sensor driver, hardware, robot, actuator or hardware-in-loop work; no physical or sensor-noise model and no accuracy, calibration or safety claim; no transport, telemetry stream, streaming or real-time behaviour; no ROS or external library; no shared freshness or sensor-health policy; no integration with Mind, Motion or Skill.

## Completion boundary

Acceptance proves deterministic software behaviour on synthetic data only. Generated values are plausible in form, not physically meaningful, and are not a model of any real sensor. Review stays the interim D-047 role, not independent, and acceptance is recorded centrally by the authorized approver.
