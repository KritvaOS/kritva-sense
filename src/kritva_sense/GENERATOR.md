# Sense synthetic data generator

| Property | Value |
|---|---|
| Task | KOS-SENSE-004 (Deterministic synthetic sensor sample generator) |
| Generator version | Generator version: 0.1.0 |
| Status | ACCEPTED: KOS-SENSE-004 central approval (program decision D-086); a test utility, it defines no contract |
| Code | [generator.py](generator.py) (standard library only) |
| Tests | `tests/generator/` (run by `make test-unit`) |
| Contracts used | Sense data contract 0.1.0 ([SENSE_CONTRACT.md](../../contract/SENSE_CONTRACT.md)) and frame graph contract 0.1.0 ([FRAME_GRAPH_CONTRACT.md](../../contract/FRAME_GRAPH_CONTRACT.md)); the generator changes neither |

## 1. Scope

The generator writes synthetic Sense samples and frame graphs from a seed. It is software on synthetic data only: generated values are plausible in form, not physically meaningful, and model no real sensor, noise, calibration or robot. It is not a simulator and makes no accuracy or safety claim. It defines no contract: the validators of contract 0.1.0 and of frame graph contract 0.1.0 decide what is conformant, and every generated document is checked against them (`check_samples`, `check_graph`). The command line refuses to write data that fails that check.

## 2. Determinism

The pseudo-random generator is SplitMix64, implemented in `generator.py` (state: one 64-bit integer; step: add `0x9E3779B97F4A7C15`, then two xor-shift-multiply rounds with `0xBF58476D1CE4E5B9` and `0x94D049BB133111EB`). Python's `random` module is not used. The same seed and configuration give byte-identical output across runs, processes (any `PYTHONHASHSEED`) and Python 3 versions on platforms with IEEE 754 double arithmetic: the generator uses only integer arithmetic, `+`, `-`, `*`, `/`, `sqrt` (exactly rounded by IEEE 754) and `round`, and no library function such as `sin` or `cos`, whose last digit is not guaranteed to agree between platforms. This is tested on the CI platform only; no other platform matrix is claimed. Known answers: seed 0 gives `0xE220A8397B1DCDAF`, `0x6E789E6AA1B965F4`, `0x06C45D188009454F`; seed 1234567 gives `6457827717110365317`, `3203168211198807973`. A float in `[0, 1)` is the top 53 bits of an output divided by 2^53. Sample values are rounded to 6 decimals, quaternion components to 12, and negative zero is written as `0.0`. The seed is an integer from 0 to 2^64 - 1.

## 3. Samples

`generate_samples(kind, sensor_id, count, seed, start_sequence=0, start_ns=0, step_ns=10000000, clock="monotonic", frame="sensor", faults=None)` returns a document:

| Field | Meaning |
|---|---|
| `generator_version` | The version of this generator. |
| `seed` | The seed used. |
| `samples` | The sample objects of contract 0.1.0, in order. Each is exactly a contract sample, with no extra field. |
| `expectations` | One entry `{index, fault, expected_code}` for every requested fault; empty when there are none. |

Sequence `start_sequence + i` and timestamp `start_ns + i * step_ns` (unit `ns`). Values for kind `imu`: `accel_x`, `accel_y` in -2 to 2 m/s^2, `accel_z` near 9.81 m/s^2, `gyro_*` in -1 to 1 rad/s; `range` 0.05 to 10 m; `encoder` -3.14159 to 3.14159 rad (inside the range of an angle, after rounding); `temperature` 273.15 to 323.15 K. Samples are `VALID` unless a fault is requested: nothing is faulty by default and nothing is random about which sample is faulty.

Sample faults, requested as `index -> name` (command line `--fault INDEX:NAME`), and the code the generator states for each:

| Fault | Effect on the sample | Expected code |
|---|---|---|
| `stale` | validity `STALE` with `error_code` `STALE_DATA` | `STALE_DATA` (conformant, not usable) |
| `missing` | validity `MISSING`, empty measurements | `MISSING_DATA` (conformant, not usable) |
| `invalid` | validity `INVALID` | `INVALID_DATA` (conformant, not usable) |
| `regression` | sequence equals the previous sample's (index at least 1); later samples continue as if it had not happened | `SEQUENCE_REGRESSION` |
| `gap` | sequence jumps ahead by 5; later samples continue from it | none: the contract only requires a strictly increasing sequence, so a gap is conformant |
| `boundary` | sequence 2^53, timestamp 2^63 - 1, every value 1e300; allowed on the last sample only | none: extreme but conformant |
| `bad_unit` | first measurement (by name) has unit `furlong` | `INVALID_UNIT` |
| `unknown_frame` | `frame_id` is `map` | `UNKNOWN_FRAME` |
| `missing_measurement` | first measurement (by name) removed | `MISSING_FIELD` |
| `bad_timestamp` | timestamp value -1 | `INVALID_TIMESTAMP` |
| `bad_version` | `contract_version` is `9.9.9` | `UNSUPPORTED_CONTRACT_VERSION` |

The Python API refuses an invalid sensor id, clock, frame or kind with `ValueError`, as the command line does. `check_samples(document)` returns the list of mismatches. It compares complete lists of violation codes (two violations of the same code are two), requires a sequence violation only where a regression was requested, and is empty only when every clean sample and every conformant fault passes the validator and every fault gives exactly its stated code.

## 4. Frame graphs

`generate_graph(seed, extra_frames=0, defect=None)` returns `{generator_version, seed, graph, expectation}`. `graph` is a frame graph document of contract 0.1.0: the chain `world -> base -> sensor` followed by `extra_frames` graph-local frames `link_1`, `link_2`, ... each the child of the one before (0 to 100). Translations are -5 to 5 m; each rotation is a unit quaternion with `w` not negative. With a `defect` the graph has exactly that defect, and `expectation` is `{defect, codes}`:

| Defect | Construction | Expected code |
|---|---|---|
| `cycle` | adds the record `sensor -> world` | `FG_CYCLE` |
| `duplicate_edge` | repeats the first record | `FG_DUPLICATE_EDGE` |
| `multiple_parents` | adds the record `world -> sensor` | `FG_MULTIPLE_PARENTS` |
| `not_unit_quaternion` | scales the first rotation by 1.5 | `FG_NOT_UNIT_QUATERNION` |

`check_graph(document)` requires exactly the expected list of codes (duplicates count), and a conformant graph must also resolve from its first to its last frame.

## 5. Command line

```
python3 -m kritva_sense.generator samples --kind K --sensor-id ID --count N --seed S [--start-sequence N] [--start-ns N] [--step-ns N] [--clock monotonic|utc] [--frame world|base|sensor] [--fault INDEX:NAME ...] [--out FILE]
python3 -m kritva_sense.generator graph --seed S [--extra-frames N] [--defect NAME] [--out FILE]
```

The output is JSON with sorted keys, two-space indent and a trailing newline, on standard output or in `--out`. Exit 0 on success; exit 2 for a usage error (unknown kind or option, negative count, a count above 1000000, missing argument), for a fault or defect that cannot be applied (index outside the sequence, a regression at index 0, a boundary fault before the last sample, two faults on one index), for an invalid sensor id, clock or frame, for data that fails the reference check and for an unwritable target, each with a message on standard error and nothing on standard output.

## 6. Limitations

Resource bound (KOS-SENSE-008, finding F-003). `--count` (and `generate_samples`) accepts at most 1000000 samples (`MAX_COUNT`); a larger value is a usage error at once, so a mistyped count cannot exhaust memory or run for hours. The cap is a guard against a typing error, not a security boundary: an operator who needs more splits the sequence with `--start-sequence` and `--start-ns`. `--out` writes the path it is given and truncates an existing file, also through a symbolic link (the operator is trusted; see THREAT_MODEL.md).

Synthetic data only. No physical, noise or timing model, no real sensor driver, no transport, streaming or real-time behaviour, no ROS or external library, no freshness or health policy and no integration with Mind, Motion or Skill. Review is the interim D-047 role, not independent.
