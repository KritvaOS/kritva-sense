# Tasks: kritva-sense

Task IDs use the prefix `KOS-SENSE` (task registry approved by program decision D-080, which approved PD-004). Weights are set centrally in the kritva-program baseline (v4, D-082); a task earns credit only through a central approval bound to immutable evidence, never from this file. Status vocabulary: NOT_STARTED, READY, IN_PROGRESS, BLOCKED, IN_REVIEW, CHANGES_REQUESTED, ACCEPTED, DEFERRED, CANCELLED.

| Task | Title | Status | Milestone | Acceptance |
|---|---|---|---|---|
| KOS-SENSE-001 | Sense architecture and data contract | ACCEPTED (contract 0.1.0 approved as v0.1.0; central approval A076) | V2-M1-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3; [task](../tasks/KOS-SENSE-001/TASK.md) |
| KOS-SENSE-002 | Contract validation and synthetic-data tests | ACCEPTED (validator, fixtures and unit gate; depends on KOS-SENSE-001; central approval A077) | V2-M2-SENSE-001 | [ACCEPTANCE_CRITERIA.md](../ACCEPTANCE_CRITERIA.md) section 3A; [task](../tasks/KOS-SENSE-002/TASK.md) |
| KOS-SENSE-003 | Deterministic frame graph and transform validation for simulated samples | IN_PROGRESS (baselined in v4, D-082; depends on KOS-SENSE-001 and KOS-SENSE-002) | V2-M5-SENSE-001 | [criteria](../tasks/KOS-SENSE-003/ACCEPTANCE_CRITERIA.md); [task](../tasks/KOS-SENSE-003/TASK.md) |

Weights: KOS-SENSE-001 = 5 and KOS-SENSE-002 = 4 (baseline v3, D-078) and KOS-SENSE-003 = 5 (baseline v4, D-082), all initial planning weights; they may change later through the central amendment. KOS-SENSE-001 and KOS-SENSE-002 are ACCEPTED: approved by Dinesh (relayed in chat 2026-10-31; interim D-047 review, not independent) and recorded centrally as A076 and A077 in kritva-program. Acceptance is for software scope on synthetic data: it is not hardware or safety validation.

Dependency: KOS-SENSE-002 depends on KOS-SENSE-001; its validator tests the approved contract and never changes it. The central baseline has no dependency field, so the dependency is recorded here and in each `tasks/*/TASK.md`.
