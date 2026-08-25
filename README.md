# Image Relevance & Auto-Tagging

## AI Image Understanding & Content Matching Engine

## Project

This FlyRank Backend AI Engineering capstone will build a trustworthy service that understands a small image library, generates structured metadata, and recommends images for articles only when the available evidence is strong enough.

The project is currently at **Phase 12 final hardening**. The complete backend and
responsive frontend have a reproducible synthetic demo seed, verified evaluator
commands, explicit security/configuration boundaries, and a final test matrix.

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
- Next.js App Router, TypeScript, Tailwind CSS, Motion, and CSS 3D transforms

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
- Phase 9 labeled deterministic evaluation and measured metrics: implemented
- Phase 10 recommendation inspection and guarded human review: implemented
- Phase 11 responsive Next.js product interface: implemented
- Phase 12 hardening and deterministic demo readiness: implemented
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
- Licensed photographic corpus collection: not started; the demo uses clearly
  labeled, programmatically generated synthetic images with no licensing claim
- Evaluation execution: implemented with a versioned deterministic baseline
- Frontend landing, images, matching, review, and evaluation routes: implemented

## Setup

### Prerequisites

- Git
- Docker Desktop or Docker Engine with Compose v2
- At least 8 GB RAM available to Docker for the Python/ML image build
- Python 3.12 and Node.js 24 only when running services outside Docker

Docker is the reproducible path; global Python and Node packages are not used.
From a clean machine:

```powershell
git clone <repository-url>
cd "Image Relevance & Auto-Tagging"
Copy-Item .env.example .env
# Replace POSTGRES_PASSWORD before any non-local deployment.
docker compose up --build -d
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api python -m scripts.seed
docker compose exec -T api pytest
```

The API entrypoint automatically runs `alembic upgrade head` before Uvicorn, so
the explicit `alembic current` command verifies migration state rather than
applying a second migration. Open `http://localhost:3000`; the API is available
at `http://localhost:8000`.

Verify health independently:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

Expected responses are `{"status":"ok"}` and
`{"status":"ready","database":"reachable"}`.

### Environment policy

Every application variable is listed in [.env.example](.env.example). Compose
defaults to the credential-free deterministic vision fixture. Gemini is opt-in:
set `VISION_PROVIDER=gemini`, `GEMINI_API_KEY`, a conservative per-call estimate,
and a total budget. `NEXT_PUBLIC_API_BASE_URL` is intentionally public and is
baked into the browser bundle at frontend build time; database credentials and
Gemini keys are server-only. `CORS_ALLOWED_ORIGINS` is a comma-separated explicit
HTTP(S) origin list; wildcard origins are rejected and credentials are disabled.

For production, replace the development database password, restrict published
ports/origins, terminate TLS at a trusted proxy, use durable object storage, and
add authentication/workspace authorization. Those deployment capabilities are
not claimed by this capstone.

Open `http://localhost:3000` for the frontend. Browser API calls use
`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`); allowed browser
origins are controlled by backend `CORS_ALLOWED_ORIGINS`.

For standalone frontend development:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm.cmd install
npm.cmd run dev
```

Standalone backend development requires Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m pytest
```

Production UI values come from backend responses. Image previews use
`GET /images/{image_id}/content`, which validates controlled path, MIME, hash,
size, and decoded content without exposing host filesystem paths.

Visual depth uses restrained CSS perspective, rotation, and translation animated
with Motion springs. This is smaller and easier to make accessible than WebGL;
Three.js and React Three Fiber remain excluded.

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

## Human review workflow

`GET /recommendations/{recommendation_id}` exposes the persisted post, candidate
image, rank, similarity, detected/expected subjects, confidence, guard reason,
explanation, and current human state. A guard-accepted candidate starts as
`pending`; `POST /recommendations/{recommendation_id}/approve` and `/reject`
accept an optional JSON `comment`. `GET /recommendations/{recommendation_id}/reviews`
returns append-only history.

An identical retry (same decision, comment, and reviewer) is idempotent. A changed
decision or comment appends a new record and becomes current while older records
remain inspectable. Guard-rejected candidates return `409` for either human action,
so review cannot turn `SUBJECT_MISMATCH` or a `NO_CONFIDENT_MATCH` run into a safe
recommendation. Review never changes the AI evidence and makes no provider call.

Authentication is intentionally deferred. `reviewer_id` is nullable and currently
returned as `null`; a future authenticated boundary will supply it server-side,
not accept a claimed reviewer identity from the request body.

Uploads are streamed with a configured byte limit, hashed with SHA-256, decoded with Pillow, restricted to JPEG/PNG/WEBP, and stored under generated keys in a controlled local directory. A byte-identical upload returns `409 Conflict`; no second database row or file is created. `storage_key` is an opaque relative identifier, not a host filesystem path.

## Evaluation

A versioned labeled set in [data/evaluation.jsonl](data/evaluation.jsonl) covers
direct fox/wolf matches, `Vulpes vulpes`, fox-versus-wolf and dog hard negatives,
no suitable image, low confidence, low similarity, required tags, and category
mismatch. Run the official deterministic baseline from `backend`:

```powershell
..\.venv\Scripts\python.exe -m scripts.evaluate
```

The clean Docker equivalent is:

```powershell
docker compose exec -T api python -m scripts.evaluate
```

The command persists an `EvaluationRun` and writes generated machine-readable
output to the ignored `backend/artifacts/evaluation/latest.json`. Equivalent API
operations are `POST /evaluation/run`, `GET /evaluation/latest`, and
`GET /evaluation/{run_id}`. Evaluation fixtures run in isolated in-memory databases;
only the final structured report enters the normal application database.

### Measured baseline

- Dataset: `evaluation-v1` (10 explicitly labeled examples)
- Evaluator: `phase9-v1`
- Matching configuration: `phase8-v1` (`0.70` similarity, `0.70` confidence)
- Eligible recommendation examples: 3
- Correct top-1 recommendations: 3
- Incorrect top-1 recommendations: 0
- Correct `NO_CONFIDENT_MATCH` outcomes: 7
- Incorrect refusals: 0
- Unsafe acceptances: 0
- **Top-1 precision: `1.0000`**

Top-1 precision is `correct acceptable top-1 recommendations / all issued top-1
recommendations`, or `3 / (3 + 0)`. Refusals are excluded from that denominator
and reported separately, so precision is not being substituted with overall
accuracy. The official PDF's mathematical definition was not available in the
project materials; this standard interpretation is therefore explicit rather
than implied.

This perfect result describes a small deterministic acceptance dataset, not
general-world model quality. Thresholds were not changed after seeing the result.

## Demo scenario

Run this exact deterministic path after the stack is healthy:

```powershell
docker compose exec -T api python -m scripts.seed
```

The command replaces only records whose names use the reserved Phase 12 demo
prefix. It generates three visibly labeled synthetic PNGs, passes them through
the same upload validation and metadata/embedding services, and prints a JSON
manifest. The manifest proves raw rank `gray wolf 0.93`, `red fox 0.90`, and
`domestic dog 0.82`; the guard rejects wolf with `SUBJECT_MISMATCH`, accepts fox,
persists a human review, then temporarily excludes the fox embedding to persist a
wolf/dog-only `NO_CONFIDENT_MATCH`. It also runs and persists `evaluation-v1`.

UI walkthrough, using IDs printed by the seed command:

1. Open `http://localhost:3000/images`; inspect fox, wolf, and dog metadata and
   embedding state. Click a card for validated image bytes and full auto-tags.
2. Open `http://localhost:3000/match` to inspect the guided create → embed → raw
   retrieval → guard workflow. The deterministic raw evidence is also printed by
   the seed manifest so the required ranking never depends on presentation timing.
3. Open `http://localhost:3000/recommendations/<accepted_recommendation_id>`.
   Verify the wolf rejection/fox acceptance evidence, enter a comment, and use
   Reject or Approve; the append-only timeline updates while evidence stays fixed.
4. Open a value from `no_match_recommendation_ids` to verify that a guard-rejected
   candidate has no approval control. The manifest's `no_match_reason` is
   `NO_CONFIDENT_MATCH` for the wolf/dog-only run.
5. Open `http://localhost:3000/evaluation`; verify 10 examples, 3 correct top-1,
   7 correct refusals, 0 unsafe acceptances, and precision `1.0000`.

To demonstrate the durable worker separately, upload a valid local JPEG/PNG/WEBP,
submit its returned UUID to `POST /images/process`, and poll the job commands in
the earlier processing section. The Compose default uses a deterministic fake
vision response and incurs no external cost.

## Limitations

- This is not a general-purpose image search engine and will target approximately 50 images.
- The initial taxonomy covers only a small, documented set of subjects.
- Model confidence is an input signal, not calibrated truth.
- The baseline thresholds have not been tuned and ten deterministic fixtures are
  too small to establish general-world performance.
- Local filesystem image storage is suitable for the capstone but not a distributed production deployment.
- Authentication and workspace isolation are not implemented yet; the image table is intentionally unscoped until that boundary is designed.
- The Phase 4 taxonomy is intentionally limited to red fox, gray wolf, domestic dog, brown bear, and white-tailed deer; out-of-taxonomy classifications are rejected.
- The default `0.70` low-confidence threshold is configurable and provisional until evaluation tunes it.
- The budget guard is a total-demo cap. It atomically reserves the configured conservative estimated cost before every provider attempt; when budgeting is enabled, a missing estimate blocks the call.
- Processing is at-least-once. Lease tokens prevent stale workers from completing reclaimed items, while the unique metadata row makes repeated processing persistence idempotent. A crash after a provider call can still require another billed call after lease recovery.
- The premium frontend is presentation polish, not part of the backend correctness core.
