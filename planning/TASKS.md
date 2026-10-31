# Tasks: kritva-sense

Task IDs use the prefix `KOS-SENSE` (proposed registry, program decision PD-004). Tasks here are planning inventory: no weight, no credit, until a separately approved baseline amendment. Status vocabulary: NOT_STARTED, READY, IN_PROGRESS, BLOCKED, IN_REVIEW, CHANGES_REQUESTED, ACCEPTED, DEFERRED, CANCELLED.

| Task | Title | Status | Milestone | Acceptance |
|---|---|---|---|---|
| KOS-SENSE-001 | Sense architecture and data contract | ACCEPTED (contract 0.1.0 approved as v0.1.0; central approval A076) | V2-M1-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3; [task](../tasks/KOS-SENSE-001/TASK.md) |
| KOS-SENSE-002 | Contract validation and synthetic-data tests | ACCEPTED (validator, fixtures and unit gate; depends on KOS-SENSE-001; central approval A077) | V2-M2-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3A; [task](../tasks/KOS-SENSE-002/TASK.md) |

Weights: KOS-SENSE-001 = 5 and KOS-SENSE-002 = 4, baselined in kritva-program baseline v3 (D-078) as initial planning weights; they may change later through the central amendment. Both tasks are ACCEPTED: approved by Dinesh (relayed in chat 2026-10-31; interim D-047 review, not independent) and recorded centrally as A076 and A077 in kritva-program. Acceptance is for software scope on synthetic data: it is not hardware or safety validation.

Dependency: KOS-SENSE-002 depends on KOS-SENSE-001; its validator tests the approved contract and never changes it. The central baseline has no dependency field, so the dependency is recorded here and in each `tasks/*/TASK.md`.
