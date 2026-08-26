import pytest

from domain.value_objects.nutrient_panel import (
    IncompleteNutrientPanelError,
    InvalidNutrientPanelError,
    NutrientPanel,
)


def test_all_zero_panel_accepted():
    panel = NutrientPanel(energy_kcal=0, protein_g=0, carbohydrates_g=0, fat_g=0)
    assert panel.energy_kcal == 0


def test_negative_value_raises():
    with pytest.raises(InvalidNutrientPanelError):
        NutrientPanel(energy_kcal=-1, protein_g=1, carbohydrates_g=1, fat_g=1)


def test_missing_optional_micronutrients_accepted():
    panel = NutrientPanel(energy_kcal=100, protein_g=1, carbohydrates_g=1, fat_g=1)
    assert panel.sugars_g is None


def test_missing_macro_core_raises():
    with pytest.raises(IncompleteNutrientPanelError):
        NutrientPanel(energy_kcal=None, protein_g=1, carbohydrates_g=1, fat_g=1)
