# Image Relevance & Auto-Tagging

## AI Image Understanding & Content Matching Engine

## Project

This FlyRank Backend AI Engineering capstone will build a trustworthy service that understands a small image library, generates structured metadata, and recommends images for articles only when the available evidence is strong enough.

The project is currently at **Phase 8 guarded recommendations**. PostgreSQL/pgvector
still returns raw semantic candidates, while a separate deterministic guard now
accepts the highest-ranked safe candidate or explicitly returns
`NO_CONFIDENT_MATCH`. Human review and evaluation have not started.

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
- Phase 6 embedding generation and pgvector persistence: implemented
- Phase 7 exact semantic retrieval and candidate ranking: implemented
- Phase 8 deterministic mismatch guard, persistence, and refusal: implemented
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
- Deterministic image/post semantic text, content-aware embeddings, and
  `vector(384)` persistence: implemented
- Semantic candidate ranking: implemented
- Mismatch guard and final recommendations: implemented
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

Create and embed a post, or explicitly embed schema-valid image metadata:

```powershell
$post = Invoke-RestMethod -Method Post -ContentType application/json `
  -Body '{"title":"Winter foxes","body":"A red fox in snow.","expected_subject":"red fox","expected_category":"animal","required_tags":["snow"]}' `
  http://localhost:8000/posts
Invoke-RestMethod -Method Post http://localhost:8000/posts/$($post.id)/embedding
Invoke-RestMethod -Method Post http://localhost:8000/images/{image_id}/embedding
Invoke-RestMethod 'http://localhost:8000/posts/{post_id}/image-candidates?top_k=5'
Invoke-RestMethod -Method Post 'http://localhost:8000/posts/{post_id}/recommendations?top_k=5'
```

Both resource types use `sentence-transformers/all-MiniLM-L6-v2` pinned to model
revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`, 384 dimensions, and L2
normalization. The local
provider is loaded lazily. Normal tests override it with a deterministic fake and
never download a model. A SHA-256 hash of the centralized semantic text allows an
unchanged resource/model/version to reuse its row without another provider call;
changed content updates that row, while a changed compatible model/version creates
a separately constrained row. Each actual embedding call is logged with provider
`local`, operation `embedding_generate`, latency/status, and estimated cost `0`.

Low-confidence image metadata remains `flagged` and is eligible for embedding so
it can support later observability experiments. Embedding does not make it
trusted; the mismatch guard rejects it. Phase 6 uses explicit embedding
endpoints rather than changing the approved Phase 5 vision-job semantics.

`GET /posts/{post_id}/image-candidates?top_k=5` performs an exact pgvector cosine
query for the configured model/revision/dimension. Pgvector's cosine distance is
ordered ascending and exposed as `similarity_score = 1 - cosine_distance`, so a
higher API score always means a closer vector. Ties use ascending image UUID.
`top_k` is bounded from 1 through 20, and the SQL query itself applies the limit.

Candidates include their subject, category, caption, tags, vision confidence, and
low-confidence flag. Low-confidence rows remain visible because this endpoint is
retrieval only. Mixed-version libraries rank compatible embeddings and exclude
incompatible rows; a library containing only incompatible image embeddings
returns `409`. Missing or schema-invalid metadata is excluded from results.

**Phase 7 candidates are not recommendations.** Raw retrieval may rank a wolf
highly for a fox article because the concepts are semantically related. Phase 8's
`POST /posts/{post_id}/recommendations?top_k=5` evaluates those same ranked rows
without invoking any provider. It rejects hard subject/category conflicts,
invalid or low-confidence metadata, missing required tags, and scores below the
versioned provisional thresholds. It recommends the first accepted rank; it never
falls back to the closest rejected image.

For example, raw retrieval can return gray wolf at `0.93` before red fox at
`0.90`. Guarded recommendation records the wolf as `SUBJECT_MISMATCH` and selects
the fox. If only wolf and dog are available, the response is
`NO_CONFIDENT_MATCH`, with a readable reason for every rejected candidate. The
aliases `red fox`, `red_fox`, and `Vulpes vulpes` normalize to the same centralized
subject concept.

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
