# Acceptance Criteria: kritva-sense

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (proposed; approval pending PD-005, PD-006). Criteria below are for task KOS-SENSE-001 (Sense architecture and data contract) and are proposed until the owner approves the task. Nothing here is accepted, weighted or credited.

## 1. Purpose and scope

Owns: sensor identity, timestamps, units, frame and coordinate conventions, validity and stale-data behaviour, errors and versioning of the Sense data contract and its reference validation.

Does not own: motion commands (kritva-motion), inference (kritva-mind), skill orchestration (kritva-skill), device drivers below the contract, and the platform foundation (kritva-core).

## 2. Normative dependencies

kritva-core (approved contract), kritvaos-community (public architecture description). Exact versions or commit SHAs are recorded here when the contracts they refer to are approved; none are pinned yet.

## 3. Functional criteria (KOS-SENSE-001)

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-001 | Every sensor stream declares a stable sensor identity and a contract version. | contract review |
| AC-002 | Every sample carries a timestamp with a stated clock and unit; units use one stated system. | contract review, validation tests |
| AC-003 | Frame and coordinate conventions are defined once and referenced, never implied. | contract review |
| AC-004 | Validity, stale-data and missing-data behaviour is specified, with an error for each failure. | contract review, fault-path tests |
| AC-005 | A breaking contract change needs a new MAJOR version, a changelog entry and an approved decision. | review, regression suite |

## 4. Interface and API compatibility

The contract defines inputs, outputs, error handling, versioning and lifecycle, with time and units stated. Contracts are versioned independently of program phases. No import of mind, skill or motion internals; consumers (mind) use the versioned contract only.

## 5. Test gates

| Gate | Command | Required result | State |
|---|---|---|---|
| Unit | `make test-unit` | all pass | NOT_IMPLEMENTED until KOS-SENSE-002 (Contract validation and synthetic-data tests) |
| Integration | `make test-integration` | all pass, real dependency boundaries | NOT_IMPLEMENTED |
| Regression | `make test-regression` | all pass, suite unchanged by the change | NOT_IMPLEMENTED |
| Structure | `make check` | planning files present, commit checker self-test passes | implemented |

An unimplemented gate is reported as NOT_IMPLEMENTED and is never counted as a pass. No coverage threshold is set; one needs an approved decision.

## 6. Specialised gates

Determinism and error-path behaviour apply to every criterion above. No hardware-in-loop or physical validation applies: any such claim stays gated on program milestone V2-M6 (HOLD).

## 7. Evidence requirements

Immutable commit SHAs, CI run IDs for secret-scan, commit-message-check and the test gates, and the review record against the closing commit.

## 8. Definition of Done

As in the program standard section 1: stable task ID, merged through the approved PR, required checks green on the exact closing commit, reviews recorded, documentation and changelog updated, immutable evidence, no blocker converted into a pass.

## 9. Known limitations and exclusions

- No implementation exists; criteria are not yet testable by automated gates (gates listed NOT_IMPLEMENTED).
- No architecture or safety reviewer is assigned (program decision PD-007).
- Licence for this repository is undecided (program decision PD-013).

## 10. Change control

Accepted criteria are never edited. A change is a new criteria version with its own review; accepted evidence keeps the version it was produced under.
