# Acceptance Criteria: KOS-SENSE-008

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-008](TASK.md), baselined in v7 (D-090). Status of these criteria: the implementation target for KOS-SENSE-008 since the baseline v7 freeze was merged and KOS-SENSE-007 was accepted (D-091); they are accepted by the central approval D-092 on closing commit a8dfb5a (`unit-tests` run 41298259048 PASS); the accepted criteria of KOS-SENSE-001 to KOS-SENSE-007 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-801 | `THREAT_MODEL.md` identifies the assets, trust boundaries, entry points and assumptions of the repository as it is (commands, loaded modules, CI workflows, build and release path); each entry point names the code or workflow it refers to. | review against the code and workflows |
| AC-802 | The command line, file and JSON input paths are reviewed for malformed, oversized and deeply nested input, path misuse and resource exhaustion; each finding or confirmed non-issue is recorded and covered by a test where it is testable. | tests in `tests/security/`, review record |
| AC-803 | Dynamic consumer loading is reviewed: import-time execution, an invalid specification, a missing or non-callable attribute, a module that raises at import or when invoked, and a module that hangs (tested in a subprocess with a timeout). The documentation and the report state that it is not a sandbox and that timeout handling does not make it one. Controlled temporary modules are used; no untrusted code is run. | tests with controlled modules in subprocesses, documentation review |
| AC-804 | Every CI workflow is reviewed for token permissions, secrets, third-party actions and their pinning, and untrusted pull request input; the PR gate configuration and the protected paths are reviewed; results are recorded per workflow. | workflow inspection, automated policy check where one is practical |
| AC-805 | Build and dependency configuration is reviewed; an automated check confirms the runtime dependencies are empty and that the KOS-SENSE-007 release artifacts contain only the listed files; the mandatory test suite runs and passes in a network-disabled environment, and a test that needs the network is identified, excluded from the offline suite and justified. | automated inspection, network-disabled test run, `make test-unit` |
| AC-806 | The findings register records for every finding a unique identifier, severity and affected component, evidence and location, impact rationale, and either the remediation commit with retest evidence or the owner disposition with rationale, residual risk and acceptance authority; no Critical or High finding is open unless the risk owner (Dinesh) has recorded an explicit disposition, and the report states that such a finding is not fixed and its residual risk is accepted. | register review, retest results |
| AC-807 | Security regression tests and the final report are committed; the report states scope, method, limits and the explicit non-claims (no certification, no sandbox, no safety claim); `make test-unit` and the security tests pass in CI on the exact closing commit and in a network-disabled run, and a missing mandatory build tool or an incomplete security check fails CI; the final review covers the actual release artifacts verified under KOS-SENSE-007, and KOS-SENSE-007 is accepted before this task becomes ACCEPTED (an acceptance prerequisite, not a dependency field). | `make test-unit`, CI, report review |

## Test boundaries

All inputs are synthetic. No network service, external scanner or external library is required for the tests. Optional external tools used during the review are named in the report and are not part of acceptance. No coverage threshold is imposed (none is approved, D-080).

## Definition of done

AC-801 to AC-807 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no claim of certification, safety or absence of vulnerabilities is made.
