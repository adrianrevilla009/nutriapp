import { ProSuccessBanner } from "@/components/features/billing/ProSuccessBanner";

// Server component shell reading Stripe's own `session_id` query param --
// display only, no data fetch (resolution 3: this app has no endpoint to
// verify entitlement with).
export default async function ProSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ session_id?: string }>;
}) {
  const sp = await searchParams;
  return <ProSuccessBanner sessionId={sp.session_id} />;
}
