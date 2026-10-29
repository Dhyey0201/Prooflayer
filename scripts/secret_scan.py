"""Scan tracked files (and optionally all git history) for credentials.

    python scripts/secret_scan.py            # every file `git ls-files` lists
    python scripts/secret_scan.py --history  # also every patch in `git log -p --all`

Uses the credential patterns in ``prooflayer_api.bench.secret_scan`` plus the
exact values of secret-looking variables in this process's environment, so a
real key exported in the shell is caught even in an unknown format. Prints
locations only, never matched text. A line containing ``secret-scan: allow``
or the repo's fake-key marker ``DO-NOT-LEAK`` is skipped. Exit 1 on any match.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps" / "api"))

from prooflayer_api.bench.secret_scan import environment_secret_values, scan  # noqa: E402

ALLOW = re.compile(rb"secret-scan: allow|DO-NOT-LEAK")


def _git(*args: str) -> bytes:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", *args],  # noqa: S607 - git from PATH
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", action="store_true", help="also scan every commit patch")
    args = parser.parse_args()

    sources = []
    for name in _git("ls-files", "-z").split(b"\0"):
        path = root / name.decode()
        if name and path.is_file():
            sources.append((name.decode(), path.read_bytes()))
    if args.history:
        sources.append(("git-history", _git("log", "-p", "--all", "--no-color")))

    result = scan(sources, environment_secret_values(), allow_line=ALLOW)
    for location in result.locations:
        print(f"possible secret: {location}")
    print(
        f"secret scan: {result.sources_scanned} sources, {result.bytes_scanned} bytes, "
        f"{result.exact_needles} environment values, {result.total_matches} matches"
    )
    return 1 if result.total_matches else 0


if __name__ == "__main__":
    sys.exit(main())
