"""Application-layer error types -- orchestration failures that aren't
domain invariant violations."""

from __future__ import annotations


class SubscriptionAlreadyActiveError(Exception):
    """Raised when a user with an already-active subscription attempts to
    start a second, concurrent one (test-plan section 1: "never a second
    concurrent subscription for the same user"). Mapped to HTTP 409."""


class SubscriptionNotFoundError(LookupError):
    """Raised when a webhook references a `stripe_subscription_id` this
    service has no matching record for -- never silently swallowed
    (test-plan section 1)."""


class InvalidCallerCredentialError(Exception):
    """Raised when an internal-service caller's
    `X-Internal-Service-Credential` header doesn't match the configured
    value -- mapped to HTTP 401, mirrors every other service's internal-
    route precedent (identity-service/catalog-service)."""


# Note: webhook signature failures are raised as
# domain.ports.payment_provider_port.WebhookSignatureVerificationError
# directly by the port/adapter (not duplicated as a separate
# application-layer type) -- infrastructure/http/error_mapping.py maps
# that domain-port error type to HTTP 401 directly.
