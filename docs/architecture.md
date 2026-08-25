# Architecture

## Component view

```text
                    Next.js frontend
              App Router | typed API client
             Tailwind | Motion | CSS 3D
                            |
                            v
                       FastAPI API
                 auth | validation | HTTP
                            |
                            v
                         Services
          ingestion | matching | guard | review | eval
                            |
                            v
                       Repositories
                            |
                            v
                 PostgreSQL + pgvector
                   ^                 ^
                   |                 |
         durable job records     vectors + domain data
                   |
                   |
                 Worker
                /      \
               v        v
     Gemini Vision    Embedding Service
       Provider       sentence-transformers
               \        /
                v      v
          AI call and cost logs
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

Phase 6 deliberately does not append embedding work to this job. The narrow
`POST /images/{id}/embedding` and `POST /posts/{id}/embedding` operations keep
vision-job completion semantics stable and make embedding failures independently
visible. A later phase may introduce a separately typed durable embedding job if
the corpus workflow requires it.

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
explicit embedding operation -> semantic representation -> local embedding
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

There is no authentication system yet. The nullable `reviewer_id` column is the
ownership seam where server-side authenticated identity will attach later; public
request schemas do not allow clients to assert it.

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
fake vision provider; Gemini remains explicit configuration. Redis, Celery,
Three.js, and React Three Fiber are not planned.

The Phase 12 evaluator seed adds no runtime service. It executes inside the API
container, follows the existing service/repository boundaries, writes generated
demo images to the controlled upload volume, and persists known-vector evidence
to PostgreSQL. The frontend remains a presentation client; FastAPI remains the
authority for retrieval, guard decisions, and human-review permission.
