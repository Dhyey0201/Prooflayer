"""Secret scanning for evidence, reports and the repository.

Two kinds of needle: high-signal credential *patterns* (private keys, cloud
and SaaS token formats), and *exact values* of secrets the process actually
holds (configured API keys, secret-looking environment variables). Results
only ever contain counts and locations, never the matched text.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

SECRET_PATTERNS: dict[str, re.Pattern[bytes]] = {
    "private_key": re.compile(
        rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY"
    ),
    "aws_access_key_id": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})"),
    "openai_style_key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    "slack_token": re.compile(rb"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "tavily_key": re.compile(rb"\btvly-[A-Za-z0-9]{20,}"),
    "jwt": re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "assigned_api_key": re.compile(
        rb"\b(?:NEBIUS|TAVILY|OPENAI|ANTHROPIC)_API_KEY\s*[=:]\s*[\"']?[A-Za-z0-9_.\-]{16,}"
    ),
}

_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.IGNORECASE)
# Shorter values are too likely to occur by chance to be meaningful needles.
MIN_VALUE_CHARS = 12


def environment_secret_values(environ: Mapping[str, str] | None = None) -> list[bytes]:
    """Values of secret-looking environment variables, for exact-match scanning."""
    environ = os.environ if environ is None else environ
    return sorted(
        {
            value.encode()
            for name, value in environ.items()
            if _SECRET_NAME.search(name) and len(value) >= MIN_VALUE_CHARS
        }
    )


@dataclass
class ScanResult:
    bytes_scanned: int = 0
    sources_scanned: int = 0
    exact_needles: int = 0
    # Counts per pattern name / "exact_value"; locations are source labels.
    matches: dict[str, int] = field(default_factory=dict)
    locations: list[str] = field(default_factory=list)

    @property
    def total_matches(self) -> int:
        return sum(self.matches.values())

    def to_wire(self) -> dict:
        return {
            "bytes_scanned": self.bytes_scanned,
            "sources_scanned": self.sources_scanned,
            "patterns": sorted(SECRET_PATTERNS),
            "exact_needles": self.exact_needles,
            "matches": self.total_matches,
            "matches_by_kind": dict(sorted(self.matches.items())),
        }


def scan(
    sources: Iterable[tuple[str, bytes]],
    exact_values: Iterable[bytes] = (),
    *,
    allow_line: re.Pattern[bytes] | None = None,
) -> ScanResult:
    needles = [v for v in set(exact_values) if len(v) >= MIN_VALUE_CHARS]
    result = ScanResult(exact_needles=len(needles))
    for label, data in sources:
        result.sources_scanned += 1
        result.bytes_scanned += len(data)
        for kind, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(data):
                if allow_line is not None and allow_line.search(_line_at(data, match.start())):
                    continue
                result.matches[kind] = result.matches.get(kind, 0) + 1
                result.locations.append(f"{label}:{data.count(b'\n', 0, match.start()) + 1}")
        for needle in needles:
            count = data.count(needle)
            if count:
                result.matches["exact_value"] = result.matches.get("exact_value", 0) + count
                result.locations.append(label)
    return result


def _line_at(data: bytes, index: int) -> bytes:
    start = data.rfind(b"\n", 0, index) + 1
    end = data.find(b"\n", index)
    return data[start : None if end < 0 else end]
