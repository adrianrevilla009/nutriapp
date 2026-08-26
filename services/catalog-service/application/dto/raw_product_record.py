"""RawProductRecord — the shared intermediate shape all source adapters
produce (implementation plan section 3).

Re-exported here from `domain.services.product_normalizer` (its
canonical definition — normalization is a domain concern) so application-
layer modules (commands/jobs) can import it from this DTO module path
without the domain layer ever importing upward from application
(ADR-0001's dependency-direction rule).
"""

from __future__ import annotations

from domain.services.product_normalizer import RawProductRecord

__all__ = ["RawProductRecord"]
