# Changelog: kritva-sense

## Unreleased

- KOS-SENSE-006 started after the acceptance of KOS-SENSE-005 (D-088; baselined in v6, D-087): status IN_PROGRESS in TASKS.md, the task record, its criteria and the status report. No contract, schema or code change. Tasks: None (status change; implementation follows in its own pull request).

- KOS-SENSE-005 ACCEPTED: central approval recorded in kritva-program (D-088) on closing commit 0bee5ed (`unit-tests` run 41278515695 PASS); stream contract 0.1.0 approved as v0.1.0. Status wording only: no contract rule, schema or code change. Tasks: None (status and approval wording; no contract or code change).

- KOS-SENSE-005 submitted for review: status IN_REVIEW with the `unit-tests` CI run 41278515695 PASS on closing commit 0bee5ed as evidence. One cross-reference in the stream contract status row is corrected (section 14, not 13); no rule, schema or code change; not accepted, and the stream contract is not yet approved. Tasks: KOS-SENSE-005.

- KOS-SENSE-005 review fixes (independent review of bce5ab5): AC-502 no longer calls `close` optional, as the contract requires one; a `sample` that is not an object is also given to the contract 0.1.0 validator; a usable timestamp now requires the unit `ns` as well as a clock and an integer value (the clock comparison needs only a recognised clock); the contract states the schema is a structural subset and that unknown record kinds are reported by the validator; the fixture for the generator's repeated-sequence fault is renamed `duplicate_then_gap_from_generator`; tests add exact positions, paths and messages, odd types and random partitions of the 10,000-record stream. No change to Sense contract 0.1.0, frame graph contract 0.1.0, the validator, the frame graph reference or the generator. Tasks: KOS-SENSE-005.

- KOS-SENSE-005: telemetry stream contract 0.1.0 (`contract/STREAM_CONTRACT.md`, `contract/stream.schema.json`) and reference validator (`src/kritva_sense/stream.py`): a document of `open`, `sample` and `close` records with a record index, lifecycle rules, `STREAM_` diagnostics for duplicate, regression and gap sequences, stated first and last sequence bounds, timestamp, clock and identity checks, an incremental checker whose result does not depend on how the records are batched, sample violations kept apart with contract 0.1.0 codes, command line `python3 -m kritva_sense.stream`; `tests/stream/` (57 fixtures with hand-written expectations, partly made with the generator) is run by `make test-unit`. Proposed, not accepted. Sense contract 0.1.0, frame graph contract 0.1.0, the validator, the frame graph reference and the generator are unchanged (pinned by tests). Tasks: KOS-SENSE-005.

- KOS-SENSE-005 started after the baseline v6 freeze (D-087): status IN_PROGRESS in TASKS.md, the task record, its criteria and the status report; KOS-SENSE-006 is baselined and stays NOT_STARTED until KOS-SENSE-005 is accepted. No contract, schema or code change. Tasks: None (status change; implementation follows in its own pull request).

- KOS-SENSE-005 and KOS-SENSE-006 planning records: task and criteria added (005 AC-501 to AC-507, telemetry stream contract and reference validator, proposed weight 4; 006 AC-601 to AC-607, consumer conformance harness, proposed weight 5, cannot start before 005 is accepted), both under milestone V2-M7-SENSE-001; to be baselined in v6 after D-087; status NOT_STARTED. No contract, schema or code change. Tasks: None (planning records; tasks not started).
- KOS-SENSE-004 ACCEPTED: central approval recorded in kritva-program (D-086) on closing commit 82b3174 (`unit-tests` run 41275942226 PASS). Status wording only: no contract, schema or code change. Tasks: None (status and approval wording; no contract or code change).

- KOS-SENSE-004 submitted for review: status IN_REVIEW with the `unit-tests` CI run 41275942226 PASS on closing commit 82b3174 as evidence. No contract, schema or code change; not accepted. Tasks: KOS-SENSE-004.

- KOS-SENSE-004 review fixes (independent review of fb4fdf6): generator checks compare complete lists of violation codes and check sequence continuity for every adjacent pair; the API refuses an invalid sensor id, clock or frame; rotations no longer use `sin` and `cos`, and the determinism claim is narrowed to exactly rounded operations on IEEE 754 platforms (separate-process test added); encoder range stays inside the angle range; duplicate `--fault` indices are refused; the two normative contract documents are pinned by SHA-256 in the tests. Generator output for graphs differs from fb4fdf6 (seed values are not stable across this fix, as the task has no accepted evidence yet). No contract, schema or accepted-code change. Tasks: KOS-SENSE-004.

- KOS-SENSE-003 ACCEPTED: central approval recorded in kritva-program (D-085) on closing commit c92e841 (`unit-tests` run 41267842700 PASS); frame graph contract 0.1.0 approved as v0.1.0. Status wording only: no contract rule, schema or code change. Tasks: None (status and approval wording; no contract or code change).

- KOS-SENSE-004: deterministic synthetic sample and frame graph generator (`src/kritva_sense/generator.py`, documented in `src/kritva_sense/GENERATOR.md`): SplitMix64 PRNG implemented in the repository, valid samples for every sensor kind, explicitly requested faults with the stated contract code, conformant and defective frame graphs, Python API and command line; `tests/generator/` is run by `make test-unit`. Proposed, not accepted. Sense contract 0.1.0, frame graph contract 0.1.0 and their schemas are unchanged (pinned by tests). Tasks: KOS-SENSE-004.

- KOS-SENSE-004 started after the baseline v5 freeze (D-083): status IN_PROGRESS in TASKS.md, the task record, its criteria and the status report. No contract, schema or code change. Tasks: None (status change; implementation follows in its own pull request).

- KOS-SENSE-004 planning records: task and criteria AC-401 to AC-407 added (proposed; to be baselined in v5 after D-083; status NOT_STARTED). No contract, schema or code change. Tasks: None (planning records; task not started).

- KOS-SENSE-003 submitted for review: status IN_REVIEW with the `unit-tests` CI run 41267842700 PASS on closing commit c92e841 as evidence. No contract, schema or code change; not accepted. Tasks: KOS-SENSE-003.

- KOS-SENSE-003: frame graph contract 0.1.0 (`contract/FRAME_GRAPH_CONTRACT.md`, `contract/frame-transform.schema.json`), reference implementation (`src/kritva_sense/frame_graph.py`: validation, deterministic composition and inversion, no assumed identity), 42 synthetic fixtures and `tests/frame_graph/`; `make test-unit` runs them. Proposed, not accepted. Sense contract 0.1.0 and its schema are unchanged (pinned by a test). Tasks: KOS-SENSE-003.

- Documentation reconciliation after the baseline v4 freeze: KOS-SENSE-003 task and criteria moved from proposed to READY (D-082), the scope states that graph-local frame ids are allowed in a frame graph (samples cannot use them), AC-302 says invalid frame identifiers, and the stale README, TASKS, MILESTONE_STATUS and status wording (task registry approved by D-080, weights baselined centrally, V2-M0 and V2-M5 status, 001 evidence description) is corrected. No contract, schema or code change. Tasks: None (documentation reconciliation; no contract or code change).

- KOS-SENSE-003 planning records: task and criteria AC-301 to AC-307 added (proposed; baselined in v4, D-082; status NOT_STARTED). No contract, schema or code change. Tasks: None (planning records; task not started).

- Documentation reconciliation after the external audit: README implementation state, milestone status, task evidence wording, the contract section 5 and 8 wording and a status evidence note. No contract, schema or code change. Tasks: None (documentation reconciliation; no contract or code change).

- KOS-SENSE-001 and KOS-SENSE-002 ACCEPTED: central approvals A076 and A077 (kritva-program, evidence run 40994325092 on e949b9f); contract 0.1.0 approved by the owner as v0.1.0 (interim D-047 review; relayed in chat 2026-10-31); the owner creates the annotated tag `v0.1.0` after merge. Tasks: None (status and wording after approval; no contract or code change).

- Status report cites the `unit-tests` CI run 40994325092 (PASS on e949b9f) as evidence for KOS-SENSE-001 and KOS-SENSE-002; a CI run is a fact about a commit, not acceptance. Tasks: KOS-SENSE-002.

- Status report lists KOS-SENSE-001 and KOS-SENSE-002 (execution COMPLETE = submitted for review, not accepted); `unit-tests` workflow runs `make check docs-check test-unit`; status consistency tests added; task statuses set to IN_REVIEW. Tasks: KOS-SENSE-002.

- KOS-SENSE-001 audit fixes: frame semantics and an IMU example, context-dependent checks (section 6.1), schema scoped as a structural subset, AC-005 aligned with the 0.x versioning rule, unit-gate table row repaired. Tasks: KOS-SENSE-001.

- KOS-SENSE-001 draft: Sense data contract 0.1.0 (`contract/SENSE_CONTRACT.md`) and machine-readable schema. Proposed, not accepted or tagged. Tasks: KOS-SENSE-001.
- KOS-SENSE-002 draft: reference validator (`src/kritva_sense/`), 31 synthetic fixtures and unit tests; `make test-unit` implemented. Task rows and criteria AC-201 to AC-206 added. Tasks: KOS-SENSE-002.

- Stage 1 status reporting: `status/status.json` (schema 2.0, empty task list) added in PR #8; registered as a program status source (program decision D-077). No task, weight or credit. Tasks: None (cross-repository governance, not KOS-SENSE-001).

- Governance baseline: acceptance criteria, planning files, CI checks, CODEOWNERS, AGENTS.md, SECURITY.md (Task: KOS-SENSE-001 planning; program milestone V2-M0-SENSE-001).
