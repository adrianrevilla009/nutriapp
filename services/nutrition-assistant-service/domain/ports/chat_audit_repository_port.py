"""ChatAuditRepositoryPort -- write-only traceability log (rag-conventions
SKILL.md "track which retrieved records backed each response, so a bad
answer can be traced back to a retrieval or generation failure"). NOT a
queryable conversation-resume feature (implementation plan section 9
resolution 6) -- write path only, no read/list method on this port.

`health_adjacent_flagged` (added 2026-09-12, implementation plan
addendum, same date -- security-review operational mitigation): records
whether `health_topic_classifier.is_health_adjacent` flagged the query,
independent of whether a disclaimer ended up in the response. This is a
logging-only addition for future manual drift review of the rule-based
classifier's precision/recall -- it introduces no new retrieval or
LLM-trust logic."""

from __future__ import annotations

import uuid
from typing import Protocol


class ChatAuditRepositoryPort(Protocol):
    async def record(
        self,
        user_id: uuid.UUID,
        query: str,
        retrieved_record_ids: list[str],
        prompt_template_version: str,
        had_sufficient_context: bool,
        disclaimer_included: bool,
        health_adjacent_flagged: bool,
    ) -> None: ...
