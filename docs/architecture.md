# Architecture

## Component view

```text
Authenticated client (Next.js or API evaluator)
                    |
                    v
             FastAPI auth + validation
                    |
                    v
        workspace-scoped application services
                    |
                    v
          workspace-scoped repositories
                    |
                    v
             PostgreSQL + pgvector

Image flow
  durable PostgreSQL job -> worker -> vision provider -> Pydantic validation
  -> metadata -> image embedding -> vector + per-call accounting

Post flow
  durable PostgreSQL job -> worker -> post embedding
  -> vector + per-call accounting

Matching and review
  post vector -> pgvector retrieval -> deterministic mismatch guard
  -> persisted recommendation or NO_CONFIDENT_MATCH -> append-only human review

Evaluation
  versioned labeled dataset -> real application services
  -> persisted per-example evidence and aggregate metrics
```

The mismatch guard is a deterministic service inside the application layer. It is not implemented by Gemini and cannot be bypassed by a high vector-similarity score.

The Phase 11 frontend is a presentation client, not a decision layer. It
separates raw candidates from guarded outcomes, reads evaluation/review values
from FastAPI, and hides approval when review is prohibited. Browser integration
adds only configured CORS, validated image content, composed image read details,
and recommendation IDs for navigation.

CSS perspective and transforms provide restrained card depth; Motion springs
handle pointer tilt and state transitions with reduced-motion fallbacks. No WebGL,
Three.js, React Three Fiber, or frontend state framework is used.

## Layer responsibilities

### API

- Authenticate the caller and resolve its workspace.
- Validate request data and uploaded files.
- Translate application outcomes into stable HTTP responses.
- Keep business rules out of route handlers.

### Services

- Orchestrate ingestion, processing, matching, review, and evaluation.
- Apply idempotency and state-transition rules.
- Invoke provider interfaces rather than vendor clients directly.
- Call the deterministic mismatch guard for every candidate.
- Phase 7 `ImageRetrievalService` loads the configured post vector, enforces
  embedding compatibility, converts cosine distance to similarity, and produces
  typed candidate snapshots. It makes no guard decision.
- Phase 8 `RecommendationService` requests raw ranked records, evaluates every row
  through the pure `MismatchGuard`, persists a run plus candidate snapshots, and
  selects the first `ACCEPTED` rank or returns `NO_CONFIDENT_MATCH`.

### Repositories

- Own SQLAlchemy persistence queries.
- Apply workspace scoping to tenant-owned data.
- Provide transactional job claiming and state updates.
- Hide pgvector query details from application services.
- Rank compatible image vectors with exact pgvector cosine distance and a stable
  UUID tie-breaker; apply `LIMIT` in SQL.

### PostgreSQL and pgvector

- Persist images, structured metadata, posts, vectors, recommendations, review history, jobs, idempotency records, AI-call logs, and evaluation runs.
- Use Alembic migrations and deliberate indexes.
- Perform cosine ranking without a second vector database.

### Worker

- Claim durable job items with a lease.
- Run vision and embedding operations outside HTTP requests.
- Retry transient failures with bounded backoff.
- Make duplicate delivery safe.
- Record progress, costs, latency, failures, and terminal alerts.

The implemented Phase 5 worker is a separate `python -m
app.workers.image_processing` process. It atomically selects eligible items with
PostgreSQL `FOR UPDATE SKIP LOCKED`, assigns a unique lease token, and commits the
claim before invoking vision. Only the current lease token may commit an item
outcome. Expired leases are eligible for another worker; an expired final attempt
is terminally failed.

Transient provider timeouts/unavailability use capped exponential backoff.
Malformed output, schema violations, missing images/files, provider
misconfiguration, and budget denial are permanent item failures. Job counters are
recomputed under a job-row lock after each terminal item transition.

Phase 12.5 extends this same queue with `image_processing` and `post_embedding`
job types. Image items run vision, validate/persist metadata, then generate and
persist the image embedding before terminal success. An embedding-only retry
reuses valid metadata instead of calling vision again. Post embedding creation
returns `202` and is claimed by the same worker. Provider/persistence outages are
transient; invalid vectors, configuration, and eligibility failures are permanent.

### Providers

- `VisionProvider` isolates Gemini request/response handling and permits a future local implementation.
- `EmbeddingProvider` isolates local sentence-transformers and the deterministic
  test fake. `EmbeddingService` owns eligibility, validation, reuse, accounting,
  and persistence.
- Raw AI output never flows directly to domain persistence.

## Main request flows

### Image processing

```text
upload -> validate bytes/MIME/size -> store asset -> enqueue durable item -> 202
worker -> Gemini -> Pydantic validation -> confidence policy -> metadata
       -> semantic representation -> embedding provider
  -> pgvector + per-call log OR visible failure
```

Phase 4 retains this deprecated synchronous single-image debug subset:

```text
POST /images/{id}/analyze -> stored-file validation -> VisionProvider
  -> strict Pydantic validation -> confidence flag -> one metadata row
```

Phase 5 implements the durable worker flow for production processing through
`POST /images/process`. Job creation is idempotent by unique key and exact image
set; status and item inspection are available under `/jobs/{id}`.

### Article matching

```text
raw retrieval (Phase 7, unchanged):
article -> embedding -> exact pgvector ranking -> raw candidate snapshots

guarded recommendation (Phase 8):
raw candidates -> deterministic guard
               -> persisted decisions
               -> highest-ranked accepted image OR NO_CONFIDENT_MATCH

persisted recommendation -> inspect / approve / reject
                         -> append-only human review history
```

Phase 10 exposes inspection and review through a narrow application service. The
latest review is projected as `pending`, `approved`, or `rejected`. Review writes
never invoke providers or create AI-call logs, and both human actions require the
persisted guard decision to be `ACCEPTED`.

Bearer authentication resolves an active persisted API-key digest to a workspace
before any tenant route runs. Repositories scope images, posts, jobs, candidates,
recommendations/reviews, call logs, and evaluations by that workspace; child rows
derive ownership from their parent foreign key. Foreign IDs return `404`. Health
and readiness deliberately bypass this dependency. `reviewer_id` remains nullable
because the minimal credential identifies a workspace, not an individual person.

### Labeled evaluation

```text
evaluation.jsonl -> strict label validation
  -> isolated post/image fixtures
  -> actual embedding -> retrieval -> guard -> recommendation services
  -> per-example evidence + metric calculation
  -> one EvaluationRun report in the application database
```

The fixtures use deterministic 384-dimensional vectors and never load Gemini or
sentence-transformers. Each example has its own in-memory database, so evaluation
posts, images, embeddings, AI-call logs, and recommendations cannot pollute the
development corpus. CLI and API runs persist only the versioned aggregate and
per-example JSON report.

Pgvector returns cosine distance through `<=>`; the repository orders it ascending
and limits the query, while the service exposes `1 - distance` so larger response
scores are always better. Only exact model/revision/dimension matches are compared.
No approximate index is used for the bounded corpus.

### Safety boundary

```text
high similarity + red_fox == gray_wolf
    -> SUBJECT_MISMATCH
    -> rejected

no accepted candidates
    -> NO_CONFIDENT_MATCH
```

## Deployment boundary

Docker Compose starts PostgreSQL, FastAPI, the image-processing worker, and the
standalone Next.js production server. The deterministic Compose default uses the
pinned licensed-corpus fixture providers; Gemini and the pinned local embedding
model remain explicit configuration. Redis, Celery,
Three.js, and React Three Fiber are not planned.

The Phase 12.5 seed adds no runtime service. It validates/downloads the 50-image
SHA-pinned Wikimedia corpus, uploads it through normal ingestion, enqueues the
actual batch/post work, and waits on the existing worker. Separate deterministic
vectors persist the official ranking and mismatch/refusal probe evidence. The
frontend remains a presentation client; FastAPI remains the authority for
workspace access, retrieval, guard decisions, and human-review permission.
