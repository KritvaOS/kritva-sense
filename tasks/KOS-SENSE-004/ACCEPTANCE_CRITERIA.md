# Acceptance Criteria: KOS-SENSE-004

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-004](TASK.md), baselined in v5 (D-083). Status of these criteria: the criteria of KOS-SENSE-004, baselined in v5 (D-083) and accepted by the central approval recorded in kritva-program (D-086) on the closing commit 82b3174; the accepted criteria of KOS-SENSE-001 and KOS-SENSE-002 in [../../ACCEPTANCE_CRITERIA.md](../../ACCEPTANCE_CRITERIA.md) and the criteria of [KOS-SENSE-003](../KOS-SENSE-003/ACCEPTANCE_CRITERIA.md) are not edited. All criteria are software-only and use synthetic data. No physical sensor, hardware-in-loop or safety validation is required or claimed.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-401 | The generator is deterministic: the same seed and configuration give byte-identical output across runs; the pseudo-random algorithm is documented and implemented in this repository with fixed known-answer values for given seeds; different seeds give different output. | `make test-unit` |
| AC-402 | Generated valid samples of every sensor kind (`imu`, `range`, `encoder`, `temperature`) pass the reference validator of contract 0.1.0 for any seed in the tested set. | `make test-unit` |
| AC-403 | Timestamps, sequences, frame and sensor id follow the configuration; sequences are strictly increasing per sensor id unless a regression is requested explicitly. | `make test-unit` |
| AC-404 | Stale, missing and invalid validity states, sequence regression, sequence gaps and boundary values are generated only when requested, and each generated defect is rejected or reported with the contract error code the generator documents for it. | `make test-unit` |
| AC-405 | Generated conformant frame graphs pass the frame graph validator and resolve with the documented composition; generated defective graphs (cycle, duplicate edge, multiple parents, non-unit rotation) are rejected with the documented code. | `make test-unit` |
| AC-406 | The Python API and the command line write the documented JSON format; the command line exits 0 on success, 2 on a usage error, and refuses unknown kinds, negative counts and unwritable targets with a message. | `make test-unit` |
| AC-407 | The generator, its output format, the seeds used by the tests and the test instructions are documented; `make test-unit` runs from a clean checkout, exits non-zero on failure and passes in CI on the exact closing commit; results are bound to immutable commit SHAs; Sense contract 0.1.0, the frame graph contract 0.1.0 and their schemas are unchanged (pinned by tests). | `make test-unit`, CI, review |

## Test boundaries

All inputs are synthetic. No ROS 2 or external library is required. No coverage threshold is imposed (none is approved, D-080). The generator makes no claim that generated values resemble real sensor behaviour.

## Definition of done

AC-401 to AC-407 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no physical or safety claim is inferred from synthetic validation.
