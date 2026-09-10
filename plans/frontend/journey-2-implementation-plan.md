# Implementation Plan — `frontend` journey 2 (photo upload → AI detection → logged entry)

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-10, by adrianrg1996@gmail.com.

**Related:** CLAUDE.md §3 (E2E journey 2), §8 (AI food/photo recognition boundary); `/plans/frontend/implementation-plan.md` (journey 1, already merged — this plan extends that app and inherits its resolutions unless a deviation is named below); `docs/frontend-architecture.md`; `.claude/skills/media-recognition-conventions/SKILL.md`; `.claude/skills/accessibility-standards/SKILL.md`; `services/food-recognition-service/` (actual contract, read directly); `docs/api-catalog.md`.

---

## 1. Scope

Build CLAUDE.md §3's E2E journey 2 on top of the existing frontend app: **"Upload a food photo → AI detects the item → logged with computed nutrients."**

**New/changed routes:**

| Route | Purpose | Calls |
|---|---|---|
| `/log/photo` (new) | Upload a food photo, review up to 3 AI candidates | `POST /api/v1/recognition/photos/analyze` (food-recognition-service, proxied) |
| `/search` (modified) | Catalog search — now also reachable pre-filled from a chosen AI candidate, or as the explicit manual fallback | unchanged: `GET /api/v1/catalog/products/search` |
| `/log/[productId]` (modified) | Now also accepts optional AI-context query params to log a confirmed product as `ai_detected`-sourced | unchanged: `GET /api/v1/catalog/products/{id}` + `POST /api/v1/diary/food-entries` |
| `/dashboard` (unchanged) | Same journey-1 dashboard, must reflect the new entry | unchanged: `GET /api/v1/bff/dashboard?date=` |

**Flow:** `/log/photo` (select/take a photo → submit) → candidate list (name, confidence %, portion range as a range, never a single number) → user picks one candidate **or** "none of these — search manually" → navigates to `/search?q=<candidate name>&aiAnalysisId=…&aiPortionMinG=…&aiPortionMaxG=…` (prefilled, auto-submitted) → user picks the actual catalog product that matches → `/log/[productId]?aiAnalysisId=…` → generalized log form, quantity pre-filled from the portion-range midpoint (editable), submits with `source.source_type = "ai_detected"` → same success screen/dashboard-lag messaging as journey 1.

**Key architectural finding driving this design (resolution 1 below): `food-recognition-service`'s `POST /api/v1/recognition/photos/analyze` returns no nutrient data at all per candidate** — only `name`, `portion_range_min_g/max_g`, `confidence`. `diary-service` requires the client to supply real `macros_per_unit` at logging time and never fabricates/zero-fills them. So "logged with computed nutrients" for the photo path is only honest if the AI-identified *name* is used to find a real catalog product (via the existing `/search` flow, which does carry real `nutrition_per_100g`), and that confirmed product's macros are what actually gets logged — the AI photo picks the candidate identity and a portion-range hint; the catalog match supplies the numbers.

**Acceptance criteria:**
1. A logged-in user can upload a photo at `/log/photo`, see up to 3 candidates (or an honest "uncertain"/"unavailable" state), pick one, be taken through catalog confirmation, and log a food entry whose `source.source_type = "ai_detected"` and whose macros come from a real, confirmed catalog product — then see `/dashboard` reflect it (same eventual-consistency caveat as journey 1).
2. A user can reject all candidates (or land on an "unavailable" result) and reach a fully usable manual-entry path (`/search`) with no assumption they reviewed the photo/candidates visually.
3. Every new/changed typed API client module has a Zod schema matching the real backend Pydantic schema field-for-field.
4. No candidate confidence or portion estimate is ever silently auto-accepted or collapsed to a single number.
5. TypeScript strict mode, zero `any`, unit/integration coverage on every new/modified component/hook/schema/mapping function; a new Playwright E2E spec for this journey.
6. WCAG 2.1 AA baseline met, including a fully keyboard/screen-reader-operable path that never assumes the user can visually inspect the photo or the candidate thumbnails.
7. CI green for `frontend-ci.yml`.

**Explicitly out of scope:**
- **Barcode scanning** — a meaningfully smaller addition (returns a full `CatalogProductResponse` directly, no candidate-matching gap), flagged as the natural next follow-up, not built this pass since CLAUDE.md's journey 2 wording names the photo path specifically.
- Pro features, chat, recipes, social, water/fasting/meal-planning, wearables.
- Client-side HEIC→JPEG conversion.
- Drag-and-drop upload (a plain `<input type="file">` is the whole upload affordance).

---

## 2. Architectural classification

Frontend-only change, no backend service touched. Same classification as journey 1: Server Components by default, Client Components where interactive. `/log/photo` is a Client Component. `/search` stays a Client Component, now accepting optional server-supplied initial props. `/log/[productId]` stays a Server Component shell reading `params` and now `searchParams`. Server state via TanStack Query (`useAnalyzePhoto`, alongside existing hooks). No new client-side store.

---

## 3. Files to create or modify

```
frontend/
  app/
    log/
      photo/
        page.tsx                          # NEW — upload + candidate review (Client Component)
      [productId]/
        page.tsx                          # MODIFY — read searchParams (aiAnalysisId/aiCandidateName/
                                           #   aiPortionMinG/aiPortionMaxG), build an AiContext
    search/
      page.tsx                            # MODIFY — read searchParams (q, aiAnalysisId, aiCandidateName,
                                           #   aiPortionMinG/MaxG)
    api/
      food-recognition/
        photos/
          analyze/
            route.ts                      # NEW — multipart Route Handler proxy
  components/
    features/
      recognition/                        # NEW directory
        PhotoUploadForm.tsx                 # NEW
        CandidateList.tsx                   # NEW
        ConfidenceBadge.tsx                 # NEW
      diary/
        LogFoodEntryForm.tsx                # MODIFY — generalize via a `mapToRequest` closure etc.
      catalog/
        ProductSearchBox.tsx                # MODIFY — optional `initialQuery` + `aiContext` passthrough
        ProductResultList.tsx               # MODIFY — thread `aiContext` through
        ProductResultCard.tsx               # MODIFY — append AI query params to the log href when present
      AppNav.tsx                            # MODIFY — add a "Log from photo" link
  lib/
    api/
      food-recognition.ts                  # NEW — analyzeFoodPhoto(file, accessToken), own FormData path
    server/
      backend-config.ts                    # MODIFY — add FOOD_RECOGNITION_SERVICE_BASE_URL
    hooks/
      useAnalyzePhoto.ts                   # NEW
    diary-mapping.ts                       # MODIFY — productToLogFoodEntryRequest gains an optional
                                            #   sourceOverride param, defaulting to today's behavior
  schemas/
    food-recognition.ts                    # NEW — mirrors recognition_schemas.py field-for-field
  messages/
    en.json                               # MODIFY — new photoLog/recognition keys
  tests/
    unit/
      schemas.food-recognition.test.ts     # NEW
    integration/
      PhotoUploadForm.test.tsx             # NEW
      CandidateList.test.tsx               # NEW
      route-handlers.test.ts               # MODIFY
    fixtures/
      food-recognition.fixtures.ts         # NEW
    e2e/
      photo-log-dashboard.spec.ts          # NEW

docker-compose.yml                        # MODIFY — frontend: add FOOD_RECOGNITION_SERVICE_BASE_URL
                                            #   + food-recognition-service to depends_on
infra/k8s/charts/frontend/
  values.yaml                              # MODIFY — 5th downstreamEgress entry + env var
  templates/networkpolicy-egress-downstream.yaml
                                            # MODIFY — 5th egress block
docs/api-catalog.md                        # MODIFY — note frontend as a consumer of /api/v1/recognition
```

No change to any `services/*` file. No new backend endpoint, no new domain event, no `infra/terraform` change.

---

## 4. API integration

**`lib/api/food-recognition.ts`**: `analyzeFoodPhoto(file, accessToken)` builds real `FormData` (field `file`) and POSTs to this app's own Route Handler. Deliberately does not go through `apiFetch` (JSON-only, would corrupt a multipart body) — a small, documented duplication of the minimal pieces needed (timeout, error parsing), not a silent divergence. Own longer timeout (45000ms vs. the shared 8000ms default), matching food-recognition-service's own documented resilience budget.

**`app/api/food-recognition/photos/analyze/route.ts`**: reads `Authorization: Bearer` (401 if absent), reads `request.formData()`, validates size under an 8MB cap (see resolution 4), rebuilds `FormData`, POSTs to `FOOD_RECOGNITION_SERVICE_BASE_URL`, relays the response verbatim.

**Response shape** (from `recognition_schemas.py`): `{analysis_id, status: "detected"|"uncertain"|"unavailable", candidates: [{name, portion_range_min_g, portion_range_max_g, confidence}], model_version}`. Max 3 candidates, enforced both backend and frontend-side.

**`lib/diary-mapping.ts`**: `productToLogFoodEntryRequest` gains an optional `sourceOverride` param (`source_type: "ai_detected"`, `source_reference_id: analysis_id`), defaulting to unchanged `catalog_product` behavior. The "never fabricate macros" guard applies identically to both paths — macros always come from the matched catalog product, never the AI candidate.

**`useLogFoodEntry`**: unchanged, already fully source-agnostic.

**Authentication**: identical to journey 1 — browser never talks to `food-recognition-service` directly, only to this app's own Route Handler.

---

## 5. Cross-service impact

- **First real use of `source_type: "ai_detected"`** — `diary-service`'s own plan reserved this value and named a future `architecture-agent` review as the trigger condition. Addressed via resolution 2 below (a scoped architecture-agent review, dispatched alongside this plan's approval, not blocking implementation start).
- **Micronutrient totals will show `"unavailable"` for `ai_detected` entries** — confirmed in `nutrition-calculation-service`'s existing code (`recompute_daily_nutrient_total.py` only attempts the mirror lookup for `catalog_product` sources). Macro totals unaffected (client-supplied, always real). No backend/bff-service change needed — already-correct, already-handled degrade path.
- **`bff-service` requires no change** (no `source_type` reference anywhere in its codebase).
- **`food-recognition-service`'s ingress `NetworkPolicy` will block this call in a real cluster** — same known, documented gap journey 1 already carries for its four downstream calls. Adds a 5th entry to that known list; the fix is `food-recognition-agent`'s follow-up, not built here.
- No new/changed domain event.

---

## 6. Accessibility & i18n

- Plain, labeled `<input type="file">` — no drag-and-drop, inherently keyboard-operable.
- `CandidateList` is a real `<ul>`/`<li>`, each item's accessible name combining name + confidence + portion range — full decision-relevant content available without seeing anything. Photo thumbnail (if shown) is decorative (`alt=""`), never load-bearing.
- Confidence always shown as a literal number ("confidence: NN%"), never color-only, never a frontend-side re-derivation of the backend's threshold.
- Portion always rendered as a range ("approx. NN–NN g"), never collapsed to a single number in display copy (the quantity input itself is still a single editable number, per diary-service's contract).
- "None of these — search manually" always present, not conditional on `status === "unavailable"`.
- `/log/[productId]`'s AI-sourced state adds a text disclosure banner, not a visual-only cue.
- `axe-core` on `/log/photo` and modified states of `/search`/`/log/[productId]`, same gate as journey 1. Manual keyboard-only + screen-reader smoke pass before `/implementation-review`.
- Same `next-intl`/`en` locale, `Intl.NumberFormat` for confidence/gram formatting.

---

## 7. Testing/CI/deploy

No change to `frontend-ci.yml`'s stage shape — additive within the existing pipeline. 80% overall coverage threshold unchanged, no carve-out. `docker-compose.yml`: `frontend` gains `FOOD_RECOGNITION_SERVICE_BASE_URL` + `food-recognition-service` in `depends_on`. `infra/k8s/charts/frontend/`: 5th egress target mirroring the existing 4 exactly, no chart schema change.

---

## 8. Test plan reference

`/test-plan` defines concrete cases next: schema round-trips against `detected`/`uncertain`/`unavailable` fixtures; the multipart Route Handler's 401/oversized-file/backend-error cases; `productToLogFoodEntryRequest`'s new `sourceOverride` branch (still blocks on missing catalog macros); `CandidateList`'s accessible-name construction; axe-core; a Playwright E2E spec covering the full upload→confirm→log→dashboard path plus the "none of these" manual path.

---

## 9. Risks and open questions — resolved at approval time (2026-09-10)

1. **Candidate→catalog-match design — RESOLVED, approved as the only honest approach.** Routing the AI candidate's name through `/search` to find a real product, then logging that product's real macros tagged `ai_detected`, is the only design that doesn't either invent numbers or silently lose AI provenance, given the actual backend contracts (food-recognition-service returns no nutrient data; diary-service never fabricates macros). This is a technical necessity forced by the real contracts, not an open business choice — approved as designed.
2. **`architecture-agent` review of `ai_detected` source-type usage — dispatched alongside this approval**, per diary-service's own plan naming this as the trigger condition for that review. Not blocking implementation start; findings will be addressed as a follow-up if the review surfaces anything requiring a design change.
3. **Confidence-tier display — PROCEED as designed.** Show the raw percentage for every candidate, never a second frontend-side threshold guess. Revisit only if product wants a tier label backed by a real backend-exposed threshold.
4. **Upload size cap — PROCEED with 8MB**, enforced client-side and at the Route Handler (defense in depth), as a frontend-only mitigation since `food-recognition-service` itself enforces none. A real backend-side limit is `food-recognition-agent`'s to add later.
5. **HEIC photos — PROCEED with client-side `accept` restriction only**, no transcoding. Flagged for a manual check during `/test-execution` against a real iPhone-captured photo.
6. **Buffering the upload server-side rather than streaming — PROCEED as the pragmatic first-cut choice.** Revisit toward a streamed relay only if it becomes a measured issue in staging.
7. **No feature flag** — consistent with journey 1's reasoning; `food-recognition-service`'s own kill switch already covers the degrade path, which the UI already handles honestly.
