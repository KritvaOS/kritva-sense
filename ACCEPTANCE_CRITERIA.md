# Acceptance Criteria: kritva-sense

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (proposed; approval pending PD-005, PD-006). Criteria in section 3 are for task KOS-SENSE-001 (Sense architecture and data contract) and criteria in section 3A for KOS-SENSE-002 (Contract validation and synthetic-data tests). Both are proposed until the owner approves the tasks. Nothing here is accepted, weighted or credited.

## 1. Purpose and scope

Owns: sensor identity, timestamps, units, frame and coordinate conventions, validity and stale-data behaviour, errors and versioning of the Sense data contract and its reference validation.

Does not own: motion commands (kritva-motion), inference (kritva-mind), skill orchestration (kritva-skill), device drivers below the contract, and the platform foundation (kritva-core).

## 2. Normative dependencies

kritva-core (approved contract), kritvaos-community (public architecture description). Contract 0.1.0 has no normative dependency on either, so no version or commit SHA is pinned (stated in `contract/SENSE_CONTRACT.md` section 2). A pin is recorded here when a dependency on an approved contract is introduced. KOS-SENSE-002 depends on KOS-SENSE-001: its validator implements the approved contract and never alters it.

## 3. Functional criteria (KOS-SENSE-001)

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-001 | Every sensor stream declares a stable sensor identity and a contract version. | contract review |
| AC-002 | Every sample carries a timestamp with a stated clock and unit; units use one stated system. | contract review, validation tests |
| AC-003 | Frame and coordinate conventions are defined once and referenced, never implied. | contract review |
| AC-004 | Validity, stale-data and missing-data behaviour is specified, with an error for each failure. | contract review, fault-path tests |
| AC-005 | A breaking contract change needs a new MAJOR version, a changelog entry and an approved decision. | review, regression suite |

## 3A. Functional criteria (KOS-SENSE-002)

Synthetic data only. No real sensor, hardware-in-loop or safety validation is required or claimed.

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-201 | A reference validator checks samples against the SENSE-001 contract and version; schema and validator constants agree. | `make test-unit` |
| AC-202 | Synthetic fixtures for valid samples of every sensor kind pass, including identity, timestamp, units, frame and version fields. | `make test-unit` |
| AC-203 | Fixtures with missing or malformed fields, invalid timestamps or units, and unsupported versions are rejected with deterministic, documented error codes. | `make test-unit` |
| AC-204 | Stale, missing and invalid data and sequence regression are asserted explicitly against the contract's errors. | `make test-unit` |
| AC-205 | `make test-unit` runs from a clean checkout, exits non-zero on failure and passes on the approved closing commit. | `make test-unit`, CI |
| AC-206 | Validator, fixtures, test instructions and expected outcomes are documented; results and CI are bound to immutable commit SHAs. | review |

## 4. Interface and API compatibility

The contract defines inputs, outputs, error handling, versioning and lifecycle, with time and units stated. Contracts are versioned independently of program phases. No import of mind, skill or motion internals; consumers (mind) use the versioned contract only.

## 5. Test gates

| Gate | Command | Required result | State |
|---|---|---|---|
| Unit | `make test-unit` | all pass NOT_IMPLEMENTED until KOS-SENSE-002 (Contract validation and synthetic-data tests) |
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
- No coverage threshold is set; one needs an approved decision.
- The architecture and safety reviewer roles are held by the owner on an interim basis (program decision D-047, resolving PD-007); independent review is not yet in place.
- Licence: Apache-2.0, confirmed by the owner (program decision D-064, closing PD-013).

## 10. Change control

Accepted criteria are never edited. A change is a new criteria version with its own review; accepted evidence keeps the version it was produced under.
