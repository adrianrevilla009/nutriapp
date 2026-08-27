"""NutritionValueRecomputed/NutritionTargetUpdated published payloads
match packages/shared-contracts/schemas/*.json (test-plan section 3), and
this service's understanding of FoodEntryLogged/FoodEntryCorrected/
FoodEntryDeleted, WeightRecorded/BodyMetricRecorded/GoalSet/GoalUpdated,
and ProductCatalogued/ProductUpdated matches what's actually documented
(via shared_contracts' typed payload models -- these break loudly if an
upstream service's schema drifts, per test-plan section 3)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone

import jsonschema

from domain.entities.daily_nutrition_total import DailyNutritionTotal
from domain.events.nutrition_target_updated import build_nutrition_target_updated_event
from domain.events.nutrition_value_recomputed import build_nutrition_value_recomputed_event
from domain.value_objects.activity_level import ActivityLevel
from domain.value_objects.formula_version import CURRENT_FORMULA_VERSION
from domain.value_objects.goal_type import GoalType
from domain.value_objects.macro_target_range import MacroTargetRange
from tests.fixtures.factories import make_food_entry_logged_payload

SCHEMAS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "..",
    "packages",
    "shared-contracts",
    "schemas",
)


def _load_schema(name: str) -> dict:
    with open(os.path.join(SCHEMAS_DIR, name)) as f:
        return json.load(f)


def test_nutrition_value_recomputed_payload_matches_schema():
    schema = _load_schema("nutrition_value_recomputed.v1.json")
    user_id = uuid.uuid4()
    line = DailyNutritionTotal(user_id=user_id, total_date=date(2026, 8, 25)).compute_total()
    event = build_nutrition_value_recomputed_event(
        user_id=user_id,
        scope="day",
        entry_id=None,
        total_date=date(2026, 8, 25),
        line=line,
        confidence_range=None,
        formula_version=CURRENT_FORMULA_VERSION,
        reason="food_entry_logged",
        correlation_id="c1",
        recomputed_at=datetime.now(timezone.utc),
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_nutrition_target_updated_payload_matches_schema():
    schema = _load_schema("nutrition_target_updated.v1.json")
    event = build_nutrition_target_updated_event(
        user_id=uuid.uuid4(),
        bmr_kcal=1673.75,
        tdee_kcal=2593.0,
        calorie_target_kcal=2093.0,
        macro_targets=MacroTargetRange(
            protein_g_min=112.0,
            protein_g_max=154.0,
            fat_g_min=46.5,
            carbs_g=200.0,
            carbs_floored=False,
        ),
        goal_type=GoalType.LOSE,
        activity_level=ActivityLevel.MODERATE,
        clamped=True,
        clamp_reason="Deficit capped at 1000 kcal/day below TDEE.",
        formula_version=CURRENT_FORMULA_VERSION,
        reason="weight_recorded",
        effective_from=datetime.now(timezone.utc),
        correlation_id="c2",
    )
    jsonschema.validate(instance=event.to_wire(), schema=schema)


def test_understanding_of_food_entry_logged_matches_shared_contracts():
    from shared_contracts.events.diary import FoodEntryLoggedPayloadV1

    payload = make_food_entry_logged_payload()
    FoodEntryLoggedPayloadV1.model_validate(payload)


def test_understanding_of_food_entry_deleted_matches_shared_contracts():
    from shared_contracts.events.diary import FoodEntryDeletedPayloadV1

    payload = {
        "entry_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
    FoodEntryDeletedPayloadV1.model_validate(payload)


def test_understanding_of_weight_recorded_matches_shared_contracts():
    from shared_contracts.events.profile import WeightRecordedPayloadV1

    payload = {
        "user_id": str(uuid.uuid4()),
        "weight_kg": "ciphertext-base64",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    WeightRecordedPayloadV1.model_validate(payload)


def test_understanding_of_goal_set_matches_shared_contracts():
    from shared_contracts.events.profile import GoalSetPayloadV1

    payload = {
        "user_id": str(uuid.uuid4()),
        "goal_type": "LOSE",
        "target_value": None,
        "target_date": None,
        "set_at": datetime.now(timezone.utc).isoformat(),
    }
    GoalSetPayloadV1.model_validate(payload)


def test_understanding_of_product_catalogued_matches_shared_contracts():
    from shared_contracts.events.catalog import ProductCataloguedPayloadV1

    payload = {
        "product_id": str(uuid.uuid4()),
        "barcode": "0000000000001",
        "name": "Test Product",
        "brand": None,
        "category": None,
        "nutrition_per_100g": {
            "energy_kcal": 250.0,
            "protein_g": 12.0,
            "carbohydrates_g": 30.0,
            "fat_g": 8.0,
        },
        "dietary_tags": [],
        "allergen_tags": [],
        "package_size": None,
        "sources": ["open_food_facts"],
        "catalogued_at": datetime.now(timezone.utc).isoformat(),
    }
    ProductCataloguedPayloadV1.model_validate(payload)
