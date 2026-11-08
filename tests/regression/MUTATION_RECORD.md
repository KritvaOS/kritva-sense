# Mutation record for F-001, F-002 and F-003 (KOS-SENSE-010, AC-1002)

A one-time check, not part of the suite: it shows that each regression test fails on the behaviour before the fix and passes on the current code.

**Method.** A scratch copy of the tree at the base of this pull request, with the five modules that KOS-SENSE-008 changed (`__main__.py`, `conformance.py`, `frame_graph.py`, `generator.py`, `stream.py`) replaced by their versions at commit `6e74e6f` (the parent of the KOS-SENSE-008 merge `5a4bf6d`, before the fixes). The tests were run from that copy with a memory limit (`ulimit -v 6000000`) and a time limit, because the unfixed generator has no count cap.

| Finding | Regression test | Result on the pre-fix modules | Result on the current modules |
|---|---|---|---|
| F-001 deeply nested JSON | `test_prior_defects.Reg14DeepNesting` | FAIL: 6 of 6 sub-cases (three commands, array and object): exit 1 with a traceback instead of exit 2 | PASS |
| F-002 `sys.exit` in a consumer | `test_prior_defects.Reg15ConsumerExit` | FAIL: 3 of 3 tests (import-time exit, exit in a factory, exit when invoked) | PASS |
| F-003 unbounded `--count` | `test_prior_defects.Reg16GeneratorCountCap` | ERROR: 2 of 3 tests (`MAX_COUNT` does not exist, so the cap cannot be asserted; the small-count test passes as it should) | PASS |
| Pins (side effect) | `test_contracts.Reg01ContractPins` | FAIL: 5 pinned modules differ from the pinned hashes, as the pin table is meant to show | PASS |

The check was repeated by running the same classes again on the unmodified tree of this pull request: 7 tests, all passing. The mutation was applied to a scratch copy only; no repository file was changed to produce it.
