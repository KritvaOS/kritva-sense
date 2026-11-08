# Regression suite (KOS-SENSE-010)

`make test-regression` (from the protected-path pull request of this task: `python3 scripts/regression_gate.py`) runs this suite and decides pass or fail. The mandatory cases are listed in [REGRESSION_INVENTORY.md](REGRESSION_INVENTORY.md). The suite is offline, standard library only, synthetic data only, deterministic, and has no coverage threshold (none is approved).

## What counts as a regression

A regression is a change in something a user or a contract may rely on:

1. **Contract text or schema.** Any change, even to wording, of `contract/SENSE_CONTRACT.md`, `FRAME_GRAPH_CONTRACT.md`, `STREAM_CONTRACT.md` or one of the three schemas.
2. **Accepted decisions of the reference validators.** A different violation code or path for a fixture, a different resolution result, a different stream diagnostic.
3. **Command line behaviour documented in the contracts, `GENERATOR.md`, `CONFORMANCE.md` or `RELEASE.md`.** A different exit code, a different diagnostic line, an option that is removed or renamed, output that is no longer byte for byte the same for the same input and seed, an error that is no longer reported on standard error with nothing on standard output.
4. **A fixed defect coming back.** F-001 (deeply nested JSON), F-002 (a consumer ending the harness with `sys.exit`) and F-003 (an unbounded `--count`), and any defect added to the inventory later.
5. **A gate that can pass without running.** A listed case with no test, zero tests, a skipped or incomplete run.

Not a regression: a change of an undocumented Python internal (function names, helper layout, private constants), of the wording of a message that the documents do not quote, of timing, of the layout of source files that are not pinned, or an added option, command or diagnostic that no accepted document forbids. The suite deliberately does not pin those, so ordinary refactoring stays free.

## What a deliberate change needs

| Change | Needed in the same pull request | Needed centrally |
|---|---|---|
| Wording or schema of an accepted contract (class 1) | New contract version if the meaning changes, and `planning/CHANGELOG.md` entry | A decision in kritva-program (`v2/DECISIONS.md`) approved by the owner |
| Different validator, resolution or stream result (class 2) | The contract text if it is unclear, the fixtures and their hand-written expected values, regenerated golden data | The same decision |
| Different command line behaviour (class 3) | The document that describes it, regenerated golden data, changelog entry | The same decision when a contract or a released command changes |
| A fixed defect cannot stay fixed (class 4) | Not allowed without a new finding and a decision that withdraws the protection | Yes |
| New protected behaviour | A new row in the inventory, a test that names it, golden data if it needs them | No |

The V2 acceptance standard requires that a change to an accepted contract updates the version, the changelog, the golden data and a central decision together; the suite makes the first three visible by failing until each is done, and the decision is checked in review.

## Golden data

`golden/` holds `contract_cases.json` (violations per fixture), `contract_pins.json` (copy of the pin table of `tests/packaging/test_packaging.py`), `command_lines.json` (exit code, standard output by SHA-256, first line of standard error and written files per command line case) and `conformance.json` (case list, reference result hash, verdict of each mutant). They are written only by:

```
python3 scripts/regenerate_regression_golden.py            # shows what would change, writes nothing, exit 1 if different
python3 scripts/regenerate_regression_golden.py --write    # rewrites the files (from the protected-path change: make regression-golden)
```

No test and not the gate ever runs it, and a test checks that no test module imports it. Run it only after the change was decided under the table above; the diff of `golden/` is then part of the pull request and is reviewed like source code. The stream expectations in `tests/stream/fixtures/expected.json` and the `expected_codes` of the Sense and frame graph fixtures are hand-written and are never regenerated.

## Adding a case

1. Add a row to the inventory first (the next `REG-nn`, the source, the protected behaviour, the test).
2. Add a test class with `REGRESSION = "REG-nn"` in a `test_*.py` module of this directory.
3. If the case needs golden data, extend `regression_support.py` and regenerate (above).
4. Run `python3 scripts/regression_gate.py`: it fails until the row and the test agree.

`MUTATION_RECORD.md` shows, for F-001 to F-003, that the tests fail on the pre-fix code.
