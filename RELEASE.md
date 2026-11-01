# Release notes and release procedure: kritva-sense

| Property | Value |
|---|---|
| Task | KOS-SENSE-007 (Python package and reproducible release) |
| Package | `kritva-sense`, built from `pyproject.toml` (standard library only at runtime; no runtime dependency) |
| Status | IN_PROGRESS: the release record is filled when the task closes. This file is checked against the real build by `tests/packaging/` |
| Scope | software only, synthetic data; not hardware or safety validation |

This file is the release note of the repository. It keeps five version numbers apart, states what the package does and does not do, describes how a release is built and checked, and records the hashes of the closing build. It does not publish anything.

## Versions

The package version identifies this software release. It is not a contract version and it does not imply that the component versions are equal. Each component keeps its own version, which changes only when that component changes. The package reports them through `python3 -m kritva_sense.version` (installed command `kritva-sense-version`) and the function `kritva_sense.version.version_info()`; `--check` compares the versions the code declares with the contract files shipped in the package and exits 1 on any mismatch.

| Component | Version | Where it is defined |
|---|---|---|
| Package (kritva-sense) | 0.2.0 | `pyproject.toml` and `PACKAGE_VERSION` in `src/kritva_sense/version.py` (a test keeps the two equal) |
| Sense data contract | 0.1.0 | `contract/SENSE_CONTRACT.md`, `contract/sense-sample.schema.json`, `CONTRACT_VERSION` in `validator.py` |
| Frame graph contract | 0.1.0 | `contract/FRAME_GRAPH_CONTRACT.md`, `contract/frame-transform.schema.json`, `FRAME_GRAPH_VERSION` in `frame_graph.py` |
| Stream contract | 0.1.0 | `contract/STREAM_CONTRACT.md`, `contract/stream.schema.json`, `STREAM_VERSION` in `stream.py` |
| Consumer conformance harness | 0.1.0 | `HARNESS_VERSION` in `conformance.py` |
| Synthetic data generator | 0.1.0 | `GENERATOR_VERSION` in `generator.py` |

Versioning rule. A change to a contract changes that contract's version (a breaking change needs a new major version, a changelog entry and an approved decision, as AGENTS.md says). A change to the harness or the generator changes its own version. The package version changes with every release, whatever else changed. Package version 0.2.0 is the first packaged release; the earlier repository tag `v0.1.0` marks the Sense data contract 0.1.0 and stays what it was.

## Supported functionality

The package ships the existing, accepted software without change: the Sense sample validator (`kritva-sense-validate FILE.json`), the frame graph reference (`kritva-sense-frame-graph FILE.json [FROM TO]`), the synthetic data generator (`kritva-sense-generator samples|graph ...`), the stream checker (`kritva-sense-stream FILE.json`), the consumer conformance harness (`kritva-sense-conformance [--consumer SPEC]... [--seed N] [--output FILE]`), and the version information (`kritva-sense-version [--check]`). Each command is the unchanged `main` of its module; `python3 -m kritva_sense.<module>` works the same way. The package also carries the three contract documents and three schemas under `kritva_sense/contract/`, byte-identical to `contract/` in the repository (a test compares them).

Exit codes are those of each module's documentation: 0 conformant, 1 not conformant, 2 usage or read error.

## Limitations

- Python 3.12 or later is declared; it is tested on Python 3.12 on the CI platform only (ubuntu-latest). Other Python versions and other platforms are not tested and not claimed.
- The documented command lines and modules are the only interface this release describes. The Python API of the modules is not declared stable; the 0.x contracts may still change by their own rules.
- Software only, on synthetic data. A conformant sample, graph or stream is a software property. This release is not hardware or safety validation and says nothing about any sensor or robot.
- No release is published: nothing is uploaded to PyPI or any other registry. Publication would be a separate owner decision and a separate task.
- Signed tags are not required by this release (an open owner decision).
- The wheel is reproducible byte for byte; the source distribution is reproducible after the normalisation described under Build and reproducibility, not byte for byte.

## Contract compatibility

This package implements exactly Sense data contract 0.1.0, frame graph contract 0.1.0 and stream contract 0.1.0, and rejects any other contract version as the contracts specify (`UNSUPPORTED_CONTRACT_VERSION`, `FG_UNSUPPORTED_VERSION`, `STREAM_UNSUPPORTED_VERSION`). The consumer conformance harness 0.1.0 checks a consumer against those three versions. A package release never upgrades a contract version by itself.

## Release tag

This repository uses one repository release tag per release, an annotated tag `vMAJOR.MINOR.PATCH` that names the package version (`v0.2.0` for this release). The tag is created by the owner after the approved merge and after the task is accepted; no tool creates it and no task evidence depends on it. The tag identifies the repository release. It does not imply that the component versions are equal: the contract versions, the harness version and the generator version are listed in the Versions section, and they are not the tag. Creating the tag is a release action of the owner and is not part of the acceptance evidence of KOS-SENSE-007; closing milestone V2-M8-SENSE-001 also needs the separate owner action recorded in `planning/MILESTONE_STATUS.md`.

## Build and reproducibility

The wheel and the source distribution are built from a clean copy of the tracked files in a pinned, isolated build environment:

```bash
python3 -m venv build-env
build-env/bin/python -m pip install -r release/build-requirements.txt
SOURCE_DATE_EPOCH=1700000000 build-env/bin/python -m build --no-isolation --outdir dist .
```

`release/build-requirements.txt` pins every build tool and its dependencies to an exact version (build, packaging, pyproject_hooks, setuptools); the same setuptools pin is the `[build-system]` requirement of `pyproject.toml`. Build tools are never runtime dependencies, which are empty. The build downloads nothing (`--no-isolation`); the tests check the log. README.md and RELEASE.md are not part of either distribution, so a documentation change never changes a hash.

`tests/packaging/` builds twice from the same revision in the same pinned environment, from two copies at different paths and with different file modification times, with `SOURCE_DATE_EPOCH` fixed:

- **Wheel:** byte-identical, same SHA-256. No normalisation is needed.
- **Source distribution:** not byte-identical. The non-deterministic fields are the tar member modification time of the members that the build creates (the directory entries, `PKG-INFO`, `setup.cfg` and the `egg-info` files), the owner and group names that the build user supplies, and the gzip header time. Cause: the pinned setuptools writes the current time and the build user into the archive and does not read `SOURCE_DATE_EPOCH` for the source distribution. Impact: the SHA-256 of the file differs between two builds, the content does not. The comparison therefore uses the normalised-content hash: the SHA-256 of a sorted list of every member's name, type, mode, size and content SHA-256, which leaves out exactly those fields. A test checks that nothing else differs and that the comparison still detects a change in content, name or mode.

The SHA-256 of the shipped file and the normalised-content hash are different values and are recorded separately in the Release record section. Both are valid for the CI platform only: they depend on the pinned tools, on Python 3.12 and on its zlib, which is why a developer machine with another zlib skips the comparison with the reason and CI fails on a difference.

Missing build tools. A developer run without git, the venv module or network access prints an explicit SKIP with the reason. In CI (the `CI` variable is `true`) the same situation fails the run, a skipped mandatory test is never a pass, and each run prints one `PACKAGING-EVIDENCE` line that lists the mandatory tests that ran.

## Release record

Filled from the CI run of the closing commit (the `unit-tests` log prints a `PACKAGING-HASH` line). A value is `PENDING` until the task closes. The hashes are those of the distributions built from the closing commit; they do not depend on this file.

| Field | Value |
|---|---|
| Source commit | PENDING |
| Wheel SHA-256 | PENDING |
| Source distribution SHA-256 | PENDING |
| Source distribution normalised-content hash | PENDING |
