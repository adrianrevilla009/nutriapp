import { OwnRecipesView } from "@/components/features/recipes/OwnRecipesView";

// Server component shell (docs/frontend-architecture.md section 2) --
// deliberately thin: the actual data fetch depends on the browser-held,
// in-memory access token (lib/session.ts), so the real work happens in the
// client child below, same pattern as app/dashboard/page.tsx.
export default async function RecipesPage({
  searchParams,
}: {
  searchParams: Promise<{ alreadyPro?: string }>;
}) {
  const sp = await searchParams;
  return <OwnRecipesView alreadyPro={sp.alreadyPro === "1"} />;
}
