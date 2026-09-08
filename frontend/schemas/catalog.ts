/**
 * Zod schemas mirroring
 * services/catalog-service/infrastructure/http/schemas/{product_schemas,search_schemas}.py
 * field-for-field.
 */
import { z } from "zod";

// Mirrors NutrientPanelResponse -- 12 independently-nullable float fields.
export const NutrientPanelResponseSchema = z.object({
  energy_kcal: z.number().nullable(),
  protein_g: z.number().nullable(),
  carbohydrates_g: z.number().nullable(),
  fat_g: z.number().nullable(),
  sugars_g: z.number().nullable(),
  fiber_g: z.number().nullable(),
  saturated_fat_g: z.number().nullable(),
  sodium_mg: z.number().nullable(),
  salt_g: z.number().nullable(),
  calcium_mg: z.number().nullable(),
  iron_mg: z.number().nullable(),
  vitamin_c_mg: z.number().nullable(),
});
export type NutrientPanelResponse = z.infer<typeof NutrientPanelResponseSchema>;

// Mirrors PackageSizeResponse: {value: float, unit: str}
export const PackageSizeResponseSchema = z.object({
  value: z.number(),
  unit: z.string(),
});

// Mirrors PriceResponse: {amount: float, currency: str}
export const PriceResponseSchema = z.object({
  amount: z.number(),
  currency: z.string(),
});

// Mirrors ProductResponse -- every optional field is `| None` on the
// backend and therefore `.nullable()` here, never `.optional()` (the
// backend always sends the key, with a null value, never omits it).
export const ProductResponseSchema = z.object({
  product_id: z.string().uuid(),
  barcode: z.string().nullable(),
  name: z.string().nullable(),
  brand: z.string().nullable(),
  category: z.string().nullable(),
  nutrition_per_100g: NutrientPanelResponseSchema.nullable(),
  dietary_tags: z.array(z.string()),
  allergen_tags: z.array(z.string()),
  package_size: PackageSizeResponseSchema.nullable(),
  price: PriceResponseSchema.nullable(),
  sources: z.array(z.string()),
});
export type ProductResponse = z.infer<typeof ProductResponseSchema>;

// Mirrors ProductSearchResponse: {items: [...], total, page, page_size}
export const ProductSearchResponseSchema = z.object({
  items: z.array(ProductResponseSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
});
export type ProductSearchResponse = z.infer<typeof ProductSearchResponseSchema>;
