from domain.services.allergen_tag_deriver import (
    derive_dietary_tags_from_off_labels,
    derive_off_allergen_tags,
    derive_usda_allergen_tags,
)
from domain.value_objects.allergen_tags import AllergenTag
from domain.value_objects.dietary_tags import DietaryTag


def test_off_allergen_list_maps_to_correct_set():
    tags = derive_off_allergen_tags(["en:gluten", "en:milk", "en:unknown-thing"])
    assert tags.tags == frozenset({AllergenTag.GLUTEN, AllergenTag.MILK})


def test_usda_ingredient_text_maps_to_same_internal_enum():
    tags = derive_usda_allergen_tags("Enriched wheat flour, milk, soy lecithin.")
    assert tags.tags == frozenset({AllergenTag.GLUTEN, AllergenTag.MILK, AllergenTag.SOY})


def test_usda_allergen_derivation_handles_missing_ingredients():
    tags = derive_usda_allergen_tags(None)
    assert tags.tags == frozenset()


def test_off_dietary_labels_derivation():
    tags = derive_dietary_tags_from_off_labels(["en:vegan", "en:organic"])
    assert tags.tags == frozenset({DietaryTag.VEGAN, DietaryTag.ORGANIC})


def test_conflicting_allergen_info_between_sources_is_unioned_not_intersected():
    off_tags = derive_off_allergen_tags(["en:gluten"])
    usda_tags = derive_usda_allergen_tags("Contains no known allergens.")
    from domain.value_objects.allergen_tags import AllergenTags

    merged = AllergenTags.union(off_tags, usda_tags)
    assert AllergenTag.GLUTEN in merged
