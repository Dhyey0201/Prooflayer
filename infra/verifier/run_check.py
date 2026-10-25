"""Trusted entrypoint of the independent verifier image.

Reads a tar archive of the workspace to verify from stdin, extracts it into the
container's tmpfs and runs pytest on the pinned targets given as arguments.
The host never mounts a directory into the container: stdin is the only input.

Exit codes: pytest's own (0 passed, 1 failed, 2-5 interrupted / internal /
usage / no tests collected) or 100+ for a harness failure, so the host can tell
a failing test from a broken verification.
"""

import io
import os
import re
import sys
import tarfile

REPO = "/verify/repo"
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
TARGET = re.compile(r"^tests(/[A-Za-z0-9_]+\.py)?$")


def main(argv: list[str]) -> int:
    targets = argv[1:]
    if not targets or not all(TARGET.fullmatch(t) for t in targets):
        print("verifier: invalid pytest targets", file=sys.stderr)
        return 101
    data = sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        print("verifier: missing or oversized workspace archive", file=sys.stderr)
        return 102
    os.makedirs(REPO, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            # "data" filter: no absolute paths, links out of the tree, devices or setuid bits.
            archive.extractall(REPO, filter="data")
    except (tarfile.TarError, OSError) as exc:
        print(f"verifier: archive rejected ({type(exc).__name__})", file=sys.stderr)
        return 103
    os.chdir(REPO)
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
    # Fixed argv (targets validated above); no shell is involved.
    os.execv(sys.executable, argv)  # noqa: S606
    return 104  # unreachable


if __name__ == "__main__":
    sys.exit(main(sys.argv))
