"""Reference implementation of the Sense frame graph contract (contract/FRAME_GRAPH_CONTRACT.md).

It implements the contract; it never defines or alters it, and it does not change the Sense data
contract 0.1.0. Standard library only. Software behaviour on synthetic data only: nothing here says
that a frame, a mounting transform or a calibration is physically correct.

Results are deterministic: violations are sorted by (path, code, message).

    python3 -m kritva_sense.frame_graph FILE.json              validate a frame graph document
    python3 -m kritva_sense.frame_graph FILE.json FROM TO      also resolve the transform FROM -> TO
Exit 0 conformant, 1 not conformant or no such transform, 2 usage or read error.
"""
import json
import math
import re
import sys

from .validator import Violation

FRAME_GRAPH_VERSION = "0.1.0"
SUPPORTED_VERSIONS = (FRAME_GRAPH_VERSION,)

# A unit quaternion is accepted when |norm - 1| <= QUAT_TOLERANCE. Nothing is normalized silently on input.
QUAT_TOLERANCE = 1e-9
# Below this magnitude a quaternion component counts as zero when the sign of a result is chosen.
SIGN_EPSILON = 1e-12

ERROR_CODES = (
    "FG_MALFORMED",
    "FG_MISSING_FIELD",
    "FG_UNKNOWN_FIELD",
    "FG_UNSUPPORTED_VERSION",
    "FG_INVALID_FRAME_ID",
    "FG_SELF_LINK",
    "FG_NON_FINITE",
    "FG_INVALID_UNIT",
    "FG_NOT_UNIT_QUATERNION",
    "FG_DUPLICATE_EDGE",
    "FG_MULTIPLE_PARENTS",
    "FG_CYCLE",
    "FG_FRAME_NOT_IN_GRAPH",
    "FG_NO_PATH",
)

TRANSFORM_FIELDS = ("parent", "child", "translation", "translation_unit", "rotation")
TRANSLATION_FIELDS = ("x", "y", "z")
ROTATION_FIELDS = ("w", "x", "y", "z")
TRANSLATION_UNIT = "m"
FRAME_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

_IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sorted(vs):
    return sorted(vs, key=lambda v: (v.path, v.code, v.message))


def _object_numbers(obj, fields, path, out):
    """Check that obj is an object holding exactly `fields`, each a finite number. Return the numbers or None."""
    if not isinstance(obj, dict):
        out.append(Violation("FG_MALFORMED", path, "must be an object with %s" % ", ".join(fields)))
        return None
    ok = True
    for f in fields:
        if f not in obj:
            out.append(Violation("FG_MISSING_FIELD", "%s.%s" % (path, f), "required component is absent"))
            ok = False
    for f in sorted(k for k in obj if k not in fields):
        out.append(Violation("FG_UNKNOWN_FIELD", "%s.%s" % (path, f), "component is not defined by the contract"))
        ok = False
    vals = []
    for f in fields:
        if f not in obj:
            continue
        v = obj[f]
        if not _is_num(v):
            out.append(Violation("FG_MALFORMED", "%s.%s" % (path, f), "must be a number"))
            ok = False
        elif not math.isfinite(v):
            out.append(Violation("FG_NON_FINITE", "%s.%s" % (path, f), "must be finite"))
            ok = False
        else:
            vals.append(float(v))
    return tuple(vals) if ok else None


def _frame_id(value, path, out):
    if not isinstance(value, str):
        out.append(Violation("FG_MALFORMED", path, "frame id must be a string"))
        return False
    if not FRAME_ID_RE.match(value):
        out.append(Violation("FG_INVALID_FRAME_ID", path, "frame id must match %s" % FRAME_ID_RE.pattern))
        return False
    return True


def validate_transform(record, path="$"):
    """Return a sorted list of Violation for one transform record; [] means conformant."""
    out = []
    if not isinstance(record, dict):
        return [Violation("FG_MALFORMED", path, "transform must be an object")]
    for f in TRANSFORM_FIELDS:
        if f not in record:
            out.append(Violation("FG_MISSING_FIELD", "%s.%s" % (path, f), "required field is absent"))
    for f in sorted(k for k in record if k not in TRANSFORM_FIELDS):
        out.append(Violation("FG_UNKNOWN_FIELD", "%s.%s" % (path, f), "field is not defined by contract %s" % FRAME_GRAPH_VERSION))
    parent_ok = child_ok = False
    if "parent" in record:
        parent_ok = _frame_id(record["parent"], path + ".parent", out)
    if "child" in record:
        child_ok = _frame_id(record["child"], path + ".child", out)
    if parent_ok and child_ok and record["parent"] == record["child"]:
        out.append(Violation("FG_SELF_LINK", path, "parent and child are the same frame"))
    if "translation" in record:
        _object_numbers(record["translation"], TRANSLATION_FIELDS, path + ".translation", out)
    if "translation_unit" in record and record["translation_unit"] != TRANSLATION_UNIT:
        out.append(Violation("FG_INVALID_UNIT", path + ".translation_unit", "must be %r" % TRANSLATION_UNIT))
    if "rotation" in record:
        q = _object_numbers(record["rotation"], ROTATION_FIELDS, path + ".rotation", out)
        if q is not None and abs(math.hypot(*q) - 1.0) > QUAT_TOLERANCE:
            out.append(Violation("FG_NOT_UNIT_QUATERNION", path + ".rotation",
                                 "norm must be 1 within %g" % QUAT_TOLERANCE))
    return _sorted(out)


def _edges(doc):
    """The well-formed edges of a document, in order, as (index, parent, child, record)."""
    for i, rec in enumerate(doc.get("transforms", ()) if isinstance(doc.get("transforms"), list) else ()):
        if not validate_transform(rec):
            yield i, rec["parent"], rec["child"], rec


def validate_graph(doc):
    """Return a sorted list of Violation for a frame graph document; [] means conformant."""
    out = []
    if not isinstance(doc, dict):
        return [Violation("FG_MALFORMED", "$", "frame graph must be an object")]
    for f in ("contract_version", "transforms"):
        if f not in doc:
            out.append(Violation("FG_MISSING_FIELD", f, "required field is absent"))
    for f in sorted(k for k in doc if k not in ("contract_version", "transforms")):
        out.append(Violation("FG_UNKNOWN_FIELD", f, "field is not defined by contract %s" % FRAME_GRAPH_VERSION))
    if "contract_version" in doc:
        ver = doc["contract_version"]
        if not isinstance(ver, str):
            out.append(Violation("FG_MALFORMED", "contract_version", "must be a string"))
        elif ver not in SUPPORTED_VERSIONS:
            out.append(Violation("FG_UNSUPPORTED_VERSION", "contract_version",
                                 "%r is not supported; supported: %s" % (ver, ", ".join(SUPPORTED_VERSIONS))))
    transforms = doc.get("transforms")
    if "transforms" in doc and not isinstance(transforms, list):
        out.append(Violation("FG_MALFORMED", "transforms", "must be an array"))
        return _sorted(out)
    for i, rec in enumerate(transforms or ()):
        out.extend(validate_transform(rec, "transforms[%d]" % i))

    seen = {}        # (parent, child) -> first index
    parent_of = {}   # child -> (parent, first index)
    for i, parent, child, _ in _edges(doc):
        path = "transforms[%d]" % i
        if (parent, child) in seen:
            out.append(Violation("FG_DUPLICATE_EDGE", path, "%s -> %s is already defined at transforms[%d]" % (parent, child, seen[(parent, child)])))
            continue
        seen[(parent, child)] = i
        if child in parent_of:
            out.append(Violation("FG_MULTIPLE_PARENTS", path, "%s already has parent %s (transforms[%d]); a frame has at most one parent" % (child, parent_of[child][0], parent_of[child][1])))
            continue
        parent_of[child] = (parent, i)
    out.extend(_cycles({c: p for c, (p, _) in parent_of.items()}))
    return _sorted(out)


def _cycles(parent):
    """One FG_CYCLE violation per cycle in the child -> parent map."""
    out, done, reported = [], set(), set()
    for start in sorted(parent):
        if start in done:
            continue
        chain, cur = [], start
        while cur in parent and cur not in done and cur not in chain:
            chain.append(cur)
            cur = parent[cur]
        if cur in chain:
            ring = chain[chain.index(cur):]
            key = frozenset(ring)
            if key not in reported:
                reported.add(key)
                out.append(Violation("FG_CYCLE", "transforms", "cycle among frames: %s" % ", ".join(sorted(ring))))
        done.update(chain)
    return out


# ---- pose arithmetic: a pose is (translation (x, y, z), unit quaternion (w, x, y, z)) ----

def _qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def _qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def _rotate(q, v):
    w, ux, uy, uz = q
    vx, vy, vz = v
    cx, cy, cz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx          # u x v
    dx, dy, dz = uy * cz - uz * cy, uz * cx - ux * cz, ux * cy - uy * cx          # u x (u x v)
    return (vx + 2.0 * (w * cx + dx), vy + 2.0 * (w * cy + dy), vz + 2.0 * (w * cz + dz))


def _compose(a, b):
    """The pose a o b: apply b, then a. For parent-child poses, compose(T_p_c, T_c_x) = T_p_x."""
    rt = _rotate(a[1], b[0])
    return ((rt[0] + a[0][0], rt[1] + a[0][1], rt[2] + a[0][2]), _qmul(a[1], b[1]))


def _invert(a):
    qc = _qconj(a[1])
    t = _rotate(qc, a[0])
    return ((-t[0], -t[1], -t[2]), qc)


def _canonical_quaternion(q):
    n = math.hypot(*q)
    q = [c / n for c in q]
    for c in q:
        if abs(c) > SIGN_EPSILON:
            if c < 0:
                q = [-k for k in q]
            break
    return tuple(k + 0.0 for k in q)  # + 0.0 turns -0.0 into 0.0


def _record(pose):
    t, q = pose
    q = _canonical_quaternion(q)
    return {"translation": {"x": t[0] + 0.0, "y": t[1] + 0.0, "z": t[2] + 0.0},
            "translation_unit": TRANSLATION_UNIT,
            "rotation": dict(zip(ROTATION_FIELDS, q))}


def _pose(rec):
    tr, rot = rec["translation"], rec["rotation"]
    return ((float(tr["x"]), float(tr["y"]), float(tr["z"])),
            tuple(float(rot[k]) for k in ROTATION_FIELDS))


def resolve(doc, source, target):
    """Resolve the transform that maps coordinates in frame `source` to coordinates in frame `target`.

    Returns (transform, violations). `transform` is {"translation", "translation_unit", "rotation"} in
    canonical form (unit quaternion, w >= 0), or None with the reasons in `violations`. A graph that is not
    conformant resolves nothing. An unknown or unconnected relationship is an error: no identity or
    default transform is ever invented. The identity is returned only for a frame in the graph to itself.
    """
    graph_violations = validate_graph(doc)
    if graph_violations:
        return None, graph_violations
    out = []
    parent = {}
    frames = set()
    for _, p, c, rec in _edges(doc):
        parent.setdefault(c, (p, _pose(rec)))   # validate_graph guarantees one parent per child
        frames.update((p, c))
    for name, label in ((source, "source"), (target, "target")):
        if not _frame_id(name, label, out):
            continue
        if name not in frames:
            out.append(Violation("FG_FRAME_NOT_IN_GRAPH", label, "frame %r has no transform in this graph" % name))
    if out:
        return None, _sorted(out)

    def ascend(frame):
        chain, acc, cur = [(frame, _IDENTITY)], _IDENTITY, frame
        while cur in parent:
            p, pose = parent[cur]
            acc = _compose(pose, acc)           # T_p_frame
            cur = p
            chain.append((cur, acc))
        return chain

    up_source, up_target = ascend(source), ascend(target)
    in_target = dict(up_target)
    for frame, t_common_source in up_source:    # nearest common ancestor first
        if frame in in_target:
            pose = _compose(_invert(in_target[frame]), t_common_source)
            return _record(pose), []
    return None, [Violation("FG_NO_PATH", "$", "frames %r and %r are not connected" % (source, target))]


def transform_point(transform, point):
    """Apply a resolved transform record to a point (x, y, z): returns the point in the target frame."""
    t, q = _pose(transform)
    r = _rotate(q, tuple(float(c) for c in point))
    return (r[0] + t[0], r[1] + t[1], r[2] + t[2])


def main(argv):
    if len(argv) not in (2, 4):
        print("usage: python3 -m kritva_sense.frame_graph FILE.json [FROM TO]", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("cannot read frame graph: %s" % exc, file=sys.stderr)
        return 2
    if len(argv) == 2:
        violations = validate_graph(doc)
        result = None
    else:
        result, violations = resolve(doc, argv[2], argv[3])
    for v in violations:
        print("%s %s: %s" % (v.code, v.path, v.message))
    if result is not None:
        print(json.dumps(result, indent=2, sort_keys=True))
    print("conformant" if not violations else "not conformant")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
