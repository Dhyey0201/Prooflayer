"""OpenShell sandbox policy for an agent workspace (schema ``version: 1``, OpenShell 0.1.x).

Generated from the trusted fixture template, never from run input:

* ``filesystem_policy`` is allow-only (Landlock). The repo is read-only, only the
  template's ``allowed_paths`` are writable, and ``/sandbox/secrets`` (the target
  of every read-denied symlink) is granted nowhere.
* ``landlock.compatibility: hard_requirement``: the sandbox fails to start rather
  than run without filesystem rules.
* ``process`` pins a non-root identity.
* No ``network_policies``: OpenShell denies all egress. The model is called by the
  orchestrator on the host, so the agent workspace needs no network.

Filesystem, Landlock and process settings are fixed at sandbox creation, so the
policy is passed to ``sandbox create --policy`` and never hot-reloaded.
"""

from __future__ import annotations

import hashlib
from typing import Any

import yaml

from ..services.fixtures import FixtureTemplate

REPO_DIR = "/sandbox/repo"
SECRETS_DIR = "/sandbox/secrets"
SANDBOX_UID = "10001"
SYSTEM_READ_ONLY = ("/bin", "/usr", "/lib", "/proc", "/dev/urandom", "/etc")
SYSTEM_READ_WRITE = ("/tmp", "/dev/null")  # noqa: S108 - sandbox-internal scratch path
MAX_POLICY_PATHS = 256


class PolicyError(ValueError):
    pass


def build_agent_policy(fixture: FixtureTemplate) -> dict[str, Any]:
    policy = {
        "version": 1,
        "filesystem_policy": {
            "include_workdir": False,
            "read_only": [*SYSTEM_READ_ONLY, REPO_DIR],
            "read_write": [*SYSTEM_READ_WRITE, *(f"{REPO_DIR}/{p}" for p in fixture.allowed_paths)],
        },
        "landlock": {"compatibility": "hard_requirement"},
        "process": {"run_as_user": SANDBOX_UID, "run_as_group": SANDBOX_UID},
    }
    validate_policy(policy)
    return policy


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def validate_policy(policy: dict[str, Any]) -> None:
    """OpenShell's documented path rules plus ProofLayer's own invariants."""
    fs = policy["filesystem_policy"]
    paths = [*fs["read_only"], *fs["read_write"]]
    if len(paths) > MAX_POLICY_PATHS:
        raise PolicyError("too many filesystem paths")
    for path in paths:
        if not path.startswith("/") or ".." in path.split("/") or len(path.encode()) > 4096:
            raise PolicyError(f"invalid policy path: {path}")
        # Nothing may grant the directory that holds read-denied targets.
        if _within(SECRETS_DIR, path) or _within(path, SECRETS_DIR):
            raise PolicyError(f"policy grants access to {SECRETS_DIR}: {path}")
    if "/" in fs["read_write"]:
        raise PolicyError("read_write cannot contain /")
    if fs.get("include_workdir") is not False:
        raise PolicyError("include_workdir must be false")
    if policy.get("network_policies"):
        raise PolicyError("agent sandbox policy must not allow network egress")
    if policy["landlock"]["compatibility"] != "hard_requirement":
        raise PolicyError("landlock must be a hard requirement")


def render_policy(policy: dict[str, Any]) -> str:
    return yaml.safe_dump(policy, sort_keys=False)


def policy_sha256(rendered: str) -> str:
    return hashlib.sha256(rendered.encode()).hexdigest()


if __name__ == "__main__":
    import sys

    from ..enums import TemplateId
    from ..services.fixtures import get_fixture

    template = TemplateId(sys.argv[1] if len(sys.argv) > 1 else TemplateId.DENIED_SECRET_READ)
    rendered = render_policy(build_agent_policy(get_fixture(template)))
    sys.stdout.write(f"# sha256: {policy_sha256(rendered)}\n{rendered}")
