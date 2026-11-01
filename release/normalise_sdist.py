"""Rewrites a source distribution deterministically (KOS-SENSE-007, AC-706). Standard library only.

    python3 release/normalise_sdist.py SDIST.tar.gz        (SOURCE_DATE_EPOCH must be set)

The pinned setuptools writes the build time, the build user and the gzip header time into the archive and does not
read SOURCE_DATE_EPOCH for it, so two builds of one revision differ in those fields only. This script keeps every
member's name, type, mode, size, link target and content, and sets the fields that carry the build time or the
build user to fixed values: members sorted by name, modification time SOURCE_DATE_EPOCH, owner and group 0 and
"root", no extended time headers, gzip header time 0. The file is replaced in place. Exit 0; exit 2 on a usage error.
"""
import gzip
import io
import os
import sys
import tarfile

TIME_KEYS = ("mtime", "atime", "ctime")


def normalise(path, epoch):
    with tarfile.open(path, "r:gz") as src:
        members = sorted(src.getmembers(), key=lambda m: m.name)
        payload = [(m, src.extractfile(m).read() if m.isfile() else None) for m in members]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as out:
        for m, data in payload:
            info = tarfile.TarInfo(m.name)
            info.type, info.mode, info.size, info.linkname = m.type, m.mode & 0o7777, m.size, m.linkname
            info.mtime, info.uid, info.gid, info.uname, info.gname = epoch, 0, 0, "root", "root"
            info.pax_headers = {k: v for k, v in m.pax_headers.items() if k not in TIME_KEYS}
            out.addfile(info, io.BytesIO(data) if data is not None else None)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9) as gz:
            gz.write(raw.getvalue())
    os.replace(tmp, path)


def main(argv):
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    if len(argv) != 2 or not epoch.isdigit():
        print("usage: SOURCE_DATE_EPOCH=N python3 release/normalise_sdist.py SDIST.tar.gz", file=sys.stderr)
        return 2
    normalise(argv[1], int(epoch))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
