# System Design

## Problem

Selecting the closest semantic image is not enough. Embeddings deliberately place related concepts near one another, so a gray wolf can receive a high similarity score for an article about red foxes. That relationship is useful for retrieval but unsafe as a final recommendation.

The system must recommend an image only when the evidence is strong enough. Otherwise it must refuse the recommendation and explain why.

```text
Article expects: red fox
Candidate:       gray wolf
Similarity:      high
Decision:        REJECT
Reason:          subject mismatch
```

The product principle is: good suggestions when confident, safe rejection when uncertain.

## Scope

The initial corpus will contain approximately 50 licensed-free images across a few deliberately similar subjects. Candidate subjects include:

- red fox
- wolf
- dog
- bear
- deer

This is a target shape, not a requirement for exactly ten images per subject. A compact corpus makes model output inspectable and enables a carefully labeled evaluation set.

The backend includes validated ingestion, vision metadata, embeddings, ranking, a deterministic guard, durable jobs, cost records, a minimal review workflow, and evaluation. Authentication and workspace isolation will be implemented only to the level needed for real authorization and cross-workspace protection.

## Explicit non-goals

This project is **not** a general-purpose image search engine and does not attempt to index huge image libraries.

It will not initially include Redis, Celery, multiple vision models, distributed object storage, complex role-based access control, OAuth, invitations, email verification, password reset, or unrelated account features.

The premium Next.js frontend is presentation polish and not part of the backend correctness core. It is postponed until the backend acceptance probes pass. Three.js and React Three Fiber are out of scope.

## Core pipeline

```text
Image
  -> Vision AI
  -> schema validation
  -> normalized metadata
  -> semantic text representation
  -> embedding
  -> PostgreSQL + pgvector

Article
  -> normalized article text
  -> embedding
  -> PostgreSQL + pgvector

Article embedding + image embeddings
  -> cosine similarity ranking
  -> deterministic mismatch guard
  -> accepted recommendation OR No confident match
  -> human review
```

## Metadata schema

The metadata contract preserves both specific subject and broad category:

```json
{
  "subject": "red fox",
  "subject_code": "red_fox",
  "category": "animal",
  "caption": "A red fox standing in a snowy forest",
  "tags": ["red fox", "snow", "forest", "wildlife"],
  "attributes": ["orange fur", "winter"],
  "objects": ["fox", "trees", "snow"],
  "confidence": 0.96
}
```

`subject` is the human-readable specific subject. `subject_code` is its normalized taxonomy identifier. `category` is deliberately broader. Fox and wolf can both have category `animal`; therefore category cannot replace subject in safety decisions.

All model output will be parsed into a strict Pydantic v2 schema before entering domain tables. Missing fields, invalid types, out-of-range confidence, empty required collections, unknown taxonomy values, and malformed JSON will be rejected or flagged according to a documented policy.

## Matching strategy

Image metadata becomes a textual representation containing subject, category, caption, tags, attributes, and objects. The same sentence-transformers model embeds this representation and the combined article title/body into a shared vector space.

PostgreSQL with pgvector stores both vector types. Retrieval ranks candidate images by cosine similarity. At the expected scale, exact search is preferred; an approximate index will be added only if measurement supports it.

Retrieval produces candidates, not decisions. Every candidate passes through the guard.

Phase 7 implements retrieval: `ImageRetrievalService` retrieves the
configured post embedding and asks PostgreSQL for compatible image embeddings
ordered by pgvector cosine distance (`<=>`) ascending, then image UUID ascending.
The API converts distance to similarity with `1 - distance`; higher is always
better. `top_k` is applied in SQL and bounded to 1–20. Exact search is used, with
no HNSW, IVFFlat, or FAISS.

Mixed libraries exclude image rows whose model, pinned revision, or dimensions do
not match the post. A library with embeddings but no compatible image row returns
a visible conflict instead of an empty, misleading result. Missing metadata is
excluded by the join, and schema-invalid metadata is excluded by service-level
validation. Flagged low-confidence metadata remains visible and explicitly
flagged. None of these candidates is accepted or rejected during retrieval.
Phase 8 leaves that raw endpoint unchanged and lets `RecommendationService` read
the ranked rows (including invalid metadata), invoke `MismatchGuard`, persist every
decision, and select only the first accepted semantic rank.

## Mismatch guard

The deterministic guard evaluates signals in this order:

1. Invalid or missing metadata -> `INVALID_METADATA`
2. Low vision confidence -> `LOW_CONFIDENCE`
3. Normalize the article's expected subject and the image subject
4. Subject conflict -> `SUBJECT_MISMATCH`
5. Broad category conflict -> `CATEGORY_MISMATCH`
6. Mandatory concept/tag missing -> `REQUIRED_TAG_MISSING`
7. Similarity below the configured threshold -> `LOW_SIMILARITY`
8. Otherwise -> `ACCEPTED`

If every candidate is rejected, the matching result is `NO_CONFIDENT_MATCH` and includes the relevant reasons.

**A high semantic similarity score must never override a hard subject mismatch.** The guard does not call Gemini and must be fully deterministic under a fixed configuration.

The provisional thresholds live in one versioned location:

`backend/app/core/matching_config.py`

`phase8-v1` uses minimum similarity `0.70` and minimum vision confidence `0.70`.
They are implementation defaults, not optimized values; Phase 9 evaluation will
tune them. Subject aliases are centralized in `subject_taxonomy.py`, including
`red fox`, `red_fox`, and `Vulpes vulpes` -> `red_fox`.

Each request creates a `recommendation_runs` row with config and embedding identity
and one `recommendations` row per candidate. Candidate rows retain rank, similarity,
confidence, metadata flags, expected/candidate taxonomy inputs, required/candidate
tags, decision/reason code, and explanation. No AI-call logs are created by this
deterministic flow.

## Human review state

Human review is separate from the immutable AI/guard decision. Every persisted
candidate can be inspected, but only a candidate whose guard decision is
`ACCEPTED` can be approved or rejected. Its derived initial state is `pending`.
Actions are stored in append-only `recommendation_reviews` rows with `approved` or
`rejected`, an optional comment, nullable future `reviewer_id`, and creation time.

The latest row is current. An exact retry is idempotent; changing the decision or
comment explicitly appends a row and preserves prior history. Human `rejected`
alongside AI `ACCEPTED` is valid editorial judgment. Review never overwrites rank,
similarity, confidence, guard decision/reason, or explanation. A guard-rejected row
cannot receive either action, preventing a mismatch or safe refusal bypass.

## Durable job design

The API persists processing jobs and item records, then returns `202` without waiting for AI work. A separate worker claims available items using PostgreSQL row locking with `SKIP LOCKED` and expiring leases. It maintains attempts, progress, terminal errors, and retry schedules. Leases are configured longer than provider timeouts; an abandoned lease is reclaimed without relying on an in-process heartbeat.

Content hashes, unique constraints, exact-image-set idempotency keys, lease tokens, and the one-row metadata upsert prevent duplicate durable effects under request retries and at-least-once execution. Every vision attempt, including failures and zero-cost fake calls, creates an attributed call record. The configurable total-demo budget atomically reserves an operator-supplied conservative cost estimate before provider calls. Embedding accounting remains future work.

Redis and Celery are unnecessary for the bounded workload and are not part of the initial design.

## Phase 6 embedding contract

Images and posts share `sentence-transformers/all-MiniLM-L6-v2` pinned to revision
`c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, 384 dimensions, and L2-normalized
output. Image text is built in
a fixed subject/category/caption/tags/attributes/objects order. Post text uses the
stored title/body and includes optional expected subject/category only when they
exist; Phase 6 performs no AI intent extraction.

The SHA-256 hash of UTF-8 semantic text is stored with each vector. The unique
resource/model/version row is reused when its hash is unchanged, updated after a
content change, and supplemented by a new row for another compatible
model/version. Vectors must be non-empty, exactly 384-dimensional, finite numeric
values before persistence. Flagged low-confidence metadata is embeddable but
remains flagged for the future guard. Exact search is deferred with ranking; no
HNSW or FAISS index is introduced.

## Authentication and workspace isolation

The implementation will use the minimum real authentication mechanism needed by the capstone. All owned records will carry a workspace identifier, authorization will be enforced at the boundary and repository query level, and automated tests will attempt cross-workspace access.

OAuth, complex RBAC, invitations, email workflows, and general account-management features are explicitly excluded.

## Evaluation design

The versioned JSON Lines records in `data/evaluation.jsonl` describe article input,
expected subject/category/tags, acceptable and unsafe images, explicit candidate
metadata/vectors, expected guard decisions, expected no-match behavior, and human
labeling notes. Parsing rejects duplicate example IDs, mixed versions, malformed
references, overlapping labels, and missing per-candidate decisions.

The set covers:

- a direct red-fox match
- equivalent terminology (`Vulpes vulpes`)
- a wolf match
- a forced wolf candidate for a fox article
- a generic dog hard negative
- a post for which no suitable image exists
- low-confidence metadata that must be rejected
- low-similarity correct-subject metadata
- required-tag failure
- category mismatch

`EvaluationEngine` creates a separate in-memory database per example and exercises
the actual post/image embedding services with deterministic vectors, retrieval,
mismatch guard, and recommendation persistence. This cannot touch the development
corpus. `EvaluationService` persists only the final report to `evaluation_runs`.

Metric formulas:

- top-1 precision = correct acceptable issued recommendations / all issued recommendations
- safe acceptance precision = accepted candidates labeled acceptable / all accepted candidates
- unsafe rejection recall = unsafe candidates rejected / all labeled unsafe candidates
- incorrect refusal = expected recommendation with `NO_CONFIDENT_MATCH`
- correct no-match = expected `NO_CONFIDENT_MATCH` with no selected image

The project-local materials do not contain the PDF's mathematical formula, so the
standard precision interpretation above is documented explicitly. Refusals are
reported separately and are not folded into precision. Baseline `evaluation-v1`
under unchanged `phase8-v1` produced `3/3` correct issued recommendations,
`7/7` correct refusals, zero unsafe acceptances, and top-1 precision `1.0000`.

## Main risks

- Embeddings can rank related but incorrect subjects highly.
- Vision confidence is self-reported and may be poorly calibrated.
- Article-subject extraction can itself be incorrect.
- Provider output can drift across model versions.
- Duplicate job delivery can repeat costly work without idempotency.
- A tiny dataset can overfit thresholds and inflate metrics.
- Corpus licensing and repository size must remain reproducible and auditable.
- Frontend polish can distract from acceptance-probe correctness.
