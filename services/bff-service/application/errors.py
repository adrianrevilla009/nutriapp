"""Application-layer exceptions.

Deliberately empty beyond this docstring: `GetDashboardHandler` never
raises -- every downstream failure is captured (`asyncio.gather(...,
return_exceptions=True)`) and mapped to a degraded `SectionStatus`
section instead (implementation plan section 1 acceptance criterion 2).
Kept as its own module (rather than omitted) to match every other
service's file layout and as the natural home for a future application-
layer exception, should one become genuinely necessary.
"""

from __future__ import annotations
