from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.dietary_tags import DietaryTag, DietaryTags


def test_dietary_tags_from_raw_labels_dedups_and_normalizes_case():
    tags = DietaryTags.from_raw_labels(["Vegan", "VEGAN", "gluten-free"])
    assert tags.tags == frozenset({DietaryTag.VEGAN, DietaryTag.GLUTEN_FREE})


def test_dietary_tags_drops_unrecognized_label_without_raising():
    tags = DietaryTags.from_raw_labels(["vegan", "totally-not-a-real-tag"])
    assert tags.tags == frozenset({DietaryTag.VEGAN})


def test_allergen_tags_union_never_drops_a_reported_allergen():
    a = AllergenTags(frozenset({AllergenTag.GLUTEN}))
    b = AllergenTags(frozenset({AllergenTag.MILK}))
    merged = AllergenTags.union(a, b)
    assert merged.tags == frozenset({AllergenTag.GLUTEN, AllergenTag.MILK})
