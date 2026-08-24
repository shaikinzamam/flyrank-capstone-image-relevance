# Architecture

## Component view

```text
                     Next.js (later)
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

### Repositories

- Own SQLAlchemy persistence queries.
- Apply workspace scoping to tenant-owned data.
- Provide transactional job claiming and state updates.
- Hide pgvector query details from application services.

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
article -> embedding -> pgvector ranking -> candidate snapshots
        -> deterministic guard per candidate
        -> accepted ranked suggestions OR No confident match
        -> inspect / approve / reject
```

### Safety boundary

```text
high similarity + red_fox == gray_wolf
    -> SUBJECT_MISMATCH
    -> rejected

no accepted candidates
    -> NO_CONFIDENT_MATCH
```

## Deployment boundary

Docker Compose starts PostgreSQL, the FastAPI process, and a separate image-processing worker. The deterministic Compose default uses the fake vision provider; Gemini remains an explicit environment configuration. The frontend will be added only after the backend probes pass. Redis, Celery, Three.js, and React Three Fiber are not planned.
