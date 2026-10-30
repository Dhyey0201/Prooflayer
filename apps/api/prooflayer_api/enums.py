"""Core typed enums. Values mirror ``contracts/openapi.yaml`` (checked by tests)."""

from enum import StrEnum


class TemplateId(StrEnum):
    SUCCESS_VALIDATION = "success-validation"
    FALSE_SUCCESS_AUTH = "false-success-auth"
    DENIED_SECRET_READ = "denied-secret-read"  # noqa: S105 - fixture ID, not a secret


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    CANCELED = "canceled"
    ERROR = "error"


class RunMode(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"
    REPLAY = "replay"


class Verdict(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class CheckOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - check outcome, not a password
    FAIL = "FAIL"
    # Missing or unmeasurable evidence; never promoted to PASS.
    INCONCLUSIVE = "INCONCLUSIVE"


class EventType(StrEnum):
    RUN_CREATED = "run.created"
    RUN_STATUS_CHANGED = "run.status_changed"
    SANDBOX_PROVISIONED = "sandbox.provisioned"
    SANDBOX_RELEASED = "sandbox.released"
    MODEL_CALLED = "model.called"
    AGENT_ACTION_PROPOSED = "agent.action_proposed"
    TOOL_RESULT = "tool.result"
    POLICY_DENIED = "policy.denied"
    AGENT_CLAIMED = "agent.claimed"
    AGENT_FINISHED = "agent.finished"
    WORKSPACE_SNAPSHOT = "workspace.snapshot"
    CHECK_COMPLETED = "check.completed"
    CERTIFICATE_ISSUED = "certificate.issued"
    CHALLENGE_REQUESTED = "challenge.requested"
    CHALLENGE_PROPOSED = "challenge.proposed"
    CHALLENGE_REJECTED = "challenge.rejected"
    CHALLENGE_COMPLETED = "challenge.completed"


class Actor(StrEnum):
    """Who wrote an event. The agent never appears here: it cannot write evidence."""

    API = "api"
    ORCHESTRATOR = "orchestrator"
    SEEDER = "seeder"
    # The independent verifier: writes check results and certificates only.
    VERIFIER = "verifier"


class ChallengeStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    # A validated test was executed; ``outcome`` holds its measured result.
    COMPLETED = "completed"
    # The proposal failed validation and was never executed.
    REJECTED = "rejected"
    ERROR = "error"


class ErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    VALIDATION_ERROR = "validation_error"
    READ_ONLY = "read_only"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
