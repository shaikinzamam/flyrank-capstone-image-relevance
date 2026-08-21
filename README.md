# Image Relevance & Auto-Tagging

## AI Image Understanding & Content Matching Engine

## Project

This FlyRank Backend AI Engineering capstone will build a trustworthy service that understands a small image library, generates structured metadata, and recommends images for articles only when the available evidence is strong enough.

The project is currently at the **Phase 2 walking skeleton**. The FastAPI runtime, PostgreSQL connection, Alembic infrastructure, pgvector extension, and health/readiness endpoints exist. No domain feature or evaluation result exists yet.

## Problem

Semantic similarity alone is not a safe recommendation policy. A gray wolf can be semantically close to an article about red foxes while still being the wrong subject. The system therefore combines semantic retrieval with a deterministic mismatch guard that can refuse every candidate and return `No confident match`.

## Core idea

```text
Images -> validated vision metadata -> image embeddings --+
                                                        +-> ranking -> mismatch guard -> recommendation or refusal
Articles ---------------------------> post embeddings ---+
```

The mismatch guard remains separate from the vision model. A high similarity score never overrides a hard subject mismatch.

## Architecture

The planned backend uses thin FastAPI routes, application services, repositories, PostgreSQL with pgvector, and a separate PostgreSQL-backed worker. Gemini Flash is isolated behind a vision-provider interface, while sentence-transformers provides local embeddings.

See [docs/design.md](docs/design.md) and [docs/architecture.md](docs/architecture.md) for the approved design.

## Tech stack

- Python 3.12
- FastAPI and Pydantic v2
- SQLAlchemy 2 and Alembic
- PostgreSQL and pgvector
- Gemini Flash Vision behind a provider interface
- Local sentence-transformers embeddings
- PostgreSQL-backed durable worker
- pytest
- Docker Compose
- Later presentation layer: Next.js, TypeScript, Tailwind CSS, Framer Motion, and CSS 3D transforms

Three.js and React Three Fiber are intentionally excluded.

## Current status

- Phase 1 design artifacts: complete
- Phase 2 backend walking skeleton: complete
- FastAPI `/health` and database-backed `/ready`: verified
- PostgreSQL, pgvector, SQLAlchemy, and Alembic infrastructure: verified
- Domain models and application features: not started
- Corpus collection: not started
- Evaluation execution: not started
- Frontend: postponed until backend acceptance probes pass

## Planned setup

The current walking skeleton can be started from the repository root with:

```powershell
docker compose up --build -d
```

The API entrypoint applies Alembic migrations before starting Uvicorn. Verify it with:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
docker compose exec -T api pytest
```

Expected walking-skeleton responses are `{"status":"ok"}` and `{"status":"ready","database":"reachable"}`. Corpus seeding and evaluation commands remain TODO because those features are outside Phase 2.

## Evaluation

A small labeled evaluation set will measure top-1 precision and guard behavior, including equivalent terms, unsafe sibling subjects, low-confidence metadata, and no-match cases. The initial planned records are in [data/evaluation.jsonl](data/evaluation.jsonl).

**No evaluation has been run and no precision score is claimed yet.** The README will contain the measured result only after the evaluation runner exists and has been executed.

## Demo scenario

```text
Red fox article -> fox recommended.

Correct fox unavailable -> wolf candidate rejected -> No confident match.
```

The demo will also show batch progress, structured metadata, explanations, a human approval/rejection trail, real evaluation output, and per-call AI cost records.

## Limitations

- This is not a general-purpose image search engine and will target approximately 50 images.
- The initial taxonomy covers only a small, documented set of subjects.
- Model confidence is an input signal, not calibrated truth.
- Thresholds must be tuned against labeled data before they can be considered reliable.
- Local filesystem image storage is suitable for the capstone but not a distributed production deployment.
- The premium frontend is presentation polish, not part of the backend correctness core.
