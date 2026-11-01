# KOS-SENSE-008: Repository security and CI assurance review

| Property | Value |
|---|---|
| Milestone | V2-M8-SENSE-001 |
| Status | NOT_STARTED (proposed for baseline v7, D-090; all of KOS-SENSE-001 to KOS-SENSE-006 are accepted) |
| Weight | 6 (initial planning weight, 6 effort days; proposed for baseline v7, D-090; effort risk: scope creep into general infrastructure, findings that need fixes) |
| Depends on | KOS-SENSE-001 to KOS-SENSE-006 (all accepted). Acceptance prerequisite, not an implementation dependency (the baseline has no dependency field): implementation and review work on KOS-SENSE-008 may proceed independently of KOS-SENSE-007, but KOS-SENSE-008 cannot become ACCEPTED until KOS-SENSE-007 has been accepted under the program approval process, and the final review must cover the actual release artifacts produced and verified under KOS-SENSE-007 |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-801 to AC-807) |
| Deliverables | `tasks/KOS-SENSE-008/THREAT_MODEL.md`, `tasks/KOS-SENSE-008/SECURITY_REVIEW.md` (findings register and final report), `tests/security/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

Before the Sense software is called release-ready, its code and its CI are reviewed against a written threat model, the findings are recorded with a severity and a disposition, and every Critical and High finding is fixed or explicitly accepted by the risk owner. The review is internal: it is not a certification, a penetration test or a safety assessment.

## Scope

- A threat model: assets, trust boundaries, entry points (files and standard input read by the command lines, dynamically loaded consumer modules, the CI workflows and their pull request inputs, the build and release path) and stated assumptions.
- A review of input handling: JSON parsing, large or deeply nested input, file reading and writing, output paths of the command lines, resource exhaustion, and error behaviour with the exit codes the documents state.
- A review of the dynamic consumer loading of the conformance command line (`MODULE:ATTR`): it executes the code it imports, it is not a sandbox, and the documentation must say so. Regression tests use deliberately constructed temporary modules in isolated subprocesses: a valid consumer, a module that raises at import, a missing attribute, an attribute that is not callable, a module that raises when invoked, a module that hangs (with a timeout in the subprocess; timeout handling does not make loading a sandbox) and an invalid specification; no untrusted code is run.
- A review of the CI workflows and the PR gate configuration: token permissions, secrets, third-party actions and their pinning, handling of untrusted pull request input, and the protected paths.
- A review of build and dependency configuration, including confirmation that the runtime has no dependency outside the standard library and that the release artifacts of KOS-SENSE-007 contain what the release notes list.
- Security regression tests for the fixed findings, run by `make test-unit`, and an offline requirement: the mandatory test suite (`make test-unit`) runs and passes in a network-disabled environment, any test that needs the network is identified, excluded from the offline acceptance suite and justified, and a missing mandatory build tool or incomplete security check fails the CI run instead of passing.
- A findings register (unique identifier, severity and affected component, evidence and location, impact and exploitability rationale, disposition, remediation commit and retest evidence if fixed, owner disposition with rationale, residual risk and acceptance authority if not fixed) and a final report that never presents an owner-dispositioned finding as fixed. Fixes to protected paths (`.github/`, `Makefile`, `scripts/`) are made in separate pull requests that the owner merges.

## Non-goals

No third-party penetration test or certification; no cloud, GitHub organisation or service security; no hardware, firmware or robot safety; no ROS 2, network transport or real consumer security; no claim that synthetic conformance proves operational safety; no sandbox for consumer code.

## Completion boundary

Acceptance proves that the described review was done against the written threat model, that the findings are recorded, and that no Critical or High finding is open without an owner-approved disposition. It does not prove the absence of vulnerabilities. The risk owner is Dinesh; review stays the interim D-047 role, not independent, with Claude and ChatGPT as advisers only. The task is independently testable and independently accepted.
