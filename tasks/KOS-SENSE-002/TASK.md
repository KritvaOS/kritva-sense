# KOS-SENSE-002: Contract validation and synthetic-data tests

| Property | Value |
|---|---|
| Milestone | V2-M2-SENSE-001 |
| Status | ACCEPTED (validator, fixtures and unit gate; baselined in v3, D-078; central approval A077) |
| Weight | 4 (initial planning weight, 3 to 4 effort days; baselined in v3, D-078) |
| Depends on | KOS-SENSE-001 (the validator implements the approved contract and never changes it) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](../../ACCEPTANCE_CRITERIA.md) section 3A (AC-201 to AC-206) |
| Deliverables | `src/kritva_sense/`, `tests/contract/`, `make test-unit` |
| Evidence needed | `make test-unit` from a clean checkout at the closing SHA, CI runs, review record |

Out of scope: integration and regression gates, hardware-in-loop, safety validation of physical sensors, coverage thresholds.
