import inspect
import uuid

import pytest

from application.commands.analyze_food_photo import (
    AnalyzeFoodPhotoCommand,
    AnalyzeFoodPhotoHandler,
)
from application.errors import InvalidImageError
from domain.ports.vision_recognition_port import VisionRecognitionUnavailableError
from tests.fixtures.factories import (
    FakeOutboxRepository,
    FakePhotoAnalysisRepository,
    FakeVisionRecognitionPort,
    make_candidate,
)


def _command(image_bytes: bytes = b"fake-image-bytes") -> AnalyzeFoodPhotoCommand:
    return AnalyzeFoodPhotoCommand(
        user_id=uuid.uuid4(), image_bytes=image_bytes, correlation_id="corr-1"
    )


async def test_confident_candidates_are_detected():
    vision = FakeVisionRecognitionPort(
        candidates_to_return=[
            make_candidate(name="apple", confidence=0.9),
            make_candidate(name="banana", confidence=0.8),
        ]
    )
    repository = FakePhotoAnalysisRepository()
    outbox = FakeOutboxRepository()
    handler = AnalyzeFoodPhotoHandler(vision, repository, outbox, confidence_threshold=0.6)

    result = await handler.handle(_command())

    assert result.status == "detected"
    assert [c.name for c in result.candidates] == ["apple", "banana"]
    assert result.model_version == "claude-haiku-4-5"
    assert len(repository.saved) == 1
    assert repository.saved[0].status == "detected"
    assert len(outbox.enqueued) == 1
    assert outbox.enqueued[0].payload["status"] == "detected"
    assert outbox.enqueued[0].payload["analysis_id"] == str(result.analysis_id)


async def test_all_candidates_below_threshold_is_uncertain():
    vision = FakeVisionRecognitionPort(
        candidates_to_return=[
            make_candidate(name="apple", confidence=0.3),
            make_candidate(name="banana", confidence=0.4),
        ]
    )
    repository = FakePhotoAnalysisRepository()
    outbox = FakeOutboxRepository()
    handler = AnalyzeFoodPhotoHandler(vision, repository, outbox, confidence_threshold=0.6)

    result = await handler.handle(_command())

    assert result.status == "uncertain"
    assert len(result.candidates) == 2  # never discarded
    assert repository.saved[0].status == "uncertain"
    assert outbox.enqueued[0].payload["status"] == "uncertain"
    assert len(outbox.enqueued[0].payload["candidates"]) == 2


async def test_provider_failure_is_unavailable_with_no_exception():
    vision = FakeVisionRecognitionPort(
        error_to_raise=VisionRecognitionUnavailableError("circuit open")
    )
    repository = FakePhotoAnalysisRepository()
    outbox = FakeOutboxRepository()
    handler = AnalyzeFoodPhotoHandler(vision, repository, outbox, confidence_threshold=0.6)

    result = await handler.handle(_command())

    assert result.status == "unavailable"
    assert result.candidates == []
    assert repository.saved[0].status == "unavailable"
    assert repository.saved[0].candidates == []
    assert outbox.enqueued[0].payload["status"] == "unavailable"
    assert outbox.enqueued[0].payload["candidates"] == []


async def test_unparseable_provider_output_is_treated_as_unavailable():
    # A malformed-JSON response is caught by the adapter and re-raised as
    # VisionRecognitionUnavailableError before it ever reaches this
    # handler (implementation plan section 4) -- from the handler's
    # perspective this is indistinguishable from any other provider
    # failure.
    vision = FakeVisionRecognitionPort(
        error_to_raise=VisionRecognitionUnavailableError("malformed JSON")
    )
    repository = FakePhotoAnalysisRepository()
    outbox = FakeOutboxRepository()
    handler = AnalyzeFoodPhotoHandler(vision, repository, outbox, confidence_threshold=0.6)

    result = await handler.handle(_command())

    assert result.status == "unavailable"


async def test_feature_flag_disabled_short_circuits_without_calling_provider():
    vision = FakeVisionRecognitionPort(candidates_to_return=[make_candidate()])
    repository = FakePhotoAnalysisRepository()
    outbox = FakeOutboxRepository()
    handler = AnalyzeFoodPhotoHandler(
        vision, repository, outbox, confidence_threshold=0.6, feature_enabled=False
    )

    result = await handler.handle(_command())

    assert result.status == "unavailable"
    assert vision.call_count == 0  # never invokes the metered API while disabled
    assert outbox.enqueued[0].payload["status"] == "unavailable"


async def test_empty_image_raises_invalid_image_error():
    vision = FakeVisionRecognitionPort(candidates_to_return=[make_candidate()])
    handler = AnalyzeFoodPhotoHandler(vision, FakePhotoAnalysisRepository(), FakeOutboxRepository())
    with pytest.raises(InvalidImageError):
        await handler.handle(_command(image_bytes=b""))


async def test_at_most_three_candidates_are_ever_returned():
    vision = FakeVisionRecognitionPort(
        candidates_to_return=[
            make_candidate(name="a", confidence=0.9),
            make_candidate(name="b", confidence=0.8),
            make_candidate(name="c", confidence=0.7),
            make_candidate(name="d", confidence=0.65),
        ]
    )
    handler = AnalyzeFoodPhotoHandler(
        vision, FakePhotoAnalysisRepository(), FakeOutboxRepository(), confidence_threshold=0.6
    )
    result = await handler.handle(_command())
    assert len(result.candidates) == 3


def test_constructor_never_accepts_a_diary_service_port():
    """Structural assertion (test-plan section 1): this handler's only
    side effects are its own repository write and its own outbox publish
    -- no diary-service client/port parameter exists on the constructor
    at all."""
    params = inspect.signature(AnalyzeFoodPhotoHandler.__init__).parameters
    assert not any("diary" in name.lower() for name in params)
