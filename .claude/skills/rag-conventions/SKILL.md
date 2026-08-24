---
description: Conventions for the RAG (Retrieval-Augmented Generation) pipeline behind nutrition-assistant-service. Use whenever designing or reviewing anything that retrieves a user's own diary/profile data and feeds it to an LLM.
---

# RAG Conventions — `nutrition-assistant-service`

This skill defines **how** the RAG pipeline must be designed once it is
implemented. It does not implement anything — it is the specification
`ai-assistant-agent` and `architecture-agent` must follow and review against.

## Scope of Retrieval
- The assistant is grounded **only** in the requesting user's own data:
  their records from `diary-service`, computed values from
  `nutrition-calculation-service`, trend/analytics summaries, and any content the
  user explicitly saved (notes, goals). Never retrieve or leak another
  user's data into a prompt, under any circumstance — this is a hard
  boundary, not a best-effort one.
- General domain knowledge (not user-specific) must come from a separate,
  curated, versioned knowledge base — not from the open web at query time.
  Any external source used to build that knowledge base must be reviewed
  and dated (domain guidance changes over time).

## Chunking Strategy
- Structured data (records, computed totals, targets) is **not** chunked as
  free text — it is retrieved as structured records and formatted into the
  prompt deterministically. Chunking/embeddings are reserved for
  unstructured content (curated knowledge base, user free-text notes).
- For unstructured content: chunk by semantic unit (a full tip, a full
  FAQ entry) rather than fixed token windows, to avoid splitting a fact
  across two chunks. Target chunk size and overlap must be documented and
  justified in the implementation plan, not chosen arbitrarily.

## Embeddings & Vector Store
- Qdrant is the vector store (per `CLAUDE.md` section 2.5). One collection
  per logical content type (e.g. curated knowledge base vs. user notes) —
  never mix content types with different access-control requirements in
  the same collection.
- Embedding model choice, dimensionality, and re-embedding strategy (what
  happens when the model changes) must be documented in an ADR before
  implementation, since it affects every future retrieval.

## Grounding & Hallucination Prevention
- Every factual claim in a response must be traceable to a retrieved
  record or knowledge-base entry. If the retrieved context does not
  contain enough information to answer, the assistant must say so
  explicitly rather than filling the gap from the model's general
  training knowledge.
- The assistant never fabricates specific numbers or facts that are not
  present in the user's own data or the curated knowledge base.
- Responses must distinguish clearly between "this is what your data
  shows" and "this is general guidance" — the two must never be blended
  into a single unattributed statement.

## Professional-Advice Boundary
- Per `CLAUDE.md` section 8: the assistant never provides medical
  nutrition therapy, a diagnosis, or a professional recommendation it
  isn't licensed to give. Any query that reads as such a question (e.g.
  asking whether a symptom is linked to a nutrient deficiency) must be met
  with a visible redirect to a qualified dietitian/physician, not an
  attempt to answer from retrieved content alone.
- This boundary must be testable: the implementation plan for
  `nutrition-assistant-service` must include an explicit set of
  boundary-testing prompts (see Evaluation below) that verify the redirect
  happens consistently.

## Evaluation (before any release, and on every prompt/model change)
- Maintain a fixed evaluation set of representative queries (grounded
  factual questions, out-of-scope questions, ambiguous questions,
  adversarial attempts to retrieve another user's data) with expected
  behavior for each.
- A change to the retrieval logic, the embedding model, or the system
  prompt requires re-running this evaluation set before it can pass
  `/implementation-review`. Regressions in the professional-advice-boundary
  or cross-user-isolation categories are release-blocking; regressions in
  answer quality are reviewed case by case.
- Track and log (per `.claude/skills/observability-audit/SKILL.md`) which
  retrieved records backed each response, so a bad answer can be traced
  back to a retrieval or generation failure.

## Cost & Latency
- Every RAG call is subject to the resilience patterns in
  `.claude/skills/resilience-patterns/SKILL.md` (timeout, circuit breaker,
  explicit fallback — e.g. "answer from structured data only" if the
  vector store is unavailable).
- Model and retrieval-depth (top-k) choices must consider the guidance in
  `.claude/skills/llm-cost-and-model-selection/SKILL.md`.
