import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "benchmarks/fixture_manifest.json").read_text())
assert len(manifest["fixtures"]) >= 3
required = [
    "README.md",
    "LICENSE",
    "contracts/openapi.yaml",
    "contracts/schemas.json",
    "docs/03_SEVEN_DAY_COMMIT_PLAN.md",
    "docs/PROGRESS_LOG.md",
    "docs/07_BENCHMARK_LIMITATIONS.md",
    "benchmarks/benchmark_manifest.json",
    "benchmarks/results/benchmark-report.json",
]
for relative in required:
    assert (root / relative).exists(), relative
bench = json.loads((root / "benchmarks/benchmark_manifest.json").read_text())
assert 12 <= len(bench["cases"]) <= 20, len(bench["cases"])
report = json.loads((root / "benchmarks/results/benchmark-report.json").read_text())
assert report["environment"]["cases_sha256"] == bench["cases_sha256"], "stale benchmark report"
print(
    "ProofLayer handoff package validated:",
    len(manifest["fixtures"]),
    "seed fixtures,",
    len(bench["cases"]),
    "benchmark cases",
)
