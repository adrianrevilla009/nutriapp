"""Application-layer typed errors -- mapped to HTTP responses in
infrastructure/http/error_mapping.py. Domain-layer errors
(`domain.entities.follow.SelfFollowError`,
`domain.value_objects.feed_entry.InvalidFeedEntryError`,
`domain.ports.entitlement_check_port.EntitlementCheckUnavailableError`)
are mapped directly there too, without being wrapped a second time here
(mirrors recipe-service's identical convention)."""

from __future__ import annotations


class NotEntitledError(Exception):
    """Raised when the caller is not Pro-entitled for a follow/unfollow/
    feed request -- rejected explicitly, never silently degraded
    (social-agent.md, CLAUDE.md section 2.2)."""
