# REV-004: kritva-sense governance baseline (V2-M0-SENSE-001)

Status: APPROVED by the owner (D-114, 2026-11-07); ruleset and CODEOWNERS verified against GitHub on 2026-11-07 (D-115).
Reviewed commit: `ddf95185341656bea5f26b2f9196838321853852` (kritva-sense `main`).
Program record: REV-004 in kritva-program `v2/planning/PENDING_REVIEWS.md`.
Related plan: kritva-program `v2/planning/M0_CLOSURE_PLAN.md` and `v2/planning/M0_TASK_DEFINITIONS.md`.

This record is evidence for the owner's review. It does not accept a task, award progress, or close V2-M0-SENSE-001. Closure needs the owner's decision below and an approved `COMPLETION_RECORD.md`.

## 1. Proposed M0 task (planning only)

Title: Sense governance baseline accepted. Weight: 3. Registered as a `KOS-SENSE` task only after baseline v11 and owner approval; no placeholder row is added to `TASKS.md` before then.

| Criterion | Statement | Evidence at reviewed commit | Result |
|---|---|---|---|
| AC-M0-1 | Governance files exist: `AGENTS.md`, `ACCEPTANCE_CRITERIA.md`, `.github/CODEOWNERS`, `.github/kritva-gate.json` | Files present in the working tree at the reviewed commit | PRESENT |
| AC-M0-2 | Required checks are defined and named the same in workflows, `.github/kritva-gate.json` and the ruleset: `secret-scan`, `commit-message-check`, `pr-acceptance-gate`, `unit-tests`, `readme-check` | Workflow job names match `required_github_checks`. The ruleset also requires `readme-check`; the gate file was aligned by PR #65 | MATCH (PR #65 merged) |
| AC-M0-3 | The branch ruleset on `main` requires a pull request and the required checks. The approval roles `REPO_CODE_OWNER` and `ARCHITECTURE_REVIEWER` are held by the owner on an interim basis (D-047) and are not enforced by the ruleset (D-115) | Checked 2026-11-07 through the GitHub rulesets API: ruleset `protect-main` is active on the default branch, blocks deletion and force-push, requires a pull request with 0 approving reviews and no code-owner review, and requires pr-acceptance-gate, commit-message-check, readme-check, secret-scan, unit-tests. Bypass actors are not visible without admin access | PARTIAL: pull request and checks verified; approvals not enforced |
| AC-M0-4 | Commit and tag policy is enforced by an automated check | `commit-message-check` workflow and its tests in `unit-tests` | PRESENT |
| AC-M0-5 | `status/status.json` agrees with `planning/TASKS.md` | KOS-SENSE-001..009 COMPLETE, 010 IN_PROGRESS in both, updated 2026-11-05 | CONSISTENT |
| AC-M0-6 | Planning records are consistent and no unimplemented gate is reported as passing | `planning/MILESTONE_STATUS.md` states the regression gate is not implemented | CONSISTENT |

## 2. CI evidence

Recorded 2026-11-07 from the GitHub check runs on the reviewed commit:

- unit-tests run id: 42329065787
- commit: `ddf95185341656bea5f26b2f9196838321853852`
- result: success (push run on `main`; `secret-scan` run 42329065890 and `readme-check` run 42329065934 also succeeded). `commit-message-check` and `pr-acceptance-gate` run on pull requests, so they have no run on this commit.

## 3. Verification of ruleset and CODEOWNERS (2026-11-07)

- Ruleset: verified as stated in AC-M0-3. The approval requirement is not enforced; the owner merges under the interim reviewer roles of D-047.
- CODEOWNERS: verified. `*` and the protected files (`.github/`, `SECURITY.md`, `LICENSE`, `ACCEPTANCE_CRITERIA.md`) are owned by `@dineshannayya`. GitHub does not enforce code-owner review because the ruleset does not require it.
- Not verified: bypass actors (admin access needed).

## 4. Decision

Decision: APPROVED (owner, interim reviewer roles of D-047; recorded in D-114 on 2026-11-07; verification in D-115)
Decided by: Dinesh
Date: 2026-11-07
Notes: This is not independent review.

If approved, the program registers the Sense M0 task in baseline v11 and a `COMPLETION_RECORD.md` for V2-M0-SENSE-001 may be prepared.
