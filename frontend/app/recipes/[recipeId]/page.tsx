import { RecipeDetailView } from "@/components/features/recipes/RecipeDetailView";

export default async function RecipeDetailPage({
  params,
}: {
  params: Promise<{ recipeId: string }>;
}) {
  const { recipeId } = await params;
  return <RecipeDetailView recipeId={recipeId} />;
}
