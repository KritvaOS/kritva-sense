# Changelog: kritva-sense

## Unreleased

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
