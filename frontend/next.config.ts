import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// i18n wired from the start per docs/frontend-architecture.md section 6 /
// .claude/skills/i18n-conventions/SKILL.md -- a single "en" locale ships
// this pass, but the seam exists so a second locale is a data addition,
// not a rewrite.
const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output -- the Dockerfile's runtime stage copies only
  // .next/standalone + .next/static + public/, not the full node_modules
  // tree, per docs/containerization-and-orchestration.md section 1's
  // "runtime stage copies only the artifacts needed to run" convention.
  output: "standalone",
};

export default withNextIntl(nextConfig);
