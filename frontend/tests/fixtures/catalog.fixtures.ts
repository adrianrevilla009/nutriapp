/**
 * Fixtures shaped from
 * services/catalog-service/infrastructure/http/schemas/{product_schemas,search_schemas}.py
 * (read verbatim during /implementation-plan's research). Test-plan section 4/8.
 */
import type { ProductResponse, ProductSearchResponse } from "@/schemas/catalog";

// A fully-populated product, e.g. an Open Food Facts-sourced item.
export const productWithNutritionFixture: ProductResponse = {
  product_id: "22222222-2222-4222-8222-222222222222",
  barcode: "0000000000017",
  name: "Plain Yogurt",
  brand: "Acme Dairy",
  category: "dairy",
  nutrition_per_100g: {
    energy_kcal: 61,
    protein_g: 3.5,
    carbohydrates_g: 4.7,
    fat_g: 3.3,
    sugars_g: 4.7,
    fiber_g: 0,
    saturated_fat_g: 2.1,
    sodium_mg: 46,
    salt_g: 0.11,
    calcium_mg: 121,
    iron_mg: 0.05,
    vitamin_c_mg: 0.5,
  },
  dietary_tags: ["vegetarian"],
  allergen_tags: ["milk"],
  package_size: { value: 500, unit: "g" },
  price: { amount: 1.99, currency: "USD" },
  sources: ["open_food_facts"],
};

// All-nullable-fields-populated variant (product_schemas.py's `| None`
// fields, every one actually null) -- e.g. a barcode-only catalog stub with
// no nutrition data on file yet.
export const productWithoutNutritionFixture: ProductResponse = {
  product_id: "33333333-3333-4333-8333-333333333333",
  barcode: null,
  name: "Unlabeled Item",
  brand: null,
  category: null,
  nutrition_per_100g: null,
  dietary_tags: [],
  allergen_tags: [],
  package_size: null,
  price: null,
  sources: [],
};

export const productSearchResponseFixture: ProductSearchResponse = {
  items: [productWithNutritionFixture],
  total: 1,
  page: 1,
  page_size: 20,
};

export const emptyProductSearchResponseFixture: ProductSearchResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
};
