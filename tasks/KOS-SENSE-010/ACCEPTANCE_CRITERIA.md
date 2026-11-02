# Acceptance Criteria: KOS-SENSE-010

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-010](TASK.md), proposed for baseline v8. Status of these criteria: PROPOSED. They become the implementation target only after the owner freezes the baseline that adds KOS-SENSE-010; until then they are a draft, and the accepted criteria of KOS-SENSE-001 to KOS-SENSE-008 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-1001 | `tests/regression/REGRESSION_INVENTORY.md` maps every protected behaviour to its source (finding, contract clause, documented exit code or command line behaviour) and to the test that protects it, and a test checks that every inventory entry has a test and every regression test has an entry. | `tests/regression/`, review |
| AC-1002 | The testable fixed findings F-001, F-002 and F-003 of KOS-SENSE-008 each have a regression test that fails on the pre-fix behaviour (shown once by a recorded mutation check) and passes on the current code. | regression tests, mutation record |
| AC-1003 | The accepted Sense, frame graph and stream contracts 0.1.0 are protected: the hashes of the contract documents and schemas are pinned, golden valid and invalid cases pass, and changing a protected file without the version, golden data and changelog update fails the suite. | regression tests |
| AC-1004 | The documented exit codes, diagnostics and options of the five command lines and the version command are protected by tests that run the commands. | regression tests |
| AC-1005 | Generator, stream and conformance outputs for fixed seeds and inputs equal the golden results byte for byte; the golden data can be regenerated only by a documented explicit step, which the suite never runs. | regression tests, documentation |
| AC-1006 | `make test-regression` is no longer NOT_IMPLEMENTED; it exits non-zero on a failing test, a missing mandatory regression case, zero tests run or an incomplete run, prints an evidence line, and a test of the gate proves that removing a case makes it fail. | gate test, CI log |
| AC-1007 | `make test` runs `test-unit`, `test-integration` and `test-regression`, reports the three results separately, and exits non-zero if any one fails, is missing or is incomplete; CI runs the three as separate visible steps; the written rule of what counts as a regression is in the documentation. | gate test, CI run |

## Test boundaries

All inputs are synthetic and generated with fixed seeds. No network service or external library is required, and the suite runs offline. No coverage threshold is imposed (none is approved, D-080). Regression tests protect documented contracts, fixed defects and accepted external behaviour, not internal functions.

## Definition of done

AC-1001 to AC-1007 are demonstrated; `make test` passes on the exact closing commit in CI and offline with all three gates visible; required PR checks are green; protected-path changes were merged by the owner; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no claim about real consumers, hardware or safety is made.
