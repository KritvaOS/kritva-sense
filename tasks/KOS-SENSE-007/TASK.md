# KOS-SENSE-007: Python package and reproducible release

| Property | Value |
|---|---|
| Milestone | V2-M8-SENSE-001 |
| Status | NOT_STARTED (proposed for baseline v7, D-090; all of KOS-SENSE-001 to KOS-SENSE-006 are accepted) |
| Weight | 5 (initial planning weight, 5 effort days; proposed for baseline v7, D-090; effort risk: reproducibility across two builds and clean-environment install tests) |
| Depends on | KOS-SENSE-001 to KOS-SENSE-006 (all accepted) |
| Requires physical | No (software only, synthetic data) |
| Acceptance | [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) (AC-701 to AC-707) |
| Deliverables | `pyproject.toml`, `RELEASE.md` (release notes template and release procedure), `tests/packaging/`, `make test-unit` |
| Acceptance evidence | Not yet: immutable closing SHA, `unit-tests` CI run on that SHA, review record and central approval are recorded when the task closes |

## Purpose

The Sense software (validator, frame graph reference, generator, stream checker and conformance harness) exists only as a source checkout. This task makes it a versioned, installable and reproducibly built Python package, so a future consumer can install a known release instead of copying files. It changes no contract: the package carries the approved contracts and implementations unchanged.

## Scope

- Package metadata in `pyproject.toml`: name, package version, supported Python versions, licence, package contents and command line entry points for the existing modules. The runtime has no dependency outside the Python standard library. Build-time tools are declared and pinned separately and are never runtime dependencies.
- A versioning rule, written in `RELEASE.md`, that keeps the package version, the three contract versions (Sense 0.1.0, frame graph 0.1.0, stream 0.1.0) and the harness version separate and identifiable; the package exposes the contract versions it implements. Owner decision recorded for this task: one repository release tag per release, with the contract and harness versions listed in the release notes; the tag is created by the owner and by no tool.
- A build of a wheel and a source distribution with standard Python packaging tools, from a clean checkout in an isolated environment.
- Install and smoke tests from a temporary directory with the source tree unavailable: import every public module, run the documented command lines (sample validation, frame graph resolution, generator, stream checking, conformance harness against the reference consumer) and check that the packaged contract and schema files, if shipped, are byte-identical to `contract/`.
- Reproducibility: wheel and sdist are built twice from the same source revision in the same pinned, isolated build environment with a fixed `SOURCE_DATE_EPOCH`, and the actual files are compared byte for byte and by SHA-256. If a file cannot be made byte-identical, the specific non-deterministic field, its cause and its impact are documented together with the normalisation used to compare the logical contents; the release notes keep the SHA-256 of the shipped file apart from any normalised-content hash. No unexplained difference is accepted. A stdlib-only builder is not required.
- A small documented version-information interface in the package that reports the package version, the Sense, frame graph and stream contract versions and the harness version, checked against the contract files the package ships.
- Release notes and artifact hashes: supported functionality, limitations, compatibility with the contract versions, the source commit and the SHA-256 of each distribution file. The release tag identifies the repository release; it does not imply that the component versions are equal. Completion of the milestone includes the owner's tag action, which is a release action and not part of this task's acceptance evidence.
- `make test-unit` runs the packaging tests (standard library only for the tests). The build tools are pinned in a dedicated build configuration. In a developer environment a missing build tool gives an explicit SKIP with its reason; in the CI acceptance run a missing build tool is a failure, a skip is never counted as a PASS, and the evidence shows that every mandatory packaging test ran.

## Non-goals

No change to any contract, schema, validator, generator, stream checker or harness behaviour; no publication to PyPI or any other registry (a separate owner decision and a separate task if wanted); no ROS 2, hardware or consumer integration; no external runtime dependency; no claim of a stable public API beyond the documented command lines and modules; no automatic upgrade of contract versions; no signed-tag policy (an open owner decision).

## Completion boundary

Acceptance proves that the packaged software installs and runs from a clean environment and that the build is reproducible on the CI platform. It does not publish a release, create a tag or prove behaviour on other platforms. The task is independently testable and independently accepted. Review stays the interim D-047 role, not independent, and acceptance is recorded centrally by the authorized approver.
