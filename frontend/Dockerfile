# syntax=docker/dockerfile:1
#
# Multi-stage build (docs/containerization-and-orchestration.md section 1):
# node:22-alpine for the build stage, a minimal runtime stage, non-root
# user, git-SHA image tag applied at CI/deploy time (never `latest`).
#
# Build context is the repo root (docker-compose.yml / frontend-ci.yml),
# matching every backend service's own convention, so a future
# packages/shared-contracts-equivalent TS package can be added as a local
# workspace dependency without a Dockerfile rewrite.

FROM node:22-alpine AS builder
WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate
COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json frontend/package.json
RUN pnpm install --frozen-lockfile --filter frontend...
COPY frontend/ frontend/
WORKDIR /repo/frontend
RUN pnpm build

FROM node:22-alpine AS runtime
# node:22-alpine already ships a non-root "node" user (uid/gid 1000) --
# reused here rather than creating a colliding one (docs/containerization-
# and-orchestration.md section 1's "non-root user" requirement, satisfied
# via the base image's own convention instead of a bespoke one).
WORKDIR /app
# Standalone output bundles only the production node_modules subset
# next actually needs, traced from the build -- no full workspace
# node_modules copy required (see next.config.ts's `output: "standalone"`).
COPY --from=builder /repo/frontend/.next/standalone ./
COPY --from=builder /repo/frontend/.next/static ./frontend/.next/static
COPY --from=builder /repo/frontend/public ./frontend/public
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "frontend/server.js"]
