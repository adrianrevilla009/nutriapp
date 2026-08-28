import uuid
from datetime import datetime, timezone

from domain.events.food_photo_analyzed import build_food_photo_analyzed_event
from domain.value_objects.confidence_score import ConfidenceScore
from domain.value_objects.food_candidate import FoodCandidate
from domain.value_objects.portion_range_grams import PortionRangeGrams


def test_event_payload_shape():
    analysis_id = uuid.uuid4()
    user_id = uuid.uuid4()
    occurred_at = datetime.now(timezone.utc)
    candidate = FoodCandidate(
        name="apple",
        portion_range=PortionRangeGrams(min_g=100, max_g=150),
        confidence=ConfidenceScore(0.9),
    )
    event = build_food_photo_analyzed_event(
        analysis_id=analysis_id,
        user_id=user_id,
        candidates=[candidate],
        model_version="claude-haiku-4-5",
        status="detected",
        correlation_id="corr-1",
        occurred_at=occurred_at,
    )

    assert event.event_type == "FoodPhotoAnalyzed"
    assert event.version == 1
    assert event.aggregate_id == str(analysis_id)
    assert event.occurred_at == occurred_at
    assert event.metadata.user_id == str(user_id)
    assert event.metadata.correlation_id == "corr-1"
    assert event.payload == {
        "analysis_id": str(analysis_id),
        "candidates": [
            {
                "name": "apple",
                "portion_range_min_g": 100,
                "portion_range_max_g": 150,
                "confidence": 0.9,
            }
        ],
        "model_version": "claude-haiku-4-5",
        "status": "detected",
    }


def test_event_payload_with_no_candidates():
    event = build_food_photo_analyzed_event(
        analysis_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        candidates=[],
        model_version="claude-haiku-4-5",
        status="unavailable",
        correlation_id="corr-2",
        occurred_at=datetime.now(timezone.utc),
    )
    assert event.payload["candidates"] == []
    assert event.payload["status"] == "unavailable"
