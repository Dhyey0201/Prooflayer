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


class ErrorCode(StrEnum):
    BAD_REQUEST = "bad_request"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
