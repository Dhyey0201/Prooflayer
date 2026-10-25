"""Offline verification of a ProofLayer certificate against its evidence.

    python -m prooflayer_api.evidence.verify_cli --certificate cert.json --events events.json \\
        [--ledger data/evidence-ledger.jsonl] [--expected-manifest-sha256 HEX]
    python -m prooflayer_api.evidence.verify_cli --api http://127.0.0.1:8000/api/v1 --run RUN_ID \\
        [--ledger apps/api/data/evidence-ledger.jsonl]

Checks, each reported separately:

1. ``manifest_digest``: ``evidence_manifest_sha256`` is the SHA-256 of the embedded manifest.
2. ``content_digest``: the manifest's ``content_sha256`` covers this verdict, claims,
   checks and limitations (so none can be edited without breaking 1).
3. ``identity``: run, template and verdict agree between certificate and manifest.
4. ``event_chain``: every event's hash and link recompute from seq 1.
5. ``chain_head``: the event at ``events_through_seq`` has the manifest's chain head.
6. ``issued_event``: a ``certificate.issued`` event records these digests.
7. ``detached_ledger`` / ``expected_manifest``: the digest matches an independent copy.

Exit status 0 only if every check that ran passed. Without a ledger or an
expected digest, a full rewrite of the database cannot be ruled out, and the
report says so (``detached: false``).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..verifier.certificate import certificate_digest, content_digest, manifest_digest
from .hashchain import verify_chain
from .ledger import EvidenceLedger


def verify_certificate(
    certificate: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    *,
    ledger: EvidenceLedger | None = None,
    expected_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}

    def record(name: str, ok: bool, detail: str = "") -> None:
        results[name] = {"ok": ok, "detail": detail}

    manifest = certificate.get("manifest") or {}
    claimed = certificate.get("evidence_manifest_sha256")
    record("manifest_digest", manifest_digest(dict(manifest)) == claimed)
    record("content_digest", content_digest(dict(certificate)) == manifest.get("content_sha256"))
    record(
        "identity",
        all(certificate.get(k) == manifest.get(k) for k in ("run_id", "template_id", "verdict")),
    )

    chain = verify_chain(events)
    record(
        "event_chain",
        chain.valid,
        "" if chain.valid else f"seq {chain.first_invalid_seq}: {chain.reason}",
    )
    through = manifest.get("events_through_seq")
    head = next((e for e in events if e.get("seq") == through), None)
    record(
        "chain_head",
        head is not None and head.get("event_hash") == manifest.get("event_chain_head"),
        f"events_through_seq={through}",
    )
    cert_sha = certificate_digest(dict(certificate))
    issued = [
        e["safe_payload"]
        for e in events
        if e.get("event_type") == "certificate.issued"
        and e.get("run_id") == certificate.get("run_id")
    ]
    record(
        "issued_event",
        any(
            p.get("manifest_sha256") == claimed and p.get("certificate_sha256") == cert_sha
            for p in issued
        ),
    )

    detached = False
    if ledger is not None and ledger.enabled:
        entries = ledger.find(str(certificate.get("run_id")))
        match = any(
            e.get("manifest_sha256") == claimed and e.get("certificate_sha256") == cert_sha
            for e in entries
        )
        record("detached_ledger", match, f"{len(entries)} ledger entries for run")
        detached = True
    if expected_manifest_sha256 is not None:
        record("expected_manifest", expected_manifest_sha256 == claimed)
        detached = True

    return {
        "run_id": certificate.get("run_id"),
        "verdict": certificate.get("verdict"),
        "certificate_sha256": cert_sha,
        "evidence_manifest_sha256": claimed,
        "valid": all(r["ok"] for r in results.values()),
        "detached": detached,
        "checks": results,
    }


def _fetch(url: str) -> Any:
    if not url.startswith(("http://", "https://")):
        raise ValueError("--api must be an http(s) URL")
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - scheme checked
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a ProofLayer certificate offline.")
    parser.add_argument("--certificate", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--api", help="API base URL, e.g. http://127.0.0.1:8000/api/v1")
    parser.add_argument("--run", help="run ID (with --api)")
    parser.add_argument("--ledger", type=Path, help="detached evidence ledger (JSON lines)")
    parser.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)

    if args.api:
        if not args.run:
            parser.error("--api needs --run")
        base = args.api.rstrip("/")
        certificate = _fetch(f"{base}/runs/{args.run}/certificate")
        events = _fetch(f"{base}/runs/{args.run}/events")
    elif args.certificate and args.events:
        certificate = json.loads(args.certificate.read_text(encoding="utf-8"))
        events = json.loads(args.events.read_text(encoding="utf-8"))
    else:
        parser.error("give --certificate and --events, or --api and --run")

    report = verify_certificate(
        certificate,
        events,
        ledger=EvidenceLedger(args.ledger) if args.ledger else None,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
