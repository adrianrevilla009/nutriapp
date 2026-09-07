from __future__ import annotations

import uuid

from sqlalchemy import select

from infrastructure.persistence.models import ChatAuditLogModel
from infrastructure.persistence.postgres_chat_audit_repository import PostgresChatAuditRepository


async def test_record_writes_a_row(session_factory) -> None:
    user_id = uuid.uuid4()
    async with session_factory() as session:
        repo = PostgresChatAuditRepository(session)
        await repo.record(
            user_id=user_id,
            query="what did I eat",
            retrieved_record_ids=["a1", "b2"],
            prompt_template_version="v1",
            had_sufficient_context=True,
            disclaimer_included=False,
        )
        await session.commit()

    async with session_factory() as session:
        rows = (await session.execute(select(ChatAuditLogModel))).scalars().all()
        assert len(rows) == 1
        assert rows[0].user_id == user_id
        assert rows[0].retrieved_record_ids == ["a1", "b2"]


async def test_no_read_method_exists_on_the_port() -> None:
    # Structural guard: ChatAuditRepositoryPort intentionally has no
    # read/list method (implementation plan section 9 resolution 6).
    assert not hasattr(PostgresChatAuditRepository, "list_for_user")
    assert not hasattr(PostgresChatAuditRepository, "get")
