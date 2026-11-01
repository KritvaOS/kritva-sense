# Kritva Sense Frame Graph Contract

| Property | Value |
|---|---|
| Document ID | KOS-SENSE-FRAME-GRAPH-001 |
| Repository | `KritvaOS/kritva-sense` |
| Task | KOS-SENSE-003 (Deterministic frame graph and transform validation for simulated samples) |
| Version | Frame graph contract version: 0.1.0 |
| Status | PROPOSED: delivered for review with KOS-SENSE-003; not accepted, tagged or credited |
| Owner | Dinesh (interim architecture and safety reviewer, program decision D-047) |
| Related contract | [SENSE_CONTRACT.md](SENSE_CONTRACT.md) 0.1.0 (accepted, tag `v0.1.0`); it is not changed by this document |
| Machine-readable form | [frame-transform.schema.json](frame-transform.schema.json) |
| Reference implementation | `src/kritva_sense/frame_graph.py` |
| Criteria | [tasks/KOS-SENSE-003/ACCEPTANCE_CRITERIA.md](../tasks/KOS-SENSE-003/ACCEPTANCE_CRITERIA.md) |

## 1. Purpose and scope

Sense contract 0.1.0 gives every sample a `frame_id` (`world`, `base` or `sensor`) and says that no transform between frames is defined and that a consumer must not infer one. This contract adds the missing piece as a separate, versioned interface: a static transform between two named frames, a graph of such transforms, and deterministic rules to validate the graph and to resolve the transform between two frames of it.

It is software behaviour on synthetic data only. It says nothing about whether a frame, a mounting transform or a calibration is physically correct, and it does not define transport, time-varying transforms, estimation, calibration or any safety property.

## 2. Relation to the Sense data contract

The frame graph contract has its own version and change record. It does not change the sample contract: samples are validated exactly as before, and a sample's `frame_id` is still one of the three frames of SENSE_CONTRACT section 5. A frame graph may also contain graph-local frames (section 4). They are not part of the frame vocabulary of the sample contract: a sample whose `frame_id` is a graph-local id is rejected by the sample validator (`UNKNOWN_FRAME`), exactly as before. Nothing in a sample is transformed by this contract: a consumer that wants a measurement in another frame resolves a transform (section 7) and applies it itself.

## 3. Document

A frame graph document is one JSON object with exactly these fields. Unknown fields are rejected (`FG_UNKNOWN_FIELD`).

| Field | Type | Rule |
|---|---|---|
| `contract_version` | string | SemVer of this contract. Supported: `0.1.0`. Otherwise `FG_UNSUPPORTED_VERSION`; a value that is not a string is `FG_MALFORMED`. |
| `transforms` | array | Zero or more transform records (section 4). An empty array is conformant and resolves nothing. |

## 4. Transform record

A transform record states where one frame (the child) is relative to another (the parent). It has exactly these fields.

| Field | Type | Rule |
|---|---|---|
| `parent` | string | Frame id of the parent frame. |
| `child` | string | Frame id of the child frame. Must differ from `parent` (`FG_SELF_LINK`). |
| `translation` | object | `{x, y, z}`: position of the child origin in the parent frame, in metres. Each a finite JSON number (not a boolean or string; NaN and infinity are `FG_NON_FINITE`). |
| `translation_unit` | string | Must equal `m` (`FG_INVALID_UNIT`). |
| `rotation` | object | `{w, x, y, z}`: a unit quaternion, see section 5. |

A frame id is a string matching `^[a-z][a-z0-9_]{0,31}$` (`FG_INVALID_FRAME_ID` otherwise; not a string is `FG_MALFORMED`). The three frames of the Sense data contract (`world`, `base`, `sensor`) keep their meaning from SENSE_CONTRACT section 5. Any other id is a graph-local frame, for example `arm_link`; it has no meaning outside the graph that defines it, it is not an extension of the sample contract's frames, and it cannot be used as `frame_id` in a Sense sample.

A missing field is `FG_MISSING_FIELD`; an unknown field, or an unknown or missing component of `translation` or `rotation`, is `FG_UNKNOWN_FIELD` or `FG_MISSING_FIELD`; a value of the wrong type is `FG_MALFORMED`. There is exactly one rotation representation. Euler angles, rotation matrices and axis-angle are not accepted, and no conversion is defined.

## 5. Convention

- Right-handed coordinates, as in SENSE_CONTRACT section 5.
- A transform record is the pose of the child frame expressed in the parent frame. A point given in child coordinates `p_child` has parent coordinates `p_parent = R(q) * p_child + t`, where `t` is `translation` and `R(q)` is the rotation of the unit quaternion `q`.
- The quaternion uses the Hamilton convention (`q = w + x*i + y*j + z*k`, `i*j = k`), with `R(q)` the active rotation of vectors, counter-clockwise about the axis seen from its positive end. Components are named, so there is no ordering ambiguity: `{w, x, y, z}`.
- The quaternion must be a unit quaternion: `|norm(q) - 1| <= 1e-9`, else `FG_NOT_UNIT_QUATERNION`. Input is never normalized silently. `q` and `-q` are the same rotation and are both accepted.
- Composition of two poses `a` then `b` is `(R_a * R_b, R_a * t_b + t_a)`; the inverse of `(R, t)` is `(R^-1, -R^-1 * t)`.

## 6. Graph rules

A frame graph is conformant when every transform record is conformant and:

1. no `(parent, child)` pair appears twice (`FG_DUPLICATE_EDGE`, reported on the later record);
2. every frame is the child of at most one parent, so the graph is a forest (`FG_MULTIPLE_PARENTS`, reported on the later record; a frame may have any number of children);
3. there is no cycle (`FG_CYCLE`, one violation per cycle, listing its frames).

Any violation, in a record or in rules 1 to 3, makes the whole graph non-conformant, and a non-conformant graph is never used for resolution (section 7): invalid records are not dropped to leave a partial graph that could be resolved. Record order affects diagnostics only: to report deterministically, the first record of a duplicate or of a second parent assignment is retained for the checks that follow (so the later one is the one reported), and a record with a violation of its own is left out of rules 1 to 3. Reordering conflicting records never makes a graph conformant. Violations are sorted by `(path, code, message)`, so the result is deterministic. Frames are connected only by records the document states: nothing is assumed about `world`, `base` and `sensor`.

## 7. Resolution

`resolve(graph, source, target)` returns the transform that maps coordinates in frame `source` to coordinates in frame `target`: `p_target = R * p_source + t`.

- A graph that is not conformant resolves nothing; the graph violations are returned.
- `source` and `target` must be frame ids (`FG_INVALID_FRAME_ID`, `FG_MALFORMED`) that appear in some record of the graph (`FG_FRAME_NOT_IN_GRAPH`). The implementation never invents an identity or default transform for an unknown frame or relationship; the identity is returned only for a frame of the graph resolved to itself.
- Frames in different components of the forest have no path (`FG_NO_PATH`).
- Otherwise the path goes up from both frames to their nearest common ancestor. With `T_c_s` and `T_c_t` the composed poses of source and target in that ancestor, the result is `inverse(T_c_t) o T_c_s`. The reverse lookup (`resolve(graph, target, source)`) is therefore the inverse transform.
- The result is canonical: translation in metres, `translation_unit` `m`, the quaternion normalized to unit length with its sign chosen so that its first non-zero component (in the order `w, x, y, z`, treating magnitudes below `1e-12` as zero) is positive, and no negative zero.
- Arithmetic is IEEE 754 double precision. Reference tests compare against hand-derived answers with an absolute tolerance of `1e-9` for translations up to `1e3` m. No accuracy claim is made beyond the tests.

## 8. Error codes

| Code | Meaning |
|---|---|
| `FG_MALFORMED` | A value has the wrong type or shape, or the document or a record is not an object. |
| `FG_MISSING_FIELD` | A required field or component is absent. |
| `FG_UNKNOWN_FIELD` | A field or component is not defined by this contract. |
| `FG_UNSUPPORTED_VERSION` | `contract_version` is a string but not a supported version. |
| `FG_INVALID_FRAME_ID` | A frame id does not match the frame id pattern. |
| `FG_SELF_LINK` | A record has the same parent and child. |
| `FG_NON_FINITE` | A number is NaN or infinite. |
| `FG_INVALID_UNIT` | `translation_unit` is not `m`. |
| `FG_NOT_UNIT_QUATERNION` | The rotation is not a unit quaternion within the tolerance. |
| `FG_DUPLICATE_EDGE` | The same `(parent, child)` pair is stated more than once. |
| `FG_MULTIPLE_PARENTS` | A frame has more than one parent. |
| `FG_CYCLE` | The records contain a cycle. |
| `FG_FRAME_NOT_IN_GRAPH` | A frame asked for in a resolution has no record in the graph. |
| `FG_NO_PATH` | The two frames are in different components of the graph. |

## 9. Worked example

A synthetic graph: the `base` frame sits at (1, 2, 0) m in `world`, turned 90 degrees counter-clockwise about z (`q = {w: 0.7071067811865476, x: 0, y: 0, z: 0.7071067811865476}`); the `sensor` frame sits at (0.1, 0, 0.2) m in `base` with no rotation.

A point at (1, 0, 0) in `sensor` is at (1.1, 0, 0.2) in `base` (add the offset). In `world`, the 90 degree turn takes (1.1, 0, 0.2) to (0, 1.1, 0.2), and adding (1, 2, 0) gives (1, 3.1, 0.2). So `resolve(graph, "sensor", "world")` is translation (1, 2.1, 0.2) with the quaternion above, and applying it to (1, 0, 0) gives (1, 3.1, 0.2). The reverse, `resolve(graph, "world", "sensor")`, has translation (-2.1, 1, -0.2) and the quaternion with `z` negated. The same graph, with the same expected answers, is the fixture `tests/frame_graph/fixtures/valid/chain_world_base_sensor.json`.

## 10. Limitations

- Transforms are static and carry no timestamp, validity or uncertainty. Time-varying transforms, interpolation and extrapolation are not defined.
- Nothing here measures or verifies a physical mounting, calibration or robot coordinate system. A conformant graph says only that its records are well formed, consistent and resolvable.
- The graph is a forest of single-parent edges. Loops of constraints, redundant (over-determined) transforms and graph optimization are out of scope.
- There is no transport, distribution or telemetry, no ROS or external library, and no integration with Mind, Motion or Skill.
- Review is the interim D-047 role, not independent review.

## 11. Versioning and lifecycle

This is frame graph contract 0.1.0, delivered as a proposal with KOS-SENSE-003. It is accepted only by a central approval recorded in kritva-program; until then nothing here is accepted. While the major version is 0, a change may be breaking; every change needs a changelog entry in [planning/CHANGELOG.md](../planning/CHANGELOG.md) and a decision, and supported versions are listed in section 3. Adding a rotation representation, a time field or a new unit is a change to this contract. Changing the meaning of `world`, `base` or `sensor` is a change to the Sense data contract, with its own version.

## 12. Verification

`make test-unit` runs `tests/frame_graph/`: valid and invalid fixtures, known-answer resolution, inverse checks, boundary cases and the command line. The command line is `python3 -m kritva_sense.frame_graph FILE.json [FROM TO]`, reading a bare frame graph document; it exits 0 when conformant (and resolved), 1 when not, 2 on a usage or read error.
