# Acceptance Criteria: KOS-SENSE-003

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-003](TASK.md), baselined in v4 (D-082). Status of these criteria: PROPOSED until the task is approved centrally; the accepted criteria of KOS-SENSE-001 and KOS-SENSE-002 in [../../ACCEPTANCE_CRITERIA.md](../../ACCEPTANCE_CRITERIA.md) are not edited. All criteria are software-only and use synthetic data. No physical sensor, hardware-in-loop or safety validation is required or claimed.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-301 | A versioned transform representation defines parent frame, child frame, translation (metres), a single rotation representation (unit quaternion with named components) and the transform direction, unambiguously. | contract review, schema tests |
| AC-302 | The validator accepts valid synthetic transforms in the documented convention and rejects malformed or missing fields, unsupported versions, unknown frame identifiers, non-finite values and non-unit rotations, with documented error codes. | `make test-unit` |
| AC-303 | A frame graph rejects duplicate parent-child relationships, self-links, frames with more than one parent and cycles, with deterministic documented error codes. | `make test-unit` |
| AC-304 | Resolution between connected frames returns the documented deterministic composition; the reverse lookup returns the inverse transform within the declared tolerance. | known-answer tests |
| AC-305 | Disconnected frames and unknown frames are reported explicitly; the implementation never invents an identity or default transform for an unknown relationship. | `make test-unit` |
| AC-306 | Tests cover at least one multi-edge graph, reverse lookup, disconnected components, cycle detection, invalid rotations and numerical boundary cases. | `make test-unit` |
| AC-307 | The contract, schema, fixtures, worked examples and test instructions are documented; `make test-unit` runs from a clean checkout, exits non-zero on failure and passes in CI on the exact closing commit; results are bound to immutable commit SHAs. | `make test-unit`, CI, review |

## Test boundaries

All inputs are synthetic. No ROS 2 or external transform library is required. No coverage threshold is imposed (none is approved, D-080). The transform representation has its own version and change record, separate from contract 0.1.0; a change to contract 0.1.0 follows that contract's own versioning and decision process.

## Definition of done

AC-301 to AC-307 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no physical or safety claim is inferred from synthetic validation.
