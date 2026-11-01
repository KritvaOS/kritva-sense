# Release notes and release procedure: kritva-sense

| Property | Value |
|---|---|
| Task | KOS-SENSE-007 (Python package and reproducible release) |
| Package | `kritva-sense`, built from `pyproject.toml` (standard library only at runtime; no runtime dependency) |
| Status | ACCEPTED (KOS-SENSE-007, central approval D-091; KOS-SENSE-008, central approval D-092): the release record is refreshed from the CI run 41298259048 of the closing commit of KOS-SENSE-008. No release is published; milestone V2-M8-SENSE-001 is closed by `COMPLETION_RECORD.md` (merged by the owner in pull request #55), and the tag `v0.2.0` is created by the owner after the final pre-tag corrections are merged. This file is checked against the real build by `tests/packaging/` |
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
- The wheel and the shipped source distribution are reproducible byte for byte on the CI platform; the shipped source distribution is the setuptools archive rewritten by `release/normalise_sdist.py`, as described under Build and reproducibility.

## Contract compatibility

This package implements exactly Sense data contract 0.1.0, frame graph contract 0.1.0 and stream contract 0.1.0, and rejects any other contract version as the contracts specify (`UNSUPPORTED_CONTRACT_VERSION`, `FG_UNSUPPORTED_VERSION`, `STREAM_UNSUPPORTED_VERSION`). The consumer conformance harness 0.1.0 checks a consumer against those three versions. A package release never upgrades a contract version by itself.

## Release tag

This repository uses one repository release tag per release, an annotated tag `vMAJOR.MINOR.PATCH` that names the package version (`v0.2.0` for this release). The tag is created by the owner after the approved merge and after the task is accepted; no tool creates it and no task evidence depends on it. The tag identifies the repository release. It does not imply that the component versions are equal: the contract versions, the harness version and the generator version are listed in the Versions section, and they are not the tag. Creating the tag is a release action of the owner and is not part of the acceptance evidence of KOS-SENSE-007; the tag message names `COMPLETION_RECORD.md` and the exact commit, and the tag is evidence, not closure authority.

## Build and reproducibility

The wheel and the source distribution are built from a clean copy of the tracked files in a pinned, isolated build environment, and the source distribution is then normalised by a script of this repository:

```bash
python3 -m venv build-env
build-env/bin/python -m pip install -r release/build-requirements.txt
SOURCE_DATE_EPOCH=1700000000 build-env/bin/python -m build --no-isolation --outdir dist .
SOURCE_DATE_EPOCH=1700000000 build-env/bin/python release/normalise_sdist.py dist/kritva_sense-0.2.0.tar.gz
```

`release/build-requirements.txt` pins every build tool and its dependencies to an exact version and the SHA-256 of its wheel (build, packaging, pyproject_hooks, setuptools); pip refuses a file with another hash. The same setuptools pin is the `[build-system]` requirement of `pyproject.toml`. Build tools are never runtime dependencies, which are empty. The build downloads nothing (`--no-isolation`); the tests check the log. README.md and RELEASE.md are not part of either distribution, so a documentation change never changes a hash.

Network use of the tests. The only network access of `tests/packaging/` is the one fetch of the hash-pinned build tools into a local wheelhouse. If the environment variable `KRITVA_WHEELHOUSE` names a directory that already holds those wheels (for example prepared once with `pip download --only-binary :all: --no-deps -r release/build-requirements.txt -d DIR`), the whole suite runs without any network access; a wheel whose hash differs is refused.

`tests/packaging/` builds twice from the same revision in the same pinned environment, from two copies at different paths and with different file modification times, with `SOURCE_DATE_EPOCH` fixed:

- **Wheel:** byte-identical, same SHA-256. No normalisation is needed.
- **Source distribution as built by setuptools:** not byte-identical. The fields that differ are the tar member modification time of every member (also as an extended header), the owner and group (numeric ids and names) that the build user supplies, and the gzip header time. Cause: the pinned setuptools writes the build time and the build user into the archive and does not read `SOURCE_DATE_EPOCH` for the source distribution. Impact: the SHA-256 of the file differs between two builds, the content does not. A test checks that nothing else differs: names, types, modes, sizes, link targets, extended headers other than times, and every content byte are equal.
- **Source distribution as shipped:** `release/normalise_sdist.py` (standard library only) rewrites the archive deterministically: members sorted by name, modification time `SOURCE_DATE_EPOCH`, owner and group 0 and `root`, no time in the extended headers, gzip header time 0. Two builds are then byte-identical with equal SHA-256, and running the script twice changes nothing. This is the file recorded below.

The normalised-content hash is the SHA-256 of a sorted list of every member's name, type, mode, size, link target, extended headers other than times, and content SHA-256. It leaves out exactly the time, owner, group and gzip-header fields listed above, so it identifies the content independently of the compression library. It is kept apart from the SHA-256 of the shipped file, which is the identity of the file itself. A test shows that the content comparison ignores those fields and detects a change in content, name, mode, link target or extended header.

The SHA-256 of a wheel or of a source distribution depends on the pinned tools, on Python 3.12 and on its zlib (CI platform only): a developer machine with another zlib skips that comparison with the reason, and CI fails on a difference. The normalised-content hash does not depend on zlib and is compared everywhere.

Missing build tools. A developer run without git, the venv module or the build tools (no network and no prepared wheelhouse) prints an explicit SKIP with the reason. In CI (the `CI` variable is `true`) the same situation fails the run, a skipped mandatory test is never a pass, and each run prints one `PACKAGING-EVIDENCE` line that lists the mandatory tests that ran.

## Release record

Filled from the `unit-tests` CI run 41298259048 on the artifact-input commit (the closing commit of KOS-SENSE-008, merge of pull request #52; the record of KOS-SENSE-007 is kept in the refresh note below; the log prints a `PACKAGING-HASH` line and a `PACKAGING-EVIDENCE` line showing that all 27 mandatory packaging tests ran). A value is `PENDING` until the task is submitted for review; the test refuses a pending value once the task is IN_REVIEW or ACCEPTED. The source commit is the artifact-input commit: the commit whose tree the recorded artifacts were built from. The commit that records the values is a later commit that changes only files outside both distributions; it builds identical artifacts, and `tests/packaging/` rebuilds and compares all three hashes on every run, so a record that no longer matches the tree fails.

| Field | Value |
|---|---|
| Source commit | a8dfb5a7827e9888a5bfae0bbcea1598727bd400 |
| Wheel SHA-256 | a83093fae5aefe6f26ec1d4d42d62209653b6b4f7c94538af8d636cf3f41da29 |
| Source distribution SHA-256 | bd272c2c58d9e14451e079bbe8c2099488c8e9b9a8ada254779ecdd6d8fe73aa |
| Source distribution normalised-content hash | fbb471f66b58b403ff8b26f7c7a2724738bb145880e82326ee4cb50ff9d05556 |

Refresh by KOS-SENSE-008. KOS-SENSE-008 fixed three findings in packaged modules (`__main__.py`, `frame_graph.py`, `stream.py`, `conformance.py` and `generator.py`: F-001 to F-003 in `tasks/KOS-SENSE-008/SECURITY_REVIEW.md`), so the artifacts above differ from those that KOS-SENSE-007 accepted. The values above come from the `unit-tests` CI run 41298259048 on commit a8dfb5a (the closing commit of KOS-SENSE-008, merge of pull request #52; its log prints the `PACKAGING-HASH` line and a `PACKAGING-EVIDENCE` line showing that all 27 mandatory packaging tests ran). The packaged files last changed in pull request #49, so the artifacts are the same as those of the first run on the merged fixes (run 41296452969 on c1d6b10 printed the same three hashes). The package version stays 0.2.0 and no tag exists or was published. The values accepted by KOS-SENSE-007 (artifact-input commit 5f1aa7a34c5aec9e0c12fc66add6d3bc6efaa7bc, `unit-tests` run 41292919590) were: wheel 47ed3803b02aafb285cfee9aa620142676e30f5f0dc6fa67e383b283a24f2415, source distribution f6f8284b7eef220a65d40359a0ab013ced2ee64d0ae068cee8f8fe960ca6d192, normalised-content hash bd5e68f34eb028a2b786adf6a83286bfd8243335325b9865dee498c5c438ee32; they stay in the decision record D-091. From now on `tests/packaging/` fails a record that does not match the build.
