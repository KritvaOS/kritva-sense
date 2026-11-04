# Acceptance Criteria: KOS-SENSE-009

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-009](TASK.md), baselined in v8 (D-099). Status of these criteria: BASELINED. They are the implementation target now that the owner has frozen the baseline that adds KOS-SENSE-009; the accepted criteria of KOS-SENSE-001 to KOS-SENSE-008 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-901 | `tests/integration/SCENARIOS.md` lists every mandatory scenario with its component boundary, synthetic input, expected result and the contract or document clause behind the expected result; the test modules name the scenario they implement, and a test checks that every listed scenario has a test and every integration test belongs to a listed scenario. | `tests/integration/`, review against the contracts |
| AC-902 | Generated samples, valid and fault-injected, are validated by the Sense validator; valid samples pass and each fault is rejected with the documented exit code and diagnostic. | integration tests |
| AC-903 | Generated samples and frame graphs are resolved through the frame graph reference, and generated streams (valid, out of order, gapped and malformed) are checked by the stream checker, each with an explicit expected result. | integration tests |
| AC-904 | A conforming synthetic consumer and a deliberately faulty one are run through the conformance harness; the conforming one passes, the faulty one fails with the expected case results, and the fixture states that it is a reference fixture and not a real consumer. | integration tests, fixture text |
| AC-905 | The installed command lines, chained through standard input and output as the documents describe, give the same results as the module interfaces; invalid input at each boundary gives the documented exit code and no traceback. | integration tests in a temporary directory, source tree unavailable where the packaging tests already do the same |
| AC-906 | `make test-integration` runs all mandatory scenarios, prints an evidence line with the scenario count and names, and exits non-zero on a failing test, a missing or skipped mandatory scenario, zero tests run, or an incomplete run; the target is no longer NOT_IMPLEMENTED; a test of the gate proves that removing a scenario makes it fail. | gate test, CI log |
| AC-907 | The CI workflow runs `make test-integration` as a separate visible step on every pull request, the suite uses only synthetic data and the standard library, and it passes in the network-disabled environment of the KOS-SENSE-008 offline test. | CI run, offline run |

## Test boundaries

All inputs are synthetic and generated with fixed seeds. No network service, external scanner or external library is required. No coverage threshold is imposed (none is approved, D-080). Nothing here validates a real consumer, a sensor, hardware or safety.

## Definition of done

AC-901 to AC-907 are demonstrated; `make check`, `docs-check`, `make test-unit` and `make test-integration` pass on the exact closing commit in CI and offline; required PR checks are green; protected-path changes were merged by the owner; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no claim about real consumers, hardware or safety is made.
