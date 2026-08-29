"""GetDashboardHandler -- the one query handler this service has
(implementation plan section 2). Fans out three independent, parallel
calls (`asyncio.gather(..., return_exceptions=True)` -- exceptions are
CAPTURED per call, never raised through, per the resilience guarantee
this handler exists to provide: one failing/degraded dependency degrades
only its own section, never the whole response) and maps each raw
result/exception into a `SectionStatus`.

This handler performs ZERO computation beyond that structural mapping --
no arithmetic, no business rule, nothing beyond "did this call succeed,
what shape did it come back in" (bff-agent.md's central, non-negotiable
rule). See tests/unit/application/test_get_dashboard.py's structural
guardrail test, which parses this module's own source to enforce that.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from domain.ports.diary_summary_port import DiarySummaryPort, DiarySummaryResult
from domain.ports.nutrition_target_port import (
    NutritionTargetNotComputedYet,
    NutritionTargetPort,
    NutritionTargetResult,
)
from domain.ports.nutrition_totals_port import NutritionTotalsPort, NutritionTotalsResult
from domain.value_objects.section_status import SectionStatus


@dataclass(frozen=True, slots=True)
class GetDashboardQuery:
    user_id: uuid.UUID
    dashboard_date: date
    authorization_header: str


@dataclass(frozen=True, slots=True)
class DashboardResult:
    diary_summary: SectionStatus[DiarySummaryResult]
    nutrient_totals: SectionStatus[NutritionTotalsResult]
    target: SectionStatus[NutritionTargetResult]


class GetDashboardHandler:
    def __init__(
        self,
        diary_summary_port: DiarySummaryPort,
        nutrition_totals_port: NutritionTotalsPort,
        nutrition_target_port: NutritionTargetPort,
    ) -> None:
        self._diary_summary_port = diary_summary_port
        self._nutrition_totals_port = nutrition_totals_port
        self._nutrition_target_port = nutrition_target_port

    async def handle(self, query: GetDashboardQuery) -> DashboardResult:
        diary_outcome, totals_outcome, target_outcome = await asyncio.gather(
            self._diary_summary_port.get_summary(query.dashboard_date, query.authorization_header),
            self._nutrition_totals_port.get_totals(
                query.dashboard_date, query.authorization_header
            ),
            self._nutrition_target_port.get_target(query.authorization_header),
            return_exceptions=True,
        )

        return DashboardResult(
            diary_summary=_to_section(diary_outcome),
            nutrient_totals=_to_section(totals_outcome),
            target=_to_target_section(target_outcome),
        )


def _to_section(outcome: object) -> SectionStatus[Any]:
    if isinstance(outcome, BaseException):
        return SectionStatus.unavailable(reason="downstream_error")
    return SectionStatus.available(outcome)


def _to_target_section(
    outcome: NutritionTargetResult | NutritionTargetNotComputedYet | BaseException,
) -> SectionStatus[NutritionTargetResult]:
    if isinstance(outcome, BaseException):
        return SectionStatus.unavailable(reason="downstream_error")
    if isinstance(outcome, NutritionTargetNotComputedYet):
        return SectionStatus.unavailable(reason="not_yet_computed")
    return SectionStatus.available(outcome)
