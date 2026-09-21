"""Typed exceptions for JevKit.

Callers should be able to react to failures without string-matching. The tree is
deliberately shallow:

    JevKitError
    ├── ConfigurationError      - the SDK was set up wrong (no key, bad URL)
    ├── TaskDefinitionError     - the task/questions are invalid
    ├── InputValidationError    - the caller's `state` does not match the schema
    ├── ProviderError           - the provider failed
    │   ├── ProviderTimeoutError
    │   ├── ProviderAuthError
    │   ├── ProviderRateLimitError
    │   └── ProviderResponseError
    ├── OutputValidationError   - the provider replied, but the result is unusable
    └── PolicyError             - execution stopped because a policy said so
        ├── RetryLimitExceeded
        ├── FallbackExhausted
        └── ReviewRequired
"""

from __future__ import annotations

__all__ = [
    "ConfigurationError",
    "FallbackExhausted",
    "InputValidationError",
    "JevKitError",
    "OutputValidationError",
    "PolicyError",
    "ProviderAuthError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "RetryLimitExceeded",
    "ReviewRequired",
    "TaskDefinitionError",
]


class JevKitError(Exception):
    """Base class for every error raised by JevKit."""

    def __init__(self, message: str, *, trace_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.trace_id = trace_id


class ConfigurationError(JevKitError):
    """The SDK or service is misconfigured (missing key, invalid base URL)."""


class TaskDefinitionError(JevKitError):
    """A DecisionTask or its questions are internally inconsistent."""


class InputValidationError(JevKitError):
    """The supplied `state` does not satisfy the task's input schema."""


class ProviderError(JevKitError):
    """A provider call failed.

    `retryable` tells the policy engine whether re-sending the same request could
    plausibly succeed. Never retry on a non-retryable error (see PLAN.md §10).
    """

    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        status_code: int | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message, trace_id=trace_id)
        self.provider = provider
        self.status_code = status_code


class ProviderTimeoutError(ProviderError):
    """The provider did not respond within the configured timeout."""

    retryable = True


class ProviderAuthError(ProviderError):
    """Authentication or authorization against the provider failed."""

    retryable = False


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request because of rate or quota limits."""

    retryable = True

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class ProviderResponseError(ProviderError):
    """The provider replied, but the payload could not be parsed or normalized."""

    retryable = False


class OutputValidationError(JevKitError):
    """A normalized result failed validation against the task's questions."""

    def __init__(
        self, message: str, *, failures: list[str] | None = None, **kwargs: object
    ) -> None:
        super().__init__(message, **kwargs)  # type: ignore[arg-type]
        self.failures = failures or []


class PolicyError(JevKitError):
    """Execution was stopped by an explicit policy decision."""


class RetryLimitExceeded(PolicyError):
    """The configured retry budget was used up without an accepted result."""


class FallbackExhausted(PolicyError):
    """Every configured provider failed or produced an unacceptable result."""


class ReviewRequired(PolicyError):
    """The policy routed this decision to human review instead of returning it."""
