from __future__ import annotations

from itertools import pairwise

import pytest

from prooflayer_api.enums import RunStatus as S
from prooflayer_api.enums import Verdict
from prooflayer_api.services.state_machine import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    VERDICT_FOR_STATUS,
    InvalidTransitionError,
    check_transition,
)

HAPPY_PATH = [S.CREATED, S.QUEUED, S.PROVISIONING, S.RUNNING, S.VERIFYING]


def test_happy_path_is_allowed() -> None:
    for current, target in pairwise(HAPPY_PATH):
        check_transition(current, target)
    for outcome in (S.VERIFIED, S.FAILED, S.INCONCLUSIVE):
        check_transition(S.VERIFYING, outcome)


@pytest.mark.parametrize("active", HAPPY_PATH)
def test_any_active_state_can_cancel_or_error(active: S) -> None:
    check_transition(active, S.CANCELED)
    check_transition(active, S.ERROR)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.QUEUED, S.VERIFIED),
        (S.CREATED, S.RUNNING),
        (S.RUNNING, S.FAILED),
        (S.QUEUED, S.CREATED),
        (S.VERIFIED, S.RUNNING),
        (S.CANCELED, S.QUEUED),
        (S.FAILED, S.VERIFIED),
        (S.QUEUED, S.QUEUED),
    ],
)
def test_forbidden_transitions_are_rejected(current: S, target: S) -> None:
    with pytest.raises(InvalidTransitionError):
        check_transition(current, target)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert {S.VERIFIED, S.FAILED, S.INCONCLUSIVE, S.CANCELED, S.ERROR} == TERMINAL_STATUSES
    for status in TERMINAL_STATUSES:
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_only_concluded_verification_has_a_verdict() -> None:
    assert VERDICT_FOR_STATUS == {
        S.VERIFIED: Verdict.VERIFIED,
        S.FAILED: Verdict.FAILED,
        S.INCONCLUSIVE: Verdict.INCONCLUSIVE,
    }
