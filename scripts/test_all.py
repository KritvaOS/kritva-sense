#!/usr/bin/env python3
"""The aggregate Sense test gate (KOS-SENSE-010, AC-1007). Standard library only.

    python3 scripts/test_all.py [--gate NAME=COMMAND ...]      (`make test` runs this)

Runs the three gates once each, in this order, and shows their results separately:

    unit         make test-unit          the unit tests
    integration  make test-integration   the integration gate (KOS-SENSE-009)
    regression   make test-regression    the regression gate (KOS-SENSE-010)

Every gate runs even when an earlier one failed, so one run shows all three results. Each result is one of:

    PASS     the command exited 0 and printed the evidence that the tests ran (unit: `Ran N tests` and `OK`; the two
             gates: their `...-GATE PASS` line)
    FAIL     the command exited with a status other than 0 and 3
    MISSING  the gate did not run or proves nothing: the command exited 3 (NOT_IMPLEMENTED), could not be started, or
             exited 0 without the evidence of a pass (an incomplete run)

The run ends with one `TEST-SUMMARY` line. Exit 0 only when all three are PASS; exit 1 when any one is FAIL or MISSING;
exit 2 for a usage error. A missing gate is never a pass. `--gate` replaces the command of one gate (used by the tests
of this script with stand-in commands); the default commands are the three make targets above.
"""
import argparse
import re
import subprocess
import sys

DEFAULT_GATES = (
    ("unit", "make --no-print-directory test-unit", re.compile(r"(?m)^Ran [1-9]\d* tests?\b.*\n(?:.*\n)*?OK\b")),
    ("integration", "make --no-print-directory test-integration", re.compile(r"(?m)^INTEGRATION-GATE PASS$")),
    ("regression", "make --no-print-directory test-regression", re.compile(r"(?m)^REGRESSION-GATE PASS$")),
)
NOT_IMPLEMENTED = 3


def run_gate(name, command, evidence, out=sys.stdout):
    """Run one gate command, echo its output, and classify it. Returns (status, reason)."""
    out.write("\n===== %s: %s =====\n" % (name, command))
    out.flush()
    try:
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                errors="replace")
    except OSError as exc:
        out.write("could not start: %s\n" % exc)
        return "MISSING", "could not be started (%s)" % exc
    lines = []
    for line in proc.stdout:          # shown as it arrives: the unit gate takes minutes
        out.write(line)
        out.flush()
        lines.append(line)
    proc.wait()
    r = subprocess.CompletedProcess(command, proc.returncode, "".join(lines))
    if r.returncode == NOT_IMPLEMENTED:
        return "MISSING", "exit 3: NOT_IMPLEMENTED"
    if r.returncode == 127 and "not found" in r.stdout.lower():
        return "MISSING", "command not found"
    if r.returncode != 0:
        return "FAIL", "exit %d" % r.returncode
    if not evidence.search(r.stdout):
        return "MISSING", "exit 0 without the evidence of a pass: incomplete run"
    return "PASS", "exit 0"


def run_all(gates, out=sys.stdout):
    """Run every gate once. Returns (exit_code, results) with results as [(name, status, reason)]."""
    results = []
    for name, command, evidence in gates:
        status, reason = run_gate(name, command, evidence, out)
        results.append((name, status, reason))
    out.write("\n===== results =====\n")
    for name, status, reason in results:
        out.write("%-12s %-8s %s\n" % (name, status, reason))
    out.write("TEST-SUMMARY %s\n" % " ".join("%s=%s" % (n, s) for n, s, _ in results))
    ok = all(s == "PASS" for _, s, _ in results)
    out.write("TEST PASS\n" if ok else "TEST FAIL: at least one gate failed, is missing or is incomplete\n")
    return (0 if ok else 1), results


def main(argv=None):
    parser = argparse.ArgumentParser(prog="test_all.py", add_help=True)
    parser.add_argument("--gate", action="append", default=[], metavar="NAME=COMMAND",
                        help="replace the command of the gate NAME (unit, integration or regression)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    gates = {name: (command, evidence) for name, command, evidence in DEFAULT_GATES}
    for item in args.gate:
        name, sep, command = item.partition("=")
        if not sep or name not in gates or not command.strip():
            print("test_all: --gate needs NAME=COMMAND with NAME one of %s" % ", ".join(gates), file=sys.stderr)
            return 2
        gates[name] = (command, gates[name][1])
    code, _ = run_all([(name, gates[name][0], gates[name][1]) for name, _, _ in DEFAULT_GATES])
    return code


if __name__ == "__main__":
    sys.exit(main())
