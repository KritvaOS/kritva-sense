#!/usr/bin/env python3
"""Regenerate the golden data of the regression suite (KOS-SENSE-010, AC-1005). Standard library only.

    python3 scripts/regenerate_regression_golden.py            show what would change (writes nothing)
    python3 scripts/regenerate_regression_golden.py --write    rewrite tests/regression/golden/*.json   (`make regression-golden` does this)

This is the only way the golden data change. No test and not the regression gate ever runs it. Run it only after a
deliberate change of accepted behaviour has been decided: the rule in tests/regression/README.md (contract version,
changelog entry and central decision, as the V2 acceptance standard requires) comes first, the golden data follow, and
the diff of the golden files is part of the pull request that makes the change. Exit 0: the golden data are current (or
were written); 1: they differ and --write was not given; 2: usage error.
"""
import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "regression"))
import regression_support as R  # noqa: E402


def current():
    return {
        "contract_cases.json": R.collect_contract_cases(),
        "contract_pins.json": R.pins(),
        "command_lines.json": R.collect_command_lines(),
        "conformance.json": R.collect_conformance(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="regenerate_regression_golden.py")
    parser.add_argument("--write", action="store_true", help="rewrite the golden files (default: only show the difference)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    changed = 0
    for name, doc in current().items():
        new = R.dumps_golden(doc)
        path = R.GOLDEN / name
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        if new == old:
            print("unchanged: %s" % name)
            continue
        changed += 1
        if args.write:
            R.GOLDEN.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
            print("written:   %s" % name)
        else:
            print("differs:   %s" % name)
            sys.stdout.writelines(list(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                                            "golden/" + name, "current/" + name, n=1))[:60])
    if changed and not args.write:
        print("golden data differ from current behaviour; run with --write only after the change was decided", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
