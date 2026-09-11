import { useTranslations } from "next-intl";
import { TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import { parseQuantityGrams, type IngredientRowState } from "@/lib/recipe-ingredients";

export function IngredientRow({
  row,
  onQuantityChange,
  onRemove,
}: {
  row: IngredientRowState;
  onQuantityChange: (rowId: string, value: string) => void;
  onRemove: (rowId: string) => void;
}) {
  const t = useTranslations("recipes");
  const invalid = parseQuantityGrams(row.quantityGramsInput) === null;

  return (
    <li className="ingredient-row">
      <span>{row.productName}</span>
      <TextField
        label={t("ingredientQuantityLabel", { name: row.productName })}
        type="number"
        min={0}
        step="any"
        inputMode="decimal"
        value={row.quantityGramsInput}
        onChange={(e) => onQuantityChange(row.rowId, e.target.value)}
        error={invalid ? t("ingredientQuantityInvalid") : null}
      />
      <Button
        type="button"
        variant="secondary"
        onClick={() => onRemove(row.rowId)}
        aria-label={t("removeIngredientAction", { name: row.productName })}
      >
        {t("removeIngredientAction", { name: row.productName })}
      </Button>
    </li>
  );
}
