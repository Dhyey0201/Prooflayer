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
]
for relative in required:
    assert (root / relative).exists(), relative
print("ProofLayer handoff package validated:", len(manifest["fixtures"]), "seed fixtures")
