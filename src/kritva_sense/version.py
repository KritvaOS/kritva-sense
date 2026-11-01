"""Version information (KOS-SENSE-007): the package version and the interface versions it implements, kept apart.

    python3 -m kritva_sense.version [--check]      (installed command: kritva-sense-version)

The package version identifies this software release. It is not a contract version: the Sense data contract, the
frame graph contract, the stream contract, the consumer conformance harness and the synthetic data generator each
keep their own version, which a release changes only when that interface changes (RELEASE.md). `--check` also
compares the declared contract versions with the contract files shipped with the package.
Exit 0: versions printed (and consistent with --check); 1: --check found a mismatch; 2: usage error.
"""
import json
import re
import sys
from pathlib import Path

PACKAGE_NAME = "kritva-sense"
PACKAGE_VERSION = "0.2.0"

FILES = {
    "sense": ("SENSE_CONTRACT.md", "sense-sample.schema.json"),
    "frame_graph": ("FRAME_GRAPH_CONTRACT.md", "frame-transform.schema.json"),
    "stream": ("STREAM_CONTRACT.md", "stream.schema.json"),
}
_DOC_ROW = {
    "sense": r"^\| Version \| Contract version: (\S+) \|$",
    "frame_graph": r"^\| Version \| Frame graph contract version: (\S+) \|$",
    "stream": r"^\| Version \| Stream contract version: (\S+) \|$",
}


def declared_versions():
    """The versions this package's code declares and implements, one per interface."""
    from . import conformance, frame_graph, generator, stream, validator
    return {
        "package_version": PACKAGE_VERSION,
        "sense_contract_version": validator.CONTRACT_VERSION,
        "frame_graph_contract_version": frame_graph.FRAME_GRAPH_VERSION,
        "stream_contract_version": stream.STREAM_VERSION,
        "harness_version": conformance.HARNESS_VERSION,
        "generator_version": generator.GENERATOR_VERSION,
    }


def contract_dir():
    """The directory with the shipped contract files: kritva_sense/contract in an installed package, otherwise the
    contract/ directory of the source checkout. None when neither exists."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "contract", here.parent.parent / "contract"):
        if candidate.is_dir():
            return candidate
    return None


def shipped_versions(directory=None):
    """The versions read from the contract files themselves: the version row of each contract document and the
    version constant of each schema. A value that cannot be read is None."""
    directory = Path(directory) if directory is not None else contract_dir()
    found = {}
    for key, (doc_name, schema_name) in FILES.items():
        doc = directory / doc_name if directory else None
        text = doc.read_text(encoding="utf-8") if doc and doc.is_file() else ""
        m = re.search(_DOC_ROW[key], text, re.M)
        found[key + "_document"] = m.group(1) if m else None
        schema = directory / schema_name if directory else None
        value = None
        if schema and schema.is_file():
            props = json.loads(schema.read_text(encoding="utf-8")).get("properties", {})
            field = props.get("stream_version" if key == "stream" else "contract_version", {})
            if "const" in field:
                value = field["const"]
            elif isinstance(field.get("enum"), list) and len(field["enum"]) == 1:
                value = field["enum"][0]
        found[key + "_schema"] = value
    return found


def check_shipped_contracts(directory=None, declared=None):
    """Compare the declared contract versions with the shipped contract files: a list of problems, empty when they
    agree. A file that is missing or has no readable version is a problem, never a pass."""
    declared = declared or declared_versions()
    directory = Path(directory) if directory is not None else contract_dir()
    if directory is None:
        return ["no contract directory is available"]
    problems = []
    for key, (doc_name, schema_name) in FILES.items():
        for name in (doc_name, schema_name):
            if not (directory / name).is_file():
                problems.append("%s is missing" % name)
    found = shipped_versions(directory)
    for key in FILES:
        want = declared[key + "_contract_version"]
        for part, name in (("document", FILES[key][0]), ("schema", FILES[key][1])):
            got = found[key + "_" + part]
            if got is None:
                if (directory / name).is_file():
                    problems.append("%s: no readable version" % name)
            elif got != want:
                problems.append("%s declares %s but the code implements %s" % (name, got, want))
    return problems


def installed_version():
    """The version in the installed distribution metadata, or None in a source checkout."""
    from importlib import metadata
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None


def version_info():
    """The documented version-information interface: a dict with the six declared versions, the version of the
    installed metadata (None in a source checkout) and the contract versions read from the shipped files."""
    info = declared_versions()
    info["installed_metadata_version"] = installed_version()
    info["shipped_contract_files"] = shipped_versions()
    return info


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--check"]):
        print("usage: python3 -m kritva_sense.version [--check]", file=sys.stderr)
        return 2
    info = version_info()
    print(json.dumps(info, indent=2, sort_keys=True))
    if args:
        problems = check_shipped_contracts()
        meta = info["installed_metadata_version"]
        if meta is not None and meta != PACKAGE_VERSION:
            problems.append("installed metadata version %s differs from PACKAGE_VERSION %s" % (meta, PACKAGE_VERSION))
        for p in problems:
            print("MISMATCH: %s" % p)
        print("versions consistent" if not problems else "versions inconsistent")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
