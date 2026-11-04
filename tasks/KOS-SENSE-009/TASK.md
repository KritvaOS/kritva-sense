# KOS-SENSE-009: Synthetic integration gate

| Property | Value |
|---|---|
| Milestone | V2-M2-SENSE-001 |
| Status | IN_REVIEW (implemented in pull requests #58 to #60; baselined in v8, D-099; all of KOS-SENSE-001 to KOS-SENSE-008 are accepted) |
| Weight | 6 (initial planning weight, 6 effort days, range 5 to 8; baselined in v8, D-099; effort risk: deciding which component boundaries are meaningful integration in a repository with no top-level runtime pipeline) |
| Depends on | KOS-SENSE-001 to KOS-SENSE-008 (all accepted). Direct technical dependencies: KOS-SENSE-002 to KOS-SENSE-007 |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-901 to AC-907) |
| Deliverables | `tests/integration/` with `SCENARIOS.md` (the scenario list), the integration test modules and the synthetic producer and consumer fixture, `make test-integration`, the CI step that runs it, and the documentation of the gate |
| Acceptance evidence | Closing commit 55191ab (merge of pull request #60); `unit-tests` CI run 41761323273 PASS on it (make check, docs-check, make test-unit and make test-integration as separate steps). Not yet: review record and central approval (recorded in kritva-program) |

## Purpose

The Sense components (validator, frame graph reference, generator, stream checker and conformance harness) are accepted and unit tested one by one. `make test-integration` still exits 3 (NOT_IMPLEMENTED, never a pass), and the milestone V2-M2-SENSE-001 promises an integration gate. This task writes down the boundaries between the components, tests them with deterministic synthetic data, and makes `make test-integration` a real gate.

## Scope

- `tests/integration/SCENARIOS.md`, written before the tests: each scenario names the component boundary it exercises, the synthetic input, the expected result and the contract or document clause that states the expected result. A scenario that only repeats a unit test is not an integration scenario and is not listed.
- Scenarios across the real boundaries: generator output validated by the Sense validator; generator output resolved through the frame graph reference; generated streams checked by the stream checker, with valid and faulted sequences; a synthetic consumer exercised through the conformance harness, with a conforming consumer and a deliberately faulty one; and the installed command lines chained through standard input and output as the documents describe.
- A synthetic producer and consumer fixture, built from the accepted contracts, labelled in its own text and in the documentation as a reference fixture. It is not a Mind, Motion or Skill consumer and shows nothing about any real consumer.
- Failure propagation: invalid or faulted data at each boundary produces the exit code and diagnostic that the documents state, with no traceback and no silent pass.
- `make test-integration` runs all mandatory scenarios, prints an evidence line listing the scenarios that ran, and exits non-zero on a failure, on a missing mandatory scenario, on zero tests run or on an incomplete run. The CI workflow runs it as a separate, visible step.
- No network service and no library outside the standard library; the suite runs in the network-disabled environment of KOS-SENSE-008.
- Protected paths (`Makefile`, `.github/`) are changed in separate pull requests that the owner merges, as in KOS-SENSE-008.

## Non-goals

No real sensor driver or hardware; no ROS 2, EtherCAT, network transport or robot runtime; no real Mind, Motion or Skill consumer and no claim about one; no real-time or performance guarantee; no change to any accepted contract, schema or exit code; no safety validation; no regression gate (KOS-SENSE-010); no completion record for V2-M2-SENSE-001.

## Completion boundary

Acceptance proves that the listed scenarios run deterministically on synthetic data, in CI and offline, and that `make test-integration` cannot pass when a mandatory scenario did not run. It does not prove that Sense works with any real consumer or sensor. The milestone V2-M2-SENSE-001 stays open until KOS-SENSE-010 is accepted and a separate, owner-approved completion record exists. The task is independently testable and independently accepted. Review stays the interim D-047 role, not independent, with Claude and ChatGPT as advisers only.
