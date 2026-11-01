# Threat model: kritva-sense (KOS-SENSE-008)

| Property | Value |
|---|---|
| Task | [KOS-SENSE-008](TASK.md), criteria AC-801 to AC-807 ([criteria](ACCEPTANCE_CRITERIA.md)) |
| Subject | the repository as it is at the review: package `kritva-sense` 0.2.0 (standard library only), the CI workflows and the pull request gate, the build and release path |
| Method | written from the code and workflows; checked by the tests in `tests/security/` where a statement is testable |
| Status | review record of the internal D-047 role (not independent). It is not a certification, a penetration test or a safety assessment |

The threat model says what is protected, who is trusted, where outside input enters and what is assumed. The findings that follow from it are in [SECURITY_REVIEW.md](SECURITY_REVIEW.md).

## 1. What the repository is

A software-only reference implementation of three data contracts (Sense sample, frame graph, stream), a synthetic data generator, a consumer conformance harness, and the planning, CI and release files around them. It runs as short-lived command lines on a developer machine or in CI. It has no server, no network client, no database, no credentials, no runtime dependency and no hardware interface. All data in the repository is synthetic.

## 2. Assets

| ID | Asset | Why it matters |
|---|---|---|
| AS-1 | The accepted contracts, schemas and reference code (`contract/`, `src/kritva_sense/`) | Other repositories and a future consumer rely on them; a silent change would change what "conformant" means. They are pinned by SHA-256 in the tests. |
| AS-2 | The integrity of `main` and of the review and acceptance record (`planning/`, `tasks/`, protected paths, kritva-program approvals) | Acceptance is the evidence that the software is what was reviewed. |
| AS-3 | The release artifacts (wheel and source distribution of KOS-SENSE-007) and the release record in `RELEASE.md` | A consumer installing the package must get the reviewed content; the record lets anyone rebuild and compare. |
| AS-4 | The operator's files and environment when a command runs | The commands read and write files the operator names; the harness can import code the operator names. |
| AS-5 | The CI token and the repository secrets | The workflows use only the automatic `github.token`; no other secret is configured in the workflows. |
| AS-6 | Availability of the commands and of CI (memory, time) | A command that hangs or exhausts memory blocks the operator or CI. |
| AS-7 | The pinned build tools and their hash list (`release/build-requirements.txt`), and any locally prepared wheelhouse of them (`KRITVA_WHEELHOUSE`) | The release build and the offline test runs install exactly these files; pip refuses a file whose SHA-256 differs, so the hash list, not the wheelhouse directory, is the trusted part. |

Not assets here: any customer or personal data (none is held), any hardware, any safety-relevant system.

## 3. Actors and trust boundaries

| ID | Boundary | Trusted side | Less trusted side |
|---|---|---|---|
| TB-1 | The operator running a command line | the operator, who chooses every path and every argument | the content of the files named (JSON documents) |
| TB-2 | The harness process and a consumer module named as `MODULE:ATTR` | the harness code | the consumer module: it is imported into the harness process and is **not** isolated. The boundary is a statement about trust in the operator's choice, not a technical barrier |
| TB-3 | A pull request and the CI that runs on it | the base branch, the owner who merges, protected paths and CODEOWNERS | the pull request branch: its files, scripts, tests, commit messages and workflow changes (a pull request can change what runs, but a `pull_request` run has a read-only token for forks and no repository secret). Everything a run produces in the job workspace (temporary directories, test output, `gate-report.md`, built distributions) is data derived from the pull request and is untrusted as well; the gate report becomes a pull request comment. Only `pr-acceptance-gate` holds a token that can write (`pull-requests: write`, for that comment); the other four workflows hold `contents: read` only |
| TB-4 | The build and release path | the pinned tool list with hashes, the build script, the owner who creates a tag | the package index at the one moment the pinned build tools are fetched (hash-checked), the downloaded gitleaks release |
| TB-5 | The package consumer (someone who installs the wheel) | the content of the wheel | the contents of the JSON documents they validate |

Actors considered: a careless or mistaken operator (most likely), a contributor who opens a pull request with hostile content, a compromised dependency or action in the supply chain, a person who supplies a crafted JSON file. Not considered: an attacker with write access to `main`, with the owner's account, or with the machine of the operator; a malicious consumer author whom the operator chooses to run (see A-2).

## 4. Entry points

Every entry point names the code or workflow it refers to. The review of each is in SECURITY_REVIEW.md, section Input handling, Consumer loading, Workflows or Build.

| ID | Entry point | Code or workflow | Input and boundary | Main concerns |
|---|---|---|---|---|
| EP-1 | `kritva-sense-validate FILE` / `python3 -m kritva_sense FILE` | `src/kritva_sense/__main__.py` (calls `validator.validate_sample`) | JSON file, TB-1 | malformed, huge or deeply nested JSON; exit codes |
| EP-2 | `kritva-sense-frame-graph FILE [FROM TO]` | `src/kritva_sense/frame_graph.py` `main` | JSON file, TB-1 | as EP-1, graph size |
| EP-3 | `kritva-sense-stream FILE` | `src/kritva_sense/stream.py` `main` | JSON file, TB-1 | as EP-1, stream length (time and memory) |
| EP-4 | `kritva-sense-generator samples or graph ...` | `src/kritva_sense/generator.py` `main` | command-line arguments, output path `--out`, TB-1 | unbounded `--count`; output path overwrite and symbolic links |
| EP-5 | `kritva-sense-conformance [--consumer SPEC]... [--output FILE]` | `src/kritva_sense/conformance.py` `main`, `load_consumer`, `run_case` | `MODULE:ATTR` consumer specification, output path, TB-1 and TB-2 | arbitrary code import, a consumer that raises, exits or hangs; path overwrite |
| EP-6 | `kritva-sense-version [--check]` | `src/kritva_sense/version.py` `main` | reads the packaged contract files, no outside input | none beyond local file reads |
| EP-7 | Python API of the modules (`import kritva_sense...`) | `src/kritva_sense/*.py` | Python objects supplied by the caller | not declared stable (RELEASE.md); callers pass trusted objects |
| EP-8 | Console script wrappers | `src/kritva_sense/_entry.py`, `[project.scripts]` in `pyproject.toml` | as the commands above | none beyond the commands |
| EP-9 | Workflow `commit-message-check` | `.github/workflows/commit-message-check.yml`, `scripts/security/check_commit_messages.py` | pull request commit messages, base branch name (passed to the script through `env:`), TB-3 | untrusted text in the shell, token permissions |
| EP-10 | Workflow `pr-acceptance-gate` | `.github/workflows/pr-acceptance-gate.yml`, `scripts/pipeline/pr_gate.py`, `.github/kritva-gate.json` | the pull request diff and commits, TB-3; the only workflow with `pull-requests: write` | the gate code comes from the pull request itself (accepted, F-007); the comment step and its token; values reach the shell through `env:` |
| EP-11 | Workflow `secret-scan` | `.github/workflows/secret-scan.yml` | full git history, downloaded gitleaks release, TB-3 and TB-4 | integrity of the downloaded scanner |
| EP-12 | Workflow `unit-tests` | `.github/workflows/unit-tests.yml`, `Makefile` target `test-unit` | pull request code executed in CI, TB-3 | runs the pull request's own tests with a read-only token and no secret; it is a required check in `.github/kritva-gate.json` (F-004) |
| EP-13 | Workflow `readme-check` | `.github/workflows/readme-check.yml`, `scripts/check_readme.py` | README text | none beyond reading files |
| EP-14 | Build and release path | `pyproject.toml`, `MANIFEST.in`, `release/build-requirements.txt`, `release/normalise_sdist.py`, `tests/packaging/`, `RELEASE.md` | one fetch of the pinned build tools, TB-4, or a prepared wheelhouse (AS-7) | hash pinning, reproducibility, content of the artifacts |
| EP-15 | Repository governance files | `.github/kritva-gate.json` (protected paths, required checks), `.github/CODEOWNERS`, `SECURITY.md` | contributors, TB-3 | which checks block a merge; accuracy of the security policy. `kritva-gate.json` is a repository-side declaration read by the gate: it does not prove that the GitHub ruleset enforces the same checks (A-8) |
| EP-16 | Local helper scripts | `scripts/docs_check.py`, `scripts/check_readme.py` | repository files | read-only checks |

## 5. Assumptions

| ID | Assumption | If it fails |
|---|---|---|
| A-1 | The operator is trusted: they choose the input paths, the output paths and the consumer specification. The commands do not restrict, resolve or sandbox paths, and an output path is truncated if it exists. | A command line assembled from untrusted text can overwrite a file the user can write, or import code. Do not build command lines from untrusted text. |
| A-2 | A consumer named as `MODULE:ATTR` is trusted code. Loading imports it into the harness process with the privileges of the user; the module is searched in the working directory and in `PYTHONPATH`. **The harness is not a sandbox, and a timeout (an operator's `timeout` command or a subprocess timeout) only ends the process; it does not make the consumer safe.** | Untrusted consumer code can do anything the user can do. Run the harness only on code you trust, in a directory you control, preferably in a disposable environment you provide. |
| A-3 | JSON documents are untrusted data, not code. The commands never execute, evaluate or import anything from a document. | A change that evaluates document content would need a new review. |
| A-4 | GitHub's `pull_request` event semantics hold: no secret and a read-only token for a pull request from a fork; the workflow definition in the pull request is used. | CI could run hostile code with a write token. |
| A-5 | The owner reviews and merges changes to protected paths and workflows (CODEOWNERS `*` and `/.github/`), and a merge needs the owner's route. | A malicious change to a workflow or gate script could be merged. |
| A-6 | The package index and the GitHub release host serve the pinned content; hash checks detect a substitution of the build tools; the gitleaks checksum is fetched from the same release (an integrity check against corruption, not against a compromised release). | A compromised scanner could hide a secret; a substituted build tool is refused by pip. |
| A-7 | The software is a synthetic-data reference implementation. No safety, hardware or operational claim is made about any robot, sensor or consumer. | Out of scope. |
| A-8 | The GitHub-hosted settings (rulesets, branch protection, required status checks, Actions permissions, private vulnerability reporting) are outside the repository files and are not verified by this review; `.github/kritva-gate.json` and `CODEOWNERS` state intent, they do not prove enforcement. | A check listed in the files may not block a merge. The owner verifies the ruleset. |

## 6. Threats considered

| ID | Threat | Entry points | Mitigation or result |
|---|---|---|---|
| T-1 | A crafted JSON file crashes a command with a traceback and the wrong exit code | EP-1 to EP-3 | Deeply nested JSON was found to do this (F-001) and is fixed; other malformed input exits 0, 1 or 2 without a traceback (tests) |
| T-2 | Resource exhaustion by a huge value (`--count`, long stream, wide object) | EP-3, EP-4 | `--count` capped at 1000000 (F-003); the stream and validator work is linear (tests) |
| T-3 | Overwriting or reading a file the operator did not mean | EP-4, EP-5 | By design (A-1); documented and recorded in a test (no finding against the code) |
| T-4 | Arbitrary code execution through the consumer specification | EP-5 | By design (A-2); documented as not a sandbox (F-010); load errors are exit 2 |
| T-5 | A consumer ends the run with a false pass (`sys.exit(0)`) or hides a failure | EP-5 | Found (F-002) and fixed; `SystemExit` is caught at load, at invocation and in the decision normaliser |
| T-6 | A consumer hangs the harness | EP-5 | Not mitigated; documented limitation (F-011). Tests use a subprocess timeout only to end their own child |
| T-7 | Untrusted pull request text reaches a shell or a privileged step | EP-9, EP-10 | No `${{ }}` expression appears inside a `run:` script: the base ref, head SHA, repository, pull request number and gate result reach scripts through `env:` (F-006, fixed); no title, body or head ref is used; no `pull_request_target` (policy test) |
| T-8 | A pull request weakens the checks that guard it | EP-10, EP-12, EP-15 | The gate runs the pull request's own gate script (F-007, accepted by the owner: protected paths and CODEOWNERS route such changes to the owner). `unit-tests` is now a required check in `kritva-gate.json` (F-004); that the GitHub ruleset requires it too is an owner action that this review does not verify (A-8) |
| T-9 | A supply-chain compromise of a CI action or the scanner | EP-11 to EP-13 | First-party actions only, each pinned to a full commit SHA with the tag in a comment (F-005, fixed); gitleaks checksum from the same release origin (F-008, accepted by the owner) |
| T-10 | A tampered or non-reproducible release artifact | EP-14 | Hash-pinned build tools, double reproducible build, exact artifact listing, release record (KOS-SENSE-007); re-checked here |
| T-11 | An outdated security policy misleads a reporter | EP-15 | `SECURITY.md` described the repository as holding no implementation (F-009) |

## 7. Out of scope

Third-party penetration testing and certification; GitHub organisation, account and branch-protection settings beyond what the repository files state; network transport, ROS 2 or any real consumer; hardware, firmware and robot safety; any claim that conformance on synthetic data shows operational safety; any sandbox for consumer code. The review states no claim that the repository is free of vulnerabilities.
