export interface LoadingSkeletonProps {
  label: string;
}

/** Announced via aria-live so a screen reader user knows content is
 * loading, not just a visually-empty area (accessibility-standards
 * SKILL.md). */
export function LoadingSkeleton({ label }: LoadingSkeletonProps) {
  return (
    <div role="status" aria-live="polite" className="loading-skeleton">
      {label}
    </div>
  );
}
