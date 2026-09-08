import { useEffect, useRef } from "react";

export interface ErrorBannerProps {
  message: string;
  /** When true, moves focus to this banner as soon as it renders -- a
   * submission error must move focus to the error summary, a commonly
   * missed a11y requirement (test-plan section 5). */
  autoFocus?: boolean;
}

export function ErrorBanner({ message, autoFocus = true }: ErrorBannerProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus, message]);

  return (
    <div ref={ref} role="alert" tabIndex={-1} className="error-banner">
      {message}
    </div>
  );
}
