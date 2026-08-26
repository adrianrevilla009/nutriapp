"""Typed event payload shapes published by catalog-service.

Data shapes only — no business logic (monorepo-tooling SKILL.md). Any
consuming service (diary-service, food-recognition-service,
recipe-service — documented in docs/events-catalog.md, none live yet) may
use these for deserialization/validation, but must never import
catalog-service's internal code directly.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PackageSizePayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str


class ProductCataloguedPayloadV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    barcode: str | None
    name: str | None
    brand: str | None
    category: str | None
    nutrition_per_100g: dict | None
    dietary_tags: list[str]
    allergen_tags: list[str]
    package_size: PackageSizePayloadV1 | None
    sources: list[str]
    catalogued_at: datetime


class ProductUpdatedPayloadV1(ProductCataloguedPayloadV1):
    changed_fields: list[str]
