# Image Relevance & Auto-Tagging

## AI Image Understanding & Content Matching Engine

## Project

This FlyRank Backend AI Engineering capstone will build a trustworthy service that understands a small image library, generates structured metadata, and recommends images for articles only when the available evidence is strong enough.

The project is currently at **Phase 5 durable background image processing**. The API creates idempotent batch jobs, a separate PostgreSQL-backed worker claims leased items, and validated vision metadata is processed with bounded retries and progress tracking. Embeddings, matching, and evaluation have not started.

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
- Phase 3 secure JPEG, PNG, and WEBP ingestion: complete
- Phase 4 provider-isolated vision metadata: implemented
- Phase 5 durable background processing: implemented
- Image upload, listing, detail, hashing, duplicate rejection, and local persistence: verified
- FastAPI `/health` and database-backed `/ready`: verified
- PostgreSQL, pgvector, SQLAlchemy, and Alembic infrastructure: verified
- Image assets move through `uploaded`, `processing`, `processed`, and `failed`
- Structured AI metadata is locally schema-validated before persistence
- Confidence below `VISION_LOW_CONFIDENCE_THRESHOLD` is stored as `flagged`
- Vision call status, latency, retry count, provider/model, and known cost are logged
- `POST /images/process` returns an idempotent durable job with `202 Accepted`
- A separate worker uses PostgreSQL `FOR UPDATE SKIP LOCKED`, leases, and capped exponential backoff
- Job and item inspection expose progress, timestamps, attempts, and clean terminal errors
- Expired leases can be reclaimed after worker interruption
- Embeddings and matching domain features: not started
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

Expected probe responses are `{"status":"ok"}` and `{"status":"ready","database":"reachable"}`. Corpus seeding and evaluation commands remain TODO because those features are outside the current ingestion phase.

Register an image with multipart form data and inspect registered assets with:

```powershell
curl.exe -F "file=@C:\path\to\image.png;type=image/png" http://localhost:8000/images
Invoke-RestMethod http://localhost:8000/images
Invoke-RestMethod http://localhost:8000/images/{image_id}
```

Analyze one uploaded image synchronously with:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/images/{image_id}/analyze
Invoke-RestMethod -Method Post 'http://localhost:8000/images/{image_id}/analyze?reprocess=true'
```

The ordinary analyze call returns the existing metadata (`reused: true`) when one
row already exists. The explicit `reprocess=true` form calls the provider and
replaces that row only after the new output passes validation. This Phase 4 HTTP
flow is intentionally synchronous; durable batch/background processing and retry
orchestration are implemented by the Phase 5 job path. This synchronous endpoint
is deprecated and retained only for explicit development/debug use; production
clients should create jobs instead.

Queue one or more uploaded images without waiting for vision processing:

```powershell
$body = @{
  image_ids = @("IMAGE_UUID_1", "IMAGE_UUID_2")
  idempotency_key = "demo-batch-001"
} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -ContentType application/json `
  -Body $body http://localhost:8000/images/process
Invoke-RestMethod http://localhost:8000/jobs/$($job.id)
Invoke-RestMethod http://localhost:8000/jobs/$($job.id)/items
```

The Compose stack runs PostgreSQL, API, and worker processes. Its default
`VISION_PROVIDER=fake` is deliberate so deterministic worker verification never
uses credentials or incurs cost. Set `VISION_PROVIDER=gemini`, a Gemini key, an
explicit conservative per-call estimate, and a total demo budget to use Gemini.

Uploads are streamed with a configured byte limit, hashed with SHA-256, decoded with Pillow, restricted to JPEG/PNG/WEBP, and stored under generated keys in a controlled local directory. A byte-identical upload returns `409 Conflict`; no second database row or file is created. `storage_key` is an opaque relative identifier, not a host filesystem path.

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
- Authentication and workspace isolation are not implemented yet; the image table is intentionally unscoped until that boundary is designed.
- The Phase 4 taxonomy is intentionally limited to red fox, gray wolf, domestic dog, brown bear, and white-tailed deer; out-of-taxonomy classifications are rejected.
- The default `0.70` low-confidence threshold is configurable and provisional until evaluation tunes it.
- The budget guard is a total-demo cap. It atomically reserves the configured conservative estimated cost before every provider attempt; when budgeting is enabled, a missing estimate blocks the call.
- Processing is at-least-once. Lease tokens prevent stale workers from completing reclaimed items, while the unique metadata row makes repeated processing persistence idempotent. A crash after a provider call can still require another billed call after lease recovery.
- The premium frontend is presentation polish, not part of the backend correctness core.
