"""allergen_tag_deriver — reconciles each source's own allergen/label
vocabulary into the canonical `AllergenTag`/`DietaryTag` sets. Cross-source
vocabulary reconciliation is the actual point of this service (test-plan
§1) — kept as standalone functions (rather than folded silently into
`product_normalizer`) so each source's mapping table is independently
testable and independently correctable if a source changes its vocabulary.
"""

from __future__ import annotations

from domain.value_objects.allergen_tags import AllergenTag, AllergenTags
from domain.value_objects.dietary_tags import DietaryTags

# Open Food Facts uses a `en:<slug>` taxonomy for allergens_tags/labels_tags.
_OFF_ALLERGEN_MAP: dict[str, AllergenTag] = {
    "en:gluten": AllergenTag.GLUTEN,
    "en:milk": AllergenTag.MILK,
    "en:eggs": AllergenTag.EGGS,
    "en:nuts": AllergenTag.NUTS,
    "en:peanuts": AllergenTag.PEANUTS,
    "en:soybeans": AllergenTag.SOY,
    "en:fish": AllergenTag.FISH,
    "en:crustaceans": AllergenTag.SHELLFISH,
    "en:molluscs": AllergenTag.MOLLUSCS,
    "en:sesame-seeds": AllergenTag.SESAME,
    "en:celery": AllergenTag.CELERY,
    "en:mustard": AllergenTag.MUSTARD,
    "en:sulphur-dioxide-and-sulphites": AllergenTag.SULPHITES,
    "en:lupin": AllergenTag.LUPIN,
}

# USDA Branded Foods has no structured allergen field — the best available
# signal is a conservative keyword scan over the free-text `ingredients`
# string. Deliberately over-inclusive (a false positive costs nothing; a
# false negative could hide a real allergen) per Addendum 1's union rule.
_USDA_INGREDIENT_KEYWORDS: dict[str, AllergenTag] = {
    "wheat": AllergenTag.GLUTEN,
    "gluten": AllergenTag.GLUTEN,
    "barley": AllergenTag.GLUTEN,
    "milk": AllergenTag.MILK,
    "whey": AllergenTag.MILK,
    "casein": AllergenTag.MILK,
    "egg": AllergenTag.EGGS,
    "soy": AllergenTag.SOY,
    "peanut": AllergenTag.PEANUTS,
    "almond": AllergenTag.NUTS,
    "walnut": AllergenTag.NUTS,
    "cashew": AllergenTag.NUTS,
    "tree nut": AllergenTag.NUTS,
    "fish": AllergenTag.FISH,
    "shrimp": AllergenTag.SHELLFISH,
    "crab": AllergenTag.SHELLFISH,
    "lobster": AllergenTag.SHELLFISH,
    "sesame": AllergenTag.SESAME,
    "celery": AllergenTag.CELERY,
    "mustard": AllergenTag.MUSTARD,
    "sulfite": AllergenTag.SULPHITES,
    "sulphite": AllergenTag.SULPHITES,
    "lupin": AllergenTag.LUPIN,
}


def derive_off_allergen_tags(raw_allergens_tags: list[str]) -> AllergenTags:
    tags = set()
    for raw in raw_allergens_tags:
        mapped = _OFF_ALLERGEN_MAP.get(raw.strip().lower())
        if mapped is not None:
            tags.add(mapped)
    return AllergenTags(frozenset(tags))


def derive_usda_allergen_tags(ingredients_text: str | None) -> AllergenTags:
    if not ingredients_text:
        return AllergenTags.empty()
    lowered = ingredients_text.lower()
    tags = {tag for keyword, tag in _USDA_INGREDIENT_KEYWORDS.items() if keyword in lowered}
    return AllergenTags(frozenset(tags))


def derive_dietary_tags_from_off_labels(raw_labels_tags: list[str]) -> DietaryTags:
    stripped = [label.split(":", 1)[-1] if ":" in label else label for label in raw_labels_tags]
    return DietaryTags.from_raw_labels(stripped)
