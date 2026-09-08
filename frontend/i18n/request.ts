import { getRequestConfig } from "next-intl/server";

// Single "en" locale ships this pass (docs/frontend-architecture.md
// section 6) -- the seam exists (every user-facing string is a
// translation key, never an inline literal) so a second locale is a
// messages-file addition later, not a component rewrite.
export default getRequestConfig(async () => {
  const locale = "en";
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
