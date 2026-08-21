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

### Providers

- `VisionProvider` isolates Gemini request/response handling and permits a future local implementation.
- `EmbeddingService` owns local sentence-transformers loading, batching, normalization, and model versioning.
- Raw AI output never flows directly to domain persistence.

## Main request flows

### Image processing

```text
upload -> validate bytes/MIME/size -> store asset -> enqueue durable item -> 202
worker -> Gemini -> Pydantic validation -> confidence policy -> metadata
worker -> semantic representation -> local embedding -> pgvector
worker -> progress + per-call logs -> complete or visible failure
```

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

## Planned deployment boundary

Docker Compose will eventually start PostgreSQL, the FastAPI process, and a separate worker process. The frontend will be added only after the backend probes pass. Redis, Celery, Three.js, and React Three Fiber are not planned.

