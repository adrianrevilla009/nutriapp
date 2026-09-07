"""Test plan section 1 -- value-object construction guards."""

from __future__ import annotations

import pytest

from domain.value_objects.chat_message import ChatMessage, InvalidChatMessageError
from domain.value_objects.disclaimer_flag import DisclaimerFlag, InvalidDisclaimerFlagError
from domain.value_objects.grounded_context import GroundedContext
from domain.value_objects.retrieved_record import InvalidRetrievedRecordError, RetrievedRecord


class TestChatMessage:
    def test_valid_message_constructs(self) -> None:
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_empty_role_rejected(self) -> None:
        with pytest.raises(InvalidChatMessageError):
            ChatMessage(role="", content="hello")

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(InvalidChatMessageError):
            ChatMessage(role="user", content="   ")

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(InvalidChatMessageError):
            ChatMessage(role="system", content="hello")


class TestRetrievedRecord:
    def test_valid_diary_record(self) -> None:
        record = RetrievedRecord(record_id="r1", source="diary", content="ate an apple")
        assert record.is_user_specific is True

    def test_knowledge_base_record_is_not_user_specific(self) -> None:
        record = RetrievedRecord(record_id="kb1", source="knowledge_base", content="fiber info")
        assert record.is_user_specific is False

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(InvalidRetrievedRecordError):
            RetrievedRecord(record_id="r1", source="bogus", content="x")

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(InvalidRetrievedRecordError):
            RetrievedRecord(record_id="r1", source="diary", content="")

    def test_empty_record_id_rejected(self) -> None:
        with pytest.raises(InvalidRetrievedRecordError):
            RetrievedRecord(record_id="", source="diary", content="x")


class TestGroundedContext:
    def test_requires_explicit_has_sufficient_context(self) -> None:
        # No default value exists for has_sufficient_context -- omitting it
        # is a TypeError, not a silently-assumed True/False.
        with pytest.raises(TypeError):
            GroundedContext(records=())  # type: ignore[call-arg]

    def test_empty_records_with_explicit_false(self) -> None:
        context = GroundedContext(records=(), has_sufficient_context=False)
        assert context.has_sufficient_context is False
        assert context.user_data_records == ()
        assert context.general_guidance_records == ()

    def test_splits_user_data_and_general_guidance(self) -> None:
        records = (
            RetrievedRecord(record_id="d1", source="diary", content="ate rice"),
            RetrievedRecord(record_id="kb1", source="knowledge_base", content="fiber info"),
        )
        context = GroundedContext(records=records, has_sufficient_context=True)
        assert len(context.user_data_records) == 1
        assert context.user_data_records[0].record_id == "d1"
        assert len(context.general_guidance_records) == 1
        assert context.general_guidance_records[0].record_id == "kb1"


class TestDisclaimerFlag:
    def test_not_required_allows_empty_text_override(self) -> None:
        flag = DisclaimerFlag(required=False, text="")
        assert flag.required is False

    def test_required_with_empty_text_rejected(self) -> None:
        with pytest.raises(InvalidDisclaimerFlagError):
            DisclaimerFlag(required=True, text="")

    def test_required_uses_default_disclaimer_text(self) -> None:
        flag = DisclaimerFlag(required=True)
        assert "qualified" in flag.text.lower()
