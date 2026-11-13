# KOS-SENSE-010: Regression gate and compatibility suite

| Property | Value |
|---|---|
| Milestone | V2-M2-SENSE-001 |
| Status | ACCEPTED (implemented in pull requests #63, #69 and #72; baselined in v8, D-099; central approval D-127; KOS-SENSE-009 accepted by D-101, so the acceptance prerequisite is met) |
| Weight | 5 (initial planning weight, 5 effort days, range 4 to 7; baselined in v8, D-099; effort risk: deciding which behaviours are compatibility guarantees takes longer than writing the tests, and tests must not freeze accidental implementation details) |
| Depends on | KOS-SENSE-001 to KOS-SENSE-009 (all accepted; KOS-SENSE-009 by D-101). Acceptance prerequisite, not an implementation dependency (the baseline has no dependency field): KOS-SENSE-010 could not become ACCEPTED until KOS-SENSE-009 was accepted, because the aggregate gate runs the integration gate; that prerequisite is met |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-1001 to AC-1007) |
| Deliverables | `tests/regression/` with `REGRESSION_INVENTORY.md`, the regression test modules and golden data, `make test-regression`, the aggregate `make test`, the CI step that runs them, and the documentation of what counts as a regression |
| Acceptance evidence | Closing commit a072cee (squash merge of pull request #72); `unit-tests` CI run 43139244187 PASS on it (make check, docs-check, make test-unit, and make test-integration and make test-regression as separate steps). The log shows all 16 mandatory regression cases and all 10 integration scenarios running. Central approval D-127 (approval A494 on baseline v13) is recorded in kritva-program; review was the interim D-047 role, not independent |

## Purpose

Accepted behaviour and fixed defects must stay fixed. `make test-regression` and `make test` still exit 3 (NOT_IMPLEMENTED, never a pass). This task defines what a regression is for Sense, maps each protected behaviour to an executable test, and makes `make test-regression` and the aggregate `make test` real gates, so that a missing gate can never be read as success.

## Scope

- `tests/regression/REGRESSION_INVENTORY.md`: each entry names its source (a finding of `tasks/KOS-SENSE-008/SECURITY_REVIEW.md`, a contract clause, a documented exit code or a documented command line behaviour), the protected behaviour and the test that protects it. Existing tests are referenced rather than duplicated; the inventory states which are reused.
- Prior defect protection: the fixed findings of KOS-SENSE-008 that are testable (F-001 recursion limit exit, F-002 `SystemExit` handling in the harness, F-003 generator count cap) and any fixed defect recorded by the earlier reviews.
- Contract compatibility: the accepted Sense, frame graph and stream contracts 0.1.0 are protected by pinned hashes of the contract documents and schemas and by golden valid and invalid cases; a change to a protected contract file fails the suite until the contract version, the changelog, the golden data and a central decision are updated together, as the V2 acceptance standard requires.
- Command line compatibility: the documented exit codes, diagnostics and options of the five command lines and the version command.
- Determinism: generator, stream and conformance outputs for fixed seeds and fixed inputs are compared with golden results; the golden data are regenerated only by an explicit, documented step.
- `make test-regression` fails on a failing test, a missing mandatory regression case, zero tests run or an incomplete run, and prints an evidence line. The aggregate `make test` runs `test-unit`, `test-integration` and `test-regression`, shows the three results separately, and exits non-zero if any one fails, is missing or is incomplete. `make acceptance` is out of scope and stays NOT_IMPLEMENTED.
- A short, written rule of what counts as a regression and what needs a contract version, a changelog entry and a central decision.
- Protected paths (`Makefile`, `.github/`) are changed in separate pull requests that the owner merges, as in KOS-SENSE-008.

## Non-goals

No change to any accepted contract semantics; no compatibility promise for undocumented Python internals; no real sensor, robot or consumer testing; no replacement or duplication of the whole unit suite; no coverage threshold (none is approved); no `make acceptance`; no completion record for V2-M2-SENSE-001.

## Completion boundary

Acceptance proves that the listed behaviours and fixed defects are protected by tests that fail when they change, that the gates cannot pass when they did not run, and that the aggregate `make test` reports all three gates. It does not prove the absence of other defects. When KOS-SENSE-009 and KOS-SENSE-010 are both accepted and all three gates pass on one closing commit, the owner may approve a completion record for V2-M2-SENSE-001; that record is separate from this task. Review stays the interim D-047 role, not independent, with Claude and ChatGPT as advisers only.
