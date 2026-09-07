"""AnswerChatQueryHandler -- the core RAG orchestration: retrieval +
prompt assembly + generation, per .claude/agents/nutrition-assistant-agent.md
("retrieval-augmented prompt assembly... response generation that is
explicit about the limits of what it retrieved").

This is the ONLY place VectorStorePort/ConversationPort/EmbeddingPort/the
three structured-history ports/EntitlementCheckPort are all orchestrated
together -- pure orchestration, zero framework/HTTP/SDK-specific code
(hexagonal-architecture SKILL.md, .claude/agents/nutrition-assistant-agent.md's
"retrieval/prompt-assembly logic lives in the application layer").

CROSS-USER ISOLATION (implementation plan acceptance criterion 5, hard
boundary, never best-effort): every structured-history repository call
below is parameterized on `command.user_id` -- the user_id carried by the
verified JWT at the HTTP boundary, never anything derived from
`command.query`'s text. This handler never parses `command.query` looking
for a user reference; it is structurally incapable of retrieving another
user's data no matter what the query text says.

PROFESSIONAL-ADVICE BOUNDARY (CLAUDE.md section 8): the mandatory
disclaimer is enforced HERE, in code, not merely requested of the LLM via
the prompt -- if `health_topic_classifier.is_health_adjacent` flags the
query and the LLM's raw response does not literally contain the
disclaimer text, this handler appends it before returning. This is the
key "structural enforcement, not LLM-judgment-only" property flagged as a
first-cut, not-fully-solved risk in implementation plan section 9
resolution 4."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from application.entitlement_check import is_user_entitled
from application.errors import AssistantUnavailableError, NotEntitledError
from domain.ports.analytics_signals_repository_port import AnalyticsSignalsRepositoryPort
from domain.ports.chat_audit_repository_port import ChatAuditRepositoryPort
from domain.ports.conversation_port import ConversationPort, ConversationUnavailableError
from domain.ports.diary_history_repository_port import DiaryHistoryRepositoryPort
from domain.ports.embedding_port import EmbeddingPort
from domain.ports.entitlement_cache_repository_port import EntitlementCacheRepositoryPort
from domain.ports.entitlement_check_port import EntitlementCheckPort
from domain.ports.nutrition_history_repository_port import NutritionHistoryRepositoryPort
from domain.ports.vector_store_port import VectorStorePort, VectorStoreUnavailableError
from domain.services.health_topic_classifier import is_health_adjacent
from domain.services.prompt_assembler import assemble_prompt
from domain.value_objects.chat_message import ChatMessage
from domain.value_objects.disclaimer_flag import DisclaimerFlag
from domain.value_objects.grounded_context import GroundedContext
from domain.value_objects.retrieval_gap import RetrievalGap
from domain.value_objects.retrieved_record import RetrievedRecord

DEFAULT_KNOWLEDGE_BASE_COLLECTION = "nutrition_assistant_knowledge_base"
DEFAULT_TOP_K = 3


@dataclass(frozen=True, slots=True)
class AnswerChatQueryCommand:
    user_id: uuid.UUID
    query: str
    chat_history: tuple[ChatMessage, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AnswerChatQueryResult:
    response_text: str
    had_sufficient_context: bool
    disclaimer_included: bool
    retrieved_record_ids: list[str]


class AnswerChatQueryHandler:
    def __init__(
        self,
        entitlement_cache: EntitlementCacheRepositoryPort,
        entitlement_check: EntitlementCheckPort,
        diary_history: DiaryHistoryRepositoryPort,
        nutrition_history: NutritionHistoryRepositoryPort,
        analytics_signals: AnalyticsSignalsRepositoryPort,
        vector_store: VectorStorePort,
        embedding: EmbeddingPort,
        conversation: ConversationPort,
        chat_audit: ChatAuditRepositoryPort,
        knowledge_base_collection: str = DEFAULT_KNOWLEDGE_BASE_COLLECTION,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self._entitlement_cache = entitlement_cache
        self._entitlement_check = entitlement_check
        self._diary_history = diary_history
        self._nutrition_history = nutrition_history
        self._analytics_signals = analytics_signals
        self._vector_store = vector_store
        self._embedding = embedding
        self._conversation = conversation
        self._chat_audit = chat_audit
        self._kb_collection = knowledge_base_collection
        self._top_k = top_k

    async def _retrieve_structured_records(self, user_id: uuid.UUID) -> list[RetrievedRecord]:
        diary_records = await self._diary_history.recent_for_user(user_id)
        nutrition_records = await self._nutrition_history.recent_for_user(user_id)
        analytics_records = await self._analytics_signals.recent_for_user(user_id)
        return [*diary_records, *nutrition_records, *analytics_records]

    async def _retrieve_knowledge_base_records(
        self, query: str
    ) -> tuple[list[RetrievedRecord], bool]:
        """Returns (records, knowledge_base_unavailable). Falls back to an
        empty result (never a hard failure of the whole request) on a
        circuit-open/unavailable vector store, per implementation plan
        section 7's explicit fallback requirement."""
        try:
            query_vector = await self._embedding.embed(query)
            hits = await self._vector_store.search(self._kb_collection, query_vector, self._top_k)
        except VectorStoreUnavailableError:
            return [], True

        return [
            RetrievedRecord(
                record_id=hit.point_id,
                source="knowledge_base",
                content=hit.payload.get("content", ""),
            )
            for hit in hits
        ], False

    async def handle(self, command: AnswerChatQueryCommand) -> AnswerChatQueryResult:
        entitled = await is_user_entitled(
            command.user_id, self._entitlement_cache, self._entitlement_check
        )
        if not entitled:
            raise NotEntitledError(f"user {command.user_id} is not entitled to the chat feature.")

        # Cross-user isolation: `command.user_id` is the ONLY user identity
        # ever passed to a repository call in this method.
        structured_records = await self._retrieve_structured_records(command.user_id)
        kb_records, kb_unavailable = await self._retrieve_knowledge_base_records(command.query)

        all_records = (*structured_records, *kb_records)
        has_sufficient_context = len(all_records) > 0

        context = GroundedContext(
            records=all_records,
            has_sufficient_context=has_sufficient_context,
            knowledge_base_unavailable=kb_unavailable,
        )
        retrieval_gap = RetrievalGap(
            insufficient_user_data=not has_sufficient_context,
            knowledge_base_unavailable=kb_unavailable,
        )

        is_health_topic = is_health_adjacent(command.query)
        disclaimer = DisclaimerFlag(required=is_health_topic)

        assembled = assemble_prompt(
            query=command.query,
            chat_history=command.chat_history,
            context=context,
            disclaimer=disclaimer,
            retrieval_gap=retrieval_gap,
        )

        try:
            raw_response = await self._conversation.generate(assembled.text)
        except ConversationUnavailableError as exc:
            raise AssistantUnavailableError(
                "The assistant is temporarily unavailable. Please try again shortly."
            ) from exc

        response_text = raw_response
        # Structural enforcement -- never merely trust the LLM to have
        # included the disclaimer it was asked for.
        if disclaimer.required and disclaimer.text not in response_text:
            response_text = f"{response_text}\n\n{disclaimer.text}"
        disclaimer_included = (not disclaimer.required) or (disclaimer.text in response_text)

        if retrieval_gap.has_gap:
            response_text = f"{response_text}\n\n{retrieval_gap.describe()}"

        retrieved_record_ids = [r.record_id for r in all_records]
        await self._chat_audit.record(
            user_id=command.user_id,
            query=command.query,
            retrieved_record_ids=retrieved_record_ids,
            prompt_template_version=assembled.template_version,
            had_sufficient_context=has_sufficient_context,
            disclaimer_included=disclaimer_included,
        )

        return AnswerChatQueryResult(
            response_text=response_text,
            had_sufficient_context=has_sufficient_context,
            disclaimer_included=disclaimer_included,
            retrieved_record_ids=retrieved_record_ids,
        )
