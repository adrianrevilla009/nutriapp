import { DashboardView } from "@/components/features/dashboard/DashboardView";

// Server component shell (docs/frontend-architecture.md section 2) --
// deliberately thin: the actual data fetch depends on the browser-held,
// in-memory access token (lib/session.ts) and the browser's own local
// "today" (lib/date.ts), neither of which a server render can know, so
// the real work happens in the client child below.
export default function DashboardPage() {
  return <DashboardView />;
}
