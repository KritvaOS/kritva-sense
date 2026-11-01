# Acceptance Criteria: KOS-SENSE-006

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-006](TASK.md), baselined in v6 (D-087); it depends on KOS-SENSE-005, accepted by the central approval D-088. Status of these criteria: the criteria of KOS-SENSE-006, baselined in v6 (D-087) and accepted by the central approval recorded in kritva-program (D-089) on the closing commit 67590bc; the accepted criteria of KOS-SENSE-001 to KOS-SENSE-005 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-601 | The consumer interface is documented unambiguously as three operations (sample decision, stream decision, frame resolution) with explicit inputs, including `now_ns`, `now_clock` and `max_age_ns`, and decision values that equal the codes of the contracts. | contract review, tests |
| AC-602 | The reference consumer implements the sample, stream and frame graph rules of the accepted contracts and passes every case of the case set. | `make test-unit` |
| AC-603 | Every case states its expected outcome and the contract clause it comes from; expected outcomes are written in the case set and are never produced by calling the reference consumer; the set covers the sample, freshness, validity-precedence, sequence, stream and frame cases listed in the task, including freshness boundaries and frame identity (no assumed connection, identity only for a frame present in the graph). | `make test-unit` |
| AC-604 | At least one mutant consumer exists per rule class (freshness, validity precedence, sequence, stream gap handling, frame identity assumption); each mutant fails at least one named case and no mutant passes the whole set. | `make test-unit` |
| AC-605 | The result is JSON with sorted keys and stable case and consumer ordering, byte-identical across runs for the same consumer and seed. | `make test-unit` |
| AC-606 | A consumer that raises or returns an undefined decision fails that case; the remaining cases and consumers still run and the verdict is not conformant. | `make test-unit` |
| AC-607 | A command line runs the harness against the reference consumer or a named Python callable and exits 0 (conformant), 1 (not conformant), 2 (usage or load error). The interface, case set, result format and test instructions are documented; `make test-unit` runs from a clean checkout, uses only the standard library, passes in CI on the exact closing commit, and every existing contract, schema, validator, generator and stream contract document is unchanged (pinned by tests). | `make test-unit`, CI, review |

## Test boundaries

All inputs are synthetic. No real consumer, ROS 2 or external library is required. No coverage threshold is imposed (none is approved, D-080).

## Definition of done

AC-601 to AC-607 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no claim about any real consumer is made.
