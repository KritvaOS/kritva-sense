# REV-004: kritva-sense governance baseline (V2-M0-SENSE-001)

Status: PREPARED, OWNER DECISION PENDING.
Reviewed commit: `ddf95185341656bea5f26b2f9196838321853852` (kritva-sense `main`).
Program record: REV-004 in kritva-program `v2/planning/PENDING_REVIEWS.md`.
Related plan: kritva-program `v2/planning/M0_CLOSURE_PLAN.md` and `v2/planning/M0_TASK_DEFINITIONS.md`.

This record is evidence for the owner's review. It does not accept a task, award progress, or close V2-M0-SENSE-001. Closure needs the owner's decision below and an approved `COMPLETION_RECORD.md`.

## 1. Proposed M0 task (planning only)

Title: Sense governance baseline accepted. Weight: 3. Registered as a `KOS-SENSE` task only after baseline v11 and owner approval; no placeholder row is added to `TASKS.md` before then.

| Criterion | Statement | Evidence at reviewed commit | Result |
|---|---|---|---|
| AC-M0-1 | Governance files exist: `AGENTS.md`, `ACCEPTANCE_CRITERIA.md`, `.github/CODEOWNERS`, `.github/kritva-gate.json` | Files present in the working tree at the reviewed commit | PRESENT |
| AC-M0-2 | Required checks are defined and named the same in workflows and `.github/kritva-gate.json`: `secret-scan`, `commit-message-check`, `pr-acceptance-gate`, `unit-tests` | Workflow job names match `required_github_checks` | MATCH |
| AC-M0-3 | The branch ruleset on `main` requires those checks and a pull request | GitHub settings, not visible from the repository | OWNER TO ATTEST |
| AC-M0-4 | Commit and tag policy is enforced by an automated check | `commit-message-check` workflow and its tests in `unit-tests` | PRESENT |
| AC-M0-5 | `status/status.json` agrees with `planning/TASKS.md` | KOS-SENSE-001..009 COMPLETE, 010 IN_PROGRESS in both, updated 2026-11-05 | CONSISTENT |
| AC-M0-6 | Planning records are consistent and no unimplemented gate is reported as passing | `planning/MILESTONE_STATUS.md` states the regression gate is not implemented | CONSISTENT |

## 2. CI evidence

The latest recorded `unit-tests` PASS is run 41761323273 on `55191ab`. That is not the reviewed commit. Before the owner decides, record a `unit-tests` run on `ddf95185341656bea5f26b2f9196838321853852` (or on the commit current at decision time) here:

- unit-tests run id: ____
- commit: ____
- result: ____

## 3. Owner attestations

- [ ] Ruleset on `main` requires pull request and the four checks above (AC-M0-3).
- [ ] CODEOWNERS entries are the intended approvers.

## 4. Decision

Decision: PENDING
Decided by: ____
Date: ____
Notes: ____

If approved, the program registers the Sense M0 task in baseline v11 and a `COMPLETION_RECORD.md` for V2-M0-SENSE-001 may be prepared.
