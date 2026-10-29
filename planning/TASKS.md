# Tasks: kritva-sense

Task IDs use the prefix `KOS-SENSE` (proposed registry, program decision PD-004). Tasks here are planning inventory: no weight, no credit, until a separately approved baseline amendment. Status vocabulary: NOT_STARTED, READY, IN_PROGRESS, BLOCKED, IN_REVIEW, CHANGES_REQUESTED, ACCEPTED, DEFERRED, CANCELLED.

| Task | Title | Status | Milestone | Acceptance |
|---|---|---|---|---|
| KOS-SENSE-001 | Sense architecture and data contract | IN_PROGRESS (draft contract 0.1.0; central baselining pending) | V2-M1-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3; [task](../tasks/KOS-SENSE-001/TASK.md) |
| KOS-SENSE-002 | Contract validation and synthetic-data tests | NOT_STARTED (proposed; depends on KOS-SENSE-001; central baselining pending) | V2-M2-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3A; [task](../tasks/KOS-SENSE-002/TASK.md) |

Proposed planning weights (estimates only, not baselined, no credit; to be revised through the central amendment): KOS-SENSE-001 = 5 (4 to 5 effort days), KOS-SENSE-002 = 4 (3 to 4 effort days). Owner direction to proceed was recorded in chat on 2026-10-29; the formal baseline amendment, decision record and approval stay in kritva-program (`v2/planning/KOS_SENSE_001_BASELINING_PLAN.md`).

Dependency: KOS-SENSE-002 depends on KOS-SENSE-001; its validator tests the approved contract and never changes it. The central baseline has no dependency field, so the dependency is recorded here and in each `tasks/*/TASK.md`. KOS-SENSE-001 is drafted and under review, KOS-SENSE-002 starts in its own pull request once this task row is on `main`. Neither is ACCEPTED, and `status/status.json` keeps an empty task list until the baseline amendment is approved.
