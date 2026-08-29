"""GET /api/v1/bff/dashboard -- test-plan section 3. Every fixture
downstream call is a fake port (never a real diary-service/
nutrition-calculation-service call)."""

from __future__ import annotations

import uuid

import jsonschema
import pytest

from domain.ports.nutrition_target_port import NutritionTargetNotComputedYet
from tests.contract.http.conftest import auth_headers
from tests.fixtures.factories import DEFAULT_DASHBOARD_DATE

USER_ID = uuid.uuid4()

_SECTION_ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["status", "reason", "data"],
    "properties": {
        "status": {"enum": ["available", "unavailable"]},
        "reason": {"enum": [None, "downstream_error", "not_yet_computed"]},
        "data": {"type": ["object", "null"]},
    },
    "additionalProperties": False,
}

_DASHBOARD_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["diary_summary", "nutrient_totals", "target"],
    "properties": {
        "diary_summary": _SECTION_ENVELOPE_SCHEMA,
        "nutrient_totals": _SECTION_ENVELOPE_SCHEMA,
        "target": _SECTION_ENVELOPE_SCHEMA,
    },
    "additionalProperties": False,
}


def _query_params() -> dict[str, str]:
    return {"date": DEFAULT_DASHBOARD_DATE.isoformat()}


async def test_all_succeed__200_all_sections_available(app_client):
    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["diary_summary"]["status"] == "available"
    assert body["nutrient_totals"]["status"] == "available"
    assert body["target"]["status"] == "available"
    assert body["diary_summary"]["data"]["total_calories_kcal"] == 1850.0
    assert body["nutrient_totals"]["data"]["calories_kcal"] == 1820.0
    assert body["target"]["data"]["calorie_target_kcal"] == 2200.0


async def test_diary_service_failure__200_degraded_diary_section_only(app_client, diary_port):
    diary_port._error = RuntimeError("simulated diary-service circuit open")

    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["diary_summary"] == {
        "status": "unavailable",
        "reason": "downstream_error",
        "data": None,
    }
    assert body["nutrient_totals"]["status"] == "available"
    assert body["target"]["status"] == "available"


async def test_nutrition_totals_failure__200_degraded_totals_section_only(app_client, totals_port):
    totals_port._error = RuntimeError("simulated nutrition-calculation-service circuit open")

    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["nutrient_totals"] == {
        "status": "unavailable",
        "reason": "downstream_error",
        "data": None,
    }
    assert body["diary_summary"]["status"] == "available"
    assert body["target"]["status"] == "available"


async def test_nutrition_target_failure__200_degraded_target_section_downstream_error(
    app_client, target_port
):
    target_port._error = RuntimeError("simulated nutrition-calculation-service circuit open")

    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["target"] == {"status": "unavailable", "reason": "downstream_error", "data": None}


async def test_nutrition_target_not_yet_computed__200_degraded_target_section_not_yet_computed(
    app_client, target_port
):
    target_port._result = NutritionTargetNotComputedYet()

    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["target"] == {"status": "unavailable", "reason": "not_yet_computed", "data": None}


async def test_all_three_fail__200_fully_degraded_never_a_5xx(
    app_client, diary_port, totals_port, target_port
):
    diary_port._error = RuntimeError("diary down")
    totals_port._error = RuntimeError("totals down")
    target_port._error = RuntimeError("target down")

    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=auth_headers(USER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _DASHBOARD_RESPONSE_SCHEMA)
    assert body["diary_summary"]["status"] == "unavailable"
    assert body["nutrient_totals"]["status"] == "unavailable"
    assert body["target"]["status"] == "unavailable"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "not-a-bearer-token"}])
async def test_missing_or_invalid_authorization__401_and_zero_downstream_requests(
    app_client, diary_port, totals_port, target_port, headers
):
    response = await app_client.get(
        "/api/v1/bff/dashboard", params=_query_params(), headers=headers
    )

    assert response.status_code == 401
    assert diary_port.calls == []
    assert totals_port.calls == []
    assert target_port.calls == []


async def test_missing_date_query_param__422(app_client):
    response = await app_client.get("/api/v1/bff/dashboard", headers=auth_headers(USER_ID))

    assert response.status_code == 422


async def test_malformed_date_query_param__422(app_client):
    response = await app_client.get(
        "/api/v1/bff/dashboard", params={"date": "not-a-date"}, headers=auth_headers(USER_ID)
    )

    assert response.status_code == 422
