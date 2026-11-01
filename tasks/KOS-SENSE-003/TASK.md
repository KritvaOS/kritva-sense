# KOS-SENSE-003: Deterministic frame graph and transform validation for simulated samples

| Property | Value |
|---|---|
| Milestone | V2-M5-SENSE-001 |
| Status | IN_PROGRESS (baselined in v4, D-082) |
| Weight | 5 (initial planning weight, 4 to 5 effort days; baseline v4, D-082) |
| Depends on | KOS-SENSE-001 and KOS-SENSE-002 (Sense contract 0.1.0, tag `v0.1.0`) |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-301 to AC-307) |
| Deliverables | `contract/FRAME_GRAPH_CONTRACT.md`, `contract/frame-transform.schema.json`, `src/kritva_sense/frame_graph.py`, `tests/frame_graph/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

Sense contract 0.1.0 names the frames `world`, `base` and `sensor` but defines no relationship between them, and says consumers must not infer one. This task adds a separate, versioned frame graph contract and a standard-library reference implementation, so relationships between those frames can be stated, validated and resolved deterministically on synthetic data. Contract 0.1.0 is not changed.

## Scope

- A versioned, machine-readable transform record: parent frame, child frame, translation in metres, rotation as one unit quaternion form, with the direction stated.
- Frame graph rules: each frame has at most one parent; no self-links, duplicates or cycles; the three frames of contract 0.1.0 (`world`, `base`, `sensor`) keep their meaning, and other graph-local frame ids (lowercase identifiers) are allowed in a graph; samples cannot refer to them, and the sample contract is unchanged.
- Validation with deterministic, documented error codes.
- Deterministic resolution between two connected frames (composition) and its inverse; an unknown or disconnected relationship is an error, never an assumed identity.
- Synthetic fixtures (valid and invalid graphs), known-answer tests and a repeatable `make test-unit`.

## Non-goals

No hardware, robot, actuator or hardware-in-loop work; no safety, calibration or physical-correctness claim; no change to contract 0.1.0; no ROS or external transform library; no real-time distribution or telemetry; no estimation, SLAM, localization or fusion; no calibration of mounting offsets; no shared sensor-health or freshness policy; no integration with Mind, Motion or Skill.

## Completion boundary

Acceptance proves deterministic software behaviour on synthetic frame graphs only. It does not prove that any physical frame, mounting transform, calibration or robot coordinate system is correct. Review stays the interim D-047 role, not independent, and acceptance is recorded centrally by the authorized approver.
