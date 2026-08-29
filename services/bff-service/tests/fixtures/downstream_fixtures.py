"""Loader for the hand-authored downstream response fixtures
(test-plan section 7) -- matches each real service's actual current
response schema (read from that service's own Pydantic response model,
not guessed): diary-service's DailySummaryResponse,
nutrition-calculation-service's NutrientTotalResponse/
NutritionTargetResponse."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).parent / "downstream_responses"


def load_downstream_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURES_DIR / f"{name}.json").read_text())
