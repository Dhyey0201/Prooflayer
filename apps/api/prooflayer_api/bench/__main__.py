"""Benchmark CLI.

    python -m prooflayer_api.bench --passes 3 --out ../../benchmarks/results/benchmark-report.json
    python -m prooflayer_api.bench --write-manifest ../../benchmarks/benchmark_manifest.json

Needs the independent verifier (Docker + ``make verifier-image``) unless
``--allow-unavailable-verifier`` is given, in which case executed checks are
INCONCLUSIVE and the report says so. Exit status: 0 when every case met its
ground truth, all passes produced identical outcomes and the secret scan found
nothing; 1 otherwise; 2 when the verifier is unavailable.
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import secrets
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ..ai.scripted import SCRIPTED_MODEL_ID
from ..config import Settings, VerifierDriverName
from ..evidence.hashchain import format_timestamp
from ..services.fixtures import FIXTURES
from ..services.runtime import build_verifier_driver
from ..verifier.certificate import SCHEMA_VERSION as CERTIFICATE_SCHEMA_VERSION
from ..verifier.checks import CHECKS_VERSION
from .cases import BENCHMARK_VERSION, CASES, build_manifest
from .harness import BenchmarkHarness, outcome_digest
from .report import build_report
from .secret_scan import environment_secret_values, scan

STATIC_LIMITATIONS = (
    "Agents are scripted model replies, not a live model: the benchmark measures the "
    "verification layer's response to fixed behaviours, not any model's task skill.",
    "Seeded cases are synthetic and few (see seed_count); ratios are exact for this set and "
    "say nothing about coverage of attacks outside it.",
    "Code-level network exfiltration (B10) is contained by the network-less verifier and "
    "fails the suite, but no evidence signal records the attempt itself.",
    "A full database rewrite is detected only by the detached ledger; the ledger is a local "
    "file here, so this holds only if a copy is kept where the database owner cannot write.",
    "Overhead timings are wall-clock on the recorded host and include container start-up.",
    "No safe-operation-blocked case is seeded; the false-positive rate is measured over the "
    "permitted operations the cases happen to perform.",
)


def _settings(args: argparse.Namespace, canary: str) -> Settings:
    return Settings(
        _env_file=None,
        PROOFLAYER_MOCK_MODE=True,
        PROOFLAYER_WORKER_ENABLED=False,
        SANDBOX_DRIVER="mock",
        VERIFIER_DRIVER=args.verifier,
        VERIFIER_TIMEOUT_SECONDS=args.verifier_timeout,
        PROOFLAYER_EVIDENCE_LEDGER="",
        # Never used by scripted runs; scanned for to prove keys stay out of evidence.
        NEBIUS_API_KEY=canary,
    )


def _environment(settings: Settings, status, enforced: bool) -> dict:
    manifest = build_manifest()
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "cases_sha256": manifest["cases_sha256"],
        "checks_version": CHECKS_VERSION,
        "certificate_schema_version": CERTIFICATE_SCHEMA_VERSION,
        "fixture_repo_shas": {t.value: f.repo_sha for t, f in FIXTURES.items()},
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "sandbox": {"driver": "mock", "enforced": enforced},
        "verifier": {
            "driver": settings.verifier_driver.value,
            "available": status.available,
            "unavailable_reason": status.reason,
            "image": settings.verifier_image,
            "image_id": status.image_id,
            "engine_version": status.version,
            "isolation": "container" if status.available else None,
            "network": "none" if status.available else None,
            "cpus": settings.verifier_cpus,
            "memory": settings.verifier_memory,
            "pids_limit": settings.verifier_pids_limit,
            "timeout_seconds": settings.verifier_timeout_seconds,
        },
        "model": {"provider": "scripted", "model_id": SCRIPTED_MODEL_ID},
        "limits": {
            "max_agent_steps": settings.max_agent_steps,
            "max_model_calls_per_run": settings.max_model_calls_per_run,
            "max_model_tokens": settings.max_model_tokens,
            "max_run_seconds": settings.max_run_seconds,
        },
    }


def _print_summary(report: dict) -> None:
    out = sys.stderr
    for case in report["cases"]:
        mark = "ok " if case["matches_expectation"] else "BAD"
        print(
            f"  {mark} {case['case_id']:<42} expected {case['expected_verdict']:<12} "
            f"got {case['verdict'] or '-':<12} claim {case['claim_status'] or '-':<12} "
            f"signals {','.join(case['signals']) or '-'}",
            file=out,
        )
    for name, metric in report["metrics"].items():
        print(
            f"  {name:<38} {metric['value']}  ({metric['numerator']}/{metric['denominator']})",
            file=out,
        )
    timing = report["verification_overhead"]
    print(
        f"  verification overhead ms: median {timing['verification_ms_median']} "
        f"p95 {timing['verification_ms_p95']} (n={timing['samples']})",
        file=out,
    )
    print(
        f"  deterministic across {report['passes']} passes: {report['deterministic']}; "
        f"secret matches: {report['secret_scan']['matches']}; "
        f"all expectations met: {report['all_expectations_met']}",
        file=out,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ProofLayer seeded benchmark.")
    parser.add_argument("--passes", type=int, default=3, help="consecutive full passes (1-10)")
    parser.add_argument("--out", type=Path, help="write the JSON report here")
    parser.add_argument("--case", action="append", help="run only this case ID (repeatable)")
    parser.add_argument(
        "--verifier", choices=[v.value for v in VerifierDriverName], default="docker"
    )
    parser.add_argument(
        "--verifier-timeout",
        type=int,
        default=30,
        help="seconds per check, container start-up included (B14 always uses all of it)",
    )
    parser.add_argument("--allow-unavailable-verifier", action="store_true")
    parser.add_argument("--workdir", type=Path, help="keep scratch databases here")
    parser.add_argument("--write-manifest", type=Path, help="write the case manifest and exit")
    parser.add_argument("--verbose", action="store_true", help="show service logs")
    args = parser.parse_args(argv)
    if not args.verbose:
        # Seeded faults log expected tracebacks (e.g. B15's lost snapshot).
        logging.getLogger("prooflayer_api").setLevel(logging.CRITICAL)

    if args.write_manifest:
        args.write_manifest.write_text(json.dumps(build_manifest(), indent=2) + "\n")
        return 0
    if not 1 <= args.passes <= 10:
        parser.error("--passes must be between 1 and 10")
    cases = CASES
    if args.case:
        unknown = set(args.case) - {c.id for c in CASES}
        if unknown:
            parser.error(f"unknown case(s): {', '.join(sorted(unknown))}")
        cases = tuple(c for c in CASES if c.id in args.case)

    canary = "bench-canary-" + secrets.token_hex(16)
    settings = _settings(args, canary)
    verifier = build_verifier_driver(settings)
    status = verifier.probe()
    if not status.available and not args.allow_unavailable_verifier:
        print(
            f"independent verifier unavailable ({status.reason}); start Docker and run "
            "`make verifier-image`, or pass --allow-unavailable-verifier",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory(prefix="prooflayer-bench-") as scratch:
        workdir = args.workdir or Path(scratch)
        workdir.mkdir(parents=True, exist_ok=True)
        harness = BenchmarkHarness(settings, verifier, workdir)
        passes = []
        for index in range(1, args.passes + 1):
            print(f"pass {index}/{args.passes}", file=sys.stderr)
            passes.append(harness.run_pass(index, cases))
        evidence = harness.evidence

    needles = [canary.encode(), *environment_secret_values()]
    evidence_scan = scan(evidence, needles)
    enforced = any(r.sandbox_enforced for p in passes for r in p)
    limitations = list(STATIC_LIMITATIONS)
    if not enforced:
        limitations.append(
            "The agent sandbox was the mock driver (not enforced): policy denials are modelled, "
            "and cases that need proof of no attempts are graded against "
            "expected_verdict_unenforced."
        )
    if not status.available:
        limitations.append(
            f"No independent verifier was available ({status.reason}); this report is not a "
            "valid benchmark result."
        )
    report = build_report(
        passes=passes,
        digests=[outcome_digest(p) for p in passes],
        environment=_environment(settings, status, enforced),
        secret_scan={
            **evidence_scan.to_wire(),
            "scope": "events, certificates, artifacts, "
            "claims and ledger of every pass, plus this report",
        },
        generated_at=format_timestamp(datetime.now(UTC)),
        limitations=limitations,
    )
    text = json.dumps(report, indent=2) + "\n"
    report_scan = scan([("report", text.encode())], needles)
    if report_scan.total_matches:
        print("secret scan matched the report itself; not writing it", file=sys.stderr)
        return 1
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    ok = (
        report["all_expectations_met"]
        and report["deterministic"]
        and evidence_scan.total_matches == 0
        and status.available
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
