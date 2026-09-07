from __future__ import annotations

import uuid

import pytest

from application.commands.handle_nutrient_deficiency_detected import (
    HandleNutrientDeficiencyDetectedCommand,
    HandleNutrientDeficiencyDetectedHandler,
)
from tests.fixtures.fakes import FakeAnalyticsSignalsRepository, FakeProcessedEventsRepository


@pytest.fixture
def handler():
    processed = FakeProcessedEventsRepository()
    analytics_signals = FakeAnalyticsSignalsRepository()
    return HandleNutrientDeficiencyDetectedHandler(processed, analytics_signals), analytics_signals


async def test_disclaimer_preserved_verbatim(handler) -> None:
    h, analytics_signals = handler
    disclaimer_text = "This is not a medical diagnosis, consult a professional."
    await h.handle(
        HandleNutrientDeficiencyDetectedCommand(
            event_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            signal="protein_g",
            summary="protein below target for 5 of last 7 days",
            disclaimer=disclaimer_text,
        )
    )
    assert analytics_signals.upsert_calls[0][3] == disclaimer_text  # byte-for-byte, untouched


async def test_idempotent_replay(handler) -> None:
    h, analytics_signals = handler
    event_id = uuid.uuid4()
    command = HandleNutrientDeficiencyDetectedCommand(
        event_id=event_id,
        user_id=uuid.uuid4(),
        signal="protein_g",
        summary="x",
        disclaimer="not a medical diagnosis",
    )
    await h.handle(command)
    await h.handle(command)
    assert len(analytics_signals.upsert_calls) == 1
