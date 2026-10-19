"""Run status state machine (docs/02_ARCHITECTURE_SECURITY.md).

created -> queued -> provisioning -> running -> verifying -> {verified, failed,
inconclusive}. Any active state may move to canceled or error. Terminal states
have no outgoing transitions.
"""

from __future__ import annotations

from ..enums import RunStatus, Verdict

ACTIVE_STATUSES = frozenset(
    {
        RunStatus.CREATED,
        RunStatus.QUEUED,
        RunStatus.PROVISIONING,
        RunStatus.RUNNING,
        RunStatus.VERIFYING,
    }
)
TERMINAL_STATUSES = frozenset(set(RunStatus) - ACTIVE_STATUSES)

_FORWARD: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset({RunStatus.QUEUED}),
    RunStatus.QUEUED: frozenset({RunStatus.PROVISIONING}),
    RunStatus.PROVISIONING: frozenset({RunStatus.RUNNING}),
    RunStatus.RUNNING: frozenset({RunStatus.VERIFYING}),
    RunStatus.VERIFYING: frozenset({RunStatus.VERIFIED, RunStatus.FAILED, RunStatus.INCONCLUSIVE}),
}

ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    status: _FORWARD.get(status, frozenset()) | {RunStatus.CANCELED, RunStatus.ERROR}
    if status in ACTIVE_STATUSES
    else frozenset()
    for status in RunStatus
}

# A verdict exists only once verification has concluded.
VERDICT_FOR_STATUS: dict[RunStatus, Verdict] = {
    RunStatus.VERIFIED: Verdict.VERIFIED,
    RunStatus.FAILED: Verdict.FAILED,
    RunStatus.INCONCLUSIVE: Verdict.INCONCLUSIVE,
}


class InvalidTransitionError(Exception):
    def __init__(self, current: RunStatus, target: RunStatus) -> None:
        super().__init__(f"cannot transition run from {current} to {target}")
        self.current = current
        self.target = target


def check_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
