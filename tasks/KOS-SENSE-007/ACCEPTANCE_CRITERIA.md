# Acceptance Criteria: KOS-SENSE-007

Standard: kritva-program `v2/planning/ACCEPTANCE_STANDARD.md` (approved by D-080). Task: [KOS-SENSE-007](TASK.md), baselined in v7 (D-090). Status of these criteria: the implementation target for KOS-SENSE-007 since the baseline v7 freeze was merged; they are not yet demonstrated, and the task is accepted only by a separate central approval; the accepted criteria of KOS-SENSE-001 to KOS-SENSE-006 are not edited. All criteria are software-only and use synthetic data.

## Functional criteria

| ID | Criterion (testable) | Verified by |
|---|---|---|
| AC-701 | `pyproject.toml` declares the package name, version, supported Python versions, licence, package contents and the command line entry points; the declared runtime dependencies are empty. | automated metadata assertions, `make test-unit` |
| AC-702 | A wheel and a source distribution build from a clean checkout in an isolated environment, using only build tools declared and pinned in a build configuration kept apart from the empty runtime dependencies; the build log shows no undeclared download. In CI a missing build tool fails the run; a skipped mandatory packaging test is never a pass and the CI evidence shows each mandatory test ran. | build step in CI, review of the log, CI test report |
| AC-703 | The wheel and the source distribution each install into a clean environment, and every public module imports from a temporary directory; the test shows the source checkout is not reachable through the working directory or `PYTHONPATH`. The distributions contain only the intended package and contract files. | install test, content listing test, `make test-unit` |
| AC-704 | After installation each documented command line runs on a synthetic input: sample validation, frame graph resolution, generator, stream checking and the conformance harness against the reference consumer (exit 0); a deliberately non-conforming input exits non-zero as documented. | install smoke test |
| AC-705 | The package version, the Sense, frame graph and stream contract versions and the harness version are separately identifiable in the metadata, through the package's version-information interface and in `RELEASE.md`. Tests cover a package version that differs from a contract version, two different contract versions, a harness version that differs from the package version, and a deliberate mismatch between the declared contract versions and the shipped contract files, which must be detected; shipped contract and schema files are byte-identical to `contract/`. | automated version tests |
| AC-706 | Wheel and sdist are built twice from the same source revision in the same pinned, isolated build environment with a fixed `SOURCE_DATE_EPOCH`; the actual files are byte-identical and have the same SHA-256. Where a file cannot be made byte-identical, `RELEASE.md` names the non-deterministic field, its cause and impact and the normalisation used; the SHA-256 of the shipped file is kept apart from any normalised hash; no unexplained difference is accepted. | double-build test, CI |
| AC-707 | `RELEASE.md` is checked against the actual release artifacts and states the supported functionality, the limitations, the contract compatibility, the one-tag-per-release policy with the tag created by the owner, the source commit and the SHA-256 of each distribution file of the closing build, and that the release tag identifies the repository release without implying equal component versions; the existing contracts, schemas, validators, generator, stream checker and harness are unchanged apart from packaging metadata (pinned by tests); `make test-unit` passes in CI on the exact closing commit. | documentation review, `make test-unit`, CI |

## Test boundaries

All inputs are synthetic. No registry, network service or external runtime library is required. Platform: the CI platform only. No coverage threshold is imposed (none is approved, D-080).

## Definition of done

AC-701 to AC-707 are demonstrated; unit tests pass on the exact closing commit; required PR checks are green; review is recorded against the closing SHA; the changelog and documentation are updated; central approval and immutable evidence are recorded in kritva-program; no claim is made about a published release, other platforms or any real consumer.
