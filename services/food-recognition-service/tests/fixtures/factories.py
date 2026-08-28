"""Fake port implementations and small builders shared across the test
suite (testing-strategy SKILL.md: unit tests exercise handlers against
fake ports, never real infrastructure)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from domain.entities.barcode_lookup import BarcodeLookup
from domain.entities.photo_analysis import PhotoAnalysis
from domain.events.base import DomainEvent
from domain.value_objects.barcode import Barcode
from domain.value_objects.catalog_product import CatalogProduct
from domain.value_objects.confidence_score import ConfidenceScore
from domain.value_objects.food_candidate import FoodCandidate
from domain.value_objects.portion_range_grams import PortionRangeGrams


def make_candidate(
    name: str = "apple", min_g: float = 100.0, max_g: float = 150.0, confidence: float = 0.9
) -> FoodCandidate:
    return FoodCandidate(
        name=name,
        portion_range=PortionRangeGrams(min_g=min_g, max_g=max_g),
        confidence=ConfidenceScore(confidence),
    )


def make_catalog_product(product_id: uuid.UUID | None = None) -> CatalogProduct:
    return CatalogProduct(
        product_id=product_id or uuid.uuid4(),
        barcode="4006381333931",
        name="Test Product",
        brand="Test Brand",
        category="snacks",
        nutrition_per_100g=None,
        dietary_tags=[],
        allergen_tags=[],
        package_size=None,
        price=None,
    )


@dataclass
class FakeVisionRecognitionPort:
    """Implements domain.ports.vision_recognition_port.VisionRecognitionPort."""

    candidates_to_return: list[FoodCandidate] = field(default_factory=list)
    error_to_raise: Exception | None = None
    version: str = "claude-haiku-4-5"
    call_count: int = 0

    @property
    def model_version(self) -> str:
        return self.version

    async def analyze(self, image_bytes: bytes) -> list[FoodCandidate]:
        self.call_count += 1
        if self.error_to_raise is not None:
            raise self.error_to_raise
        return self.candidates_to_return


@dataclass
class FakePhotoAnalysisRepository:
    """Implements domain.ports.photo_analysis_repository_port.PhotoAnalysisRepositoryPort."""

    saved: list[PhotoAnalysis] = field(default_factory=list)

    async def save(self, analysis: PhotoAnalysis) -> None:
        self.saved.append(analysis)


@dataclass
class FakeBarcodeLookupRepository:
    """Implements domain.ports.barcode_lookup_repository_port.BarcodeLookupRepositoryPort."""

    saved: list[BarcodeLookup] = field(default_factory=list)

    async def save(self, lookup: BarcodeLookup) -> None:
        self.saved.append(lookup)


@dataclass
class FakeOutboxRepository:
    """Implements domain.ports.outbox_repository_port.OutboxRepositoryPort."""

    enqueued: list[DomainEvent] = field(default_factory=list)

    async def enqueue(self, event: DomainEvent) -> None:
        self.enqueued.append(event)

    async def fetch_unpublished(self, limit: int = 100) -> list[DomainEvent]:
        return list(self.enqueued)[:limit]

    async def mark_published(self, event_id: uuid.UUID) -> None:
        return None


@dataclass
class FakeBarcodeDecoderPort:
    """Implements domain.ports.barcode_decoder_port.BarcodeDecoderPort."""

    barcode_to_return: Barcode | None = None
    call_count: int = 0

    def decode(self, image_bytes: bytes) -> Barcode | None:
        self.call_count += 1
        return self.barcode_to_return


@dataclass
class FakeCatalogLookupPort:
    """Implements domain.ports.catalog_lookup_port.CatalogLookupPort."""

    product_to_return: CatalogProduct | None = None
    error_to_raise: Exception | None = None
    call_count: int = 0

    async def lookup_by_barcode(self, barcode: Barcode) -> CatalogProduct | None:
        self.call_count += 1
        if self.error_to_raise is not None:
            raise self.error_to_raise
        return self.product_to_return
