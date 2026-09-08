import { Suspense } from "react";
import { VerifyEmailStatus } from "@/components/features/auth/VerifyEmailStatus";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

export default function VerifyEmailPage() {
  return (
    <div className="page">
      <Suspense fallback={<LoadingSkeleton label="Loading…" />}>
        <VerifyEmailStatus />
      </Suspense>
    </div>
  );
}
