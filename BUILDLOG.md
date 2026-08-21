# Build Log

This log records how AI assistance was used, which design choices were made, and what the project owner changed or verified. It must remain factual; planned work is not recorded as completed work.

## 2026-08-21 — Phase 1 design

### AI assistance

- Used Codex to read the FlyRank capstone brief and separate mandatory acceptance requirements from optional presentation scope.
- Used Codex to draft the initial design and submission-pack skeleton after architecture approval.

### Decisions

- Selected Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, pgvector, pytest, and Docker Compose.
- Selected Gemini Flash Vision behind a provider interface so model-specific behavior does not enter application services.
- Selected local sentence-transformers embeddings to keep embedding generation reproducible and free.
- Selected PostgreSQL plus pgvector to keep durable application data and vector retrieval in one persistence system. At the intended corpus size, exact cosine search is sufficient; a specialized distributed vector service would add no useful value.
- Selected a PostgreSQL-backed durable worker. Redis and Celery were intentionally avoided because PostgreSQL leasing, retries, idempotency, and progress records are enough for this bounded workload.
- Kept `subject` separate from broad `category`. A fox and a wolf may both be animals, so category alone cannot enforce the critical mismatch boundary.
- Made the mismatch guard deterministic and separate from Gemini. Hard subject conflicts override semantic similarity because closeness does not establish correctness.
- Postponed the Next.js frontend until the backend acceptance probes work. The frontend is presentation polish rather than the correctness core.

### Not yet done

- No backend or frontend code has been implemented.
- No images have been downloaded or processed.
- No model calls, tests, debugging sessions, or evaluations have occurred.
- No performance or precision result is claimed.

