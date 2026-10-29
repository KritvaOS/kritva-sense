"""python3 -m kritva_sense FILE.json: validate one sample; exit 0 conformant, 1 not, 2 usage/read error."""
import json
import sys

from .validator import validate_sample


def main(argv):
    if len(argv) != 2:
        print("usage: python3 -m kritva_sense FILE.json", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            sample = json.load(fh)
    except (OSError, ValueError) as exc:
        print("cannot read sample: %s" % exc, file=sys.stderr)
        return 2
    violations = validate_sample(sample)
    for v in violations:
        print("%s %s: %s" % (v.code, v.path, v.message))
    print("conformant" if not violations else "not conformant")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
