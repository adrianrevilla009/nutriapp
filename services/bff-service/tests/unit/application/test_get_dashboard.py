"""GetDashboardHandler -- test-plan section 1. Fake ports only, no I/O."""

from __future__ import annotations

import ast
import inspect
import uuid

from application.queries.get_dashboard import GetDashboardHandler, GetDashboardQuery
from domain.ports.nutrition_target_port import NutritionTargetNotComputedYet
from tests.fixtures.factories import (
    DEFAULT_DASHBOARD_DATE,
    FakeDiarySummaryPort,
    FakeNutritionTargetPort,
    FakeNutritionTotalsPort,
    build_diary_summary_result,
    build_nutrition_target_result,
    build_nutrition_totals_result,
)

USER_ID = uuid.uuid4()
AUTH_HEADER = "Bearer test-token"


def _query() -> GetDashboardQuery:
    return GetDashboardQuery(
        user_id=USER_ID, dashboard_date=DEFAULT_DASHBOARD_DATE, authorization_header=AUTH_HEADER
    )


async def test_all_succeed__all_sections_available_with_field_level_mapping():
    diary_result = build_diary_summary_result(total_calories_kcal=1999.0)
    totals_result = build_nutrition_totals_result(calories_kcal=1980.0)
    target_result = build_nutrition_target_result(calorie_target_kcal=2100.0)

    handler = GetDashboardHandler(
        diary_summary_port=FakeDiarySummaryPort(result=diary_result),
        nutrition_totals_port=FakeNutritionTotalsPort(result=totals_result),
        nutrition_target_port=FakeNutritionTargetPort(result=target_result),
    )

    result = await handler.handle(_query())

    assert result.diary_summary.status == "available"
    assert result.diary_summary.data is diary_result
    assert result.diary_summary.data.total_calories_kcal == 1999.0

    assert result.nutrient_totals.status == "available"
    assert result.nutrient_totals.data is totals_result
    assert result.nutrient_totals.data.calories_kcal == 1980.0

    assert result.target.status == "available"
    assert result.target.data is target_result
    assert result.target.data.calorie_target_kcal == 2100.0


async def test_diary_summary_port_raises__only_diary_section_degraded():
    diary_port = FakeDiarySummaryPort(error=RuntimeError("simulated circuit open"))
    totals_port = FakeNutritionTotalsPort()
    target_port = FakeNutritionTargetPort()

    handler = GetDashboardHandler(diary_port, totals_port, target_port)
    result = await handler.handle(_query())

    assert result.diary_summary.status == "unavailable"
    assert result.diary_summary.reason == "downstream_error"
    assert result.diary_summary.data is None

    assert result.nutrient_totals.status == "available"
    assert result.target.status == "available"


async def test_nutrition_totals_port_raises__only_totals_section_degraded():
    diary_port = FakeDiarySummaryPort()
    totals_port = FakeNutritionTotalsPort(error=RuntimeError("simulated circuit open"))
    target_port = FakeNutritionTargetPort()

    handler = GetDashboardHandler(diary_port, totals_port, target_port)
    result = await handler.handle(_query())

    assert result.nutrient_totals.status == "unavailable"
    assert result.nutrient_totals.reason == "downstream_error"
    assert result.nutrient_totals.data is None

    assert result.diary_summary.status == "available"
    assert result.target.status == "available"


async def test_nutrition_target_port_raises_generic_error__target_unavailable_downstream_error():
    diary_port = FakeDiarySummaryPort()
    totals_port = FakeNutritionTotalsPort()
    target_port = FakeNutritionTargetPort(error=RuntimeError("simulated transport failure"))

    handler = GetDashboardHandler(diary_port, totals_port, target_port)
    result = await handler.handle(_query())

    assert result.target.status == "unavailable"
    assert result.target.reason == "downstream_error"
    assert result.target.data is None


async def test_nutrition_target_port_returns_not_computed_yet__target_unavailable_not_yet_computed():
    diary_port = FakeDiarySummaryPort()
    totals_port = FakeNutritionTotalsPort()
    target_port = FakeNutritionTargetPort(result=NutritionTargetNotComputedYet())

    handler = GetDashboardHandler(diary_port, totals_port, target_port)
    result = await handler.handle(_query())

    assert result.target.status == "unavailable"
    assert result.target.reason == "not_yet_computed"
    assert result.target.data is None


async def test_not_yet_computed_and_downstream_error_reasons_are_distinct():
    handler_error = GetDashboardHandler(
        FakeDiarySummaryPort(),
        FakeNutritionTotalsPort(),
        FakeNutritionTargetPort(error=RuntimeError("boom")),
    )
    handler_not_computed = GetDashboardHandler(
        FakeDiarySummaryPort(),
        FakeNutritionTotalsPort(),
        FakeNutritionTargetPort(result=NutritionTargetNotComputedYet()),
    )

    error_result = await handler_error.handle(_query())
    not_computed_result = await handler_not_computed.handle(_query())

    assert error_result.target.reason == "downstream_error"
    assert not_computed_result.target.reason == "not_yet_computed"
    assert error_result.target.reason != not_computed_result.target.reason


async def test_all_three_fail__still_returns_a_fully_degraded_result_not_an_exception():
    handler = GetDashboardHandler(
        FakeDiarySummaryPort(error=RuntimeError("diary down")),
        FakeNutritionTotalsPort(error=RuntimeError("totals down")),
        FakeNutritionTargetPort(error=RuntimeError("target down")),
    )

    result = await handler.handle(_query())

    assert result.diary_summary.status == "unavailable"
    assert result.nutrient_totals.status == "unavailable"
    assert result.target.status == "unavailable"
    assert result.diary_summary.reason == "downstream_error"
    assert result.nutrient_totals.reason == "downstream_error"
    assert result.target.reason == "downstream_error"


def test_handler_module_contains_no_business_logic__structural_guardrail():
    """Mirrors food-recognition-service's "never writes to diary-service"
    structural test precedent (test-plan section 1): parses this
    handler's own source and asserts it contains no arithmetic or
    ordering-comparison operators -- this handler must only ever decide
    "did the call succeed / what shape did it return", never compute or
    threshold a value (bff-agent.md's central rule)."""
    import application.queries.get_dashboard as module

    source = inspect.getsource(module)
    tree = ast.parse(source)

    forbidden_binops = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )
    forbidden_compare_ops = (ast.Lt, ast.Gt, ast.LtE, ast.GtE)

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            assert not isinstance(node.op, forbidden_binops), (
                "GetDashboardHandler must contain no arithmetic -- business "
                "computation belongs in the owning domain service (ADR-0008)."
            )
        if isinstance(node, ast.Compare):
            assert not any(isinstance(op, forbidden_compare_ops) for op in node.ops), (
                "GetDashboardHandler must contain no ordering comparisons -- "
                "any threshold/eligibility logic belongs in the owning domain "
                "service (ADR-0008)."
            )
