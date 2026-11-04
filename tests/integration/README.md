# Integration gate (KOS-SENSE-009)

Status: IN_PROGRESS (baselined in v8, D-099). Criteria: [AC-901 to AC-907](../../tasks/KOS-SENSE-009/ACCEPTANCE_CRITERIA.md). Task: [KOS-SENSE-009](../../tasks/KOS-SENSE-009/TASK.md).

The Sense components (validator, frame graph reference, generator, stream checker and conformance harness) are unit tested one by one under `tests/contract`, `tests/frame_graph`, `tests/generator`, `tests/stream` and `tests/conformance`. This directory tests the boundaries between them with deterministic synthetic data, and `scripts/integration_gate.py` decides pass or fail.

**Reference fixture, not a real consumer.** `fixture.py` holds a synthetic producer and consumer built from the accepted contracts. It is not a Mind, Motion or Skill consumer, and a pass shows nothing about any real consumer, sensor, robot or safety property. No network, no hardware, no library outside the standard library.

## Run

```
python3 scripts/integration_gate.py          # the gate (what `make test-integration` runs once the Makefile target is in place)
python3 -m unittest discover -s tests/integration     # the same tests without the gate decision
```

## Files

| File | Content |
|---|---|
| [SCENARIOS.md](SCENARIOS.md) | The mandatory scenarios INT-01 to INT-10: boundary, synthetic input, expected result and the clause behind it. Written before the tests. |
| `fixture.py` | Synthetic producer (generator output, stream and graph documents) and the fixture consumers (conforming and deliberately faulty). |
| `helpers.py` | Temporary directories, interpreter calls and console-script launchers. |
| `test_data_boundaries.py` | INT-01 to INT-05: generator across the validator, frame graph reference and stream checker. |
| `test_consumer_harness.py` | INT-06 and INT-07: the fixture consumers through the conformance harness. |
| `test_command_lines.py` | INT-08 to INT-10: the command lines chained as documented, failure propagation and determinism. |

## What the gate decides

The gate passes only when SCENARIOS.md lists at least one mandatory scenario; every test belongs to a listed scenario (`SCENARIO = "INT-nn"` on its class); at least one test ran and the run was complete; no test failed, errored, was skipped, was expected to fail or unexpectedly passed; and every listed scenario ran at least one test, all passing. It prints one line, for example:

```
INTEGRATION-EVIDENCE: scenarios=10 of 10 tests=33 ran=INT-01,INT-02,...,INT-10
```

Exit 0 pass; exit 1 any failure, missing or skipped scenario, zero tests or incomplete run; exit 2 usage error. The gate never exits 3 and never reports a pass for work that did not run. `tests/integration_gate/` proves this: removing a scenario, skipping a test, a failing test, a test outside every scenario, zero tests, a test that ends the process and an import error each make the gate fail.

## Limits

- The five tools read a file path and none reads standard input, so "chained" means the documented flow: one tool writes JSON to standard output, the next reads it from a file.
- The command-line scenarios use console-script launchers of the exact form `pip` generates, run from a temporary directory. Building and installing the wheel is tested by `tests/packaging/` (KOS-SENSE-007) and is not repeated here, because it needs build tools and a package index.
- The suite is deterministic (fixed seed, fixed clock values) and runs in the network-disabled environment of KOS-SENSE-008 (`tests/security/test_offline.py` includes it).
- No coverage threshold is imposed (none is approved, D-080). The regression gate and the compatibility suite belong to KOS-SENSE-010.
