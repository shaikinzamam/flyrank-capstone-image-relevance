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

## 2026-08-21 — Phase 2 walking skeleton

### AI assistance

- Used Codex to create the FastAPI application factory, system routes, environment-backed settings, SQLAlchemy session factory, Alembic environment, Docker configuration, and endpoint tests.
- Used Codex to run the local and containerized verification commands and inspect the real output.

### Decisions

- Kept `/health` independent of PostgreSQL so it reports whether the API process is alive.
- Made `/ready` execute `SELECT 1` through a readiness service so database availability is tested without putting persistence logic in the route.
- Used dependency overrides in endpoint tests to cover ready and unavailable outcomes deterministically.
- Added a first Alembic revision that enables the `vector` extension but creates no domain tables; domain modeling remains outside Phase 2.
- Used a Python 3.12 slim Docker image because the host currently has Python 3.13. The same tests were run in the Python 3.12 container.
- Constrained Starlette below 1.0 after the first dependency resolution produced a `TestClient` deprecation warning with Starlette 1.6.

### Verification performed

- Local endpoint suite: 3 tests passed on Python 3.13.1.
- Container endpoint suite: 3 tests passed on Python 3.12.14.
- Docker Compose reported healthy PostgreSQL and API containers.
- PostgreSQL reported Alembic revision `0001` and pgvector extension version `0.8.6`.
- Live `/health` and `/ready` requests returned successful JSON responses.

### Problems encountered

- Dependency installation initially failed because sandboxed network access blocked PyPI. It succeeded after the explicit network approval path was used.
- Docker initially could not connect because Docker Desktop was not running. Docker Desktop was started with approval.
- Docker's user config file was not readable in the execution environment. Verification used an isolated temporary Docker CLI config instead.
- The first test run emitted a Starlette `TestClient` deprecation warning. Adding the compatible `starlette>=0.46,<1.0` constraint resolved it; the final test runs were warning-free.

### Still not done

- No authentication, image handling, AI provider, embedding generation, worker, matching, recommendation, evaluation, or frontend feature exists.

## 2026-08-24 - Phase 3 secure image ingestion

### AI assistance

- Used Codex to implement the `ImageAsset` model and migration, local storage adapter, repository/service boundary, thin image routes, and deterministic endpoint tests.
- Used Codex to run local and containerized tests, inspect Alembic drift, and exercise the live API against PostgreSQL and the Docker upload volume.

### Decisions

- Stream uploads to a controlled staging directory while enforcing the configured byte limit and computing SHA-256; do not load the whole request into application memory.
- Accept only declared JPEG, PNG, or WEBP MIME types, then require Pillow's decoded format to agree with the declaration. File extensions do not participate in trust decisions.
- Run both Pillow verification and full pixel decoding, treat decompression-bomb warnings as errors, and enforce a separate pixel-count safety limit.
- Store original filenames only as metadata. Final files use generated names beneath a SHA-256 prefix, and API responses expose only the relative storage key.
- Return `409 Conflict` for byte-identical uploads. A unique SHA-256 database index provides the final concurrency-safe duplicate boundary, and failed inserts remove their staged/promoted files.
- Keep image status `uploaded` in this phase. The broader status constraint anticipates later processing states without implementing a worker.
- Do not add a nullable or placeholder workspace identifier before the authentication and tenant boundary is designed.

### Verification performed

- Local endpoint suite: 14 tests passed on Python 3.13.1.
- Container endpoint suite: 14 tests passed on Python 3.12.14.
- Alembic upgraded PostgreSQL to revision `0002`; `alembic check` reported no new upgrade operations.
- Docker reported healthy PostgreSQL and API containers.
- A live PNG upload returned `201`; list and detail returned the persisted asset; an identical retry returned `409`.
- PostgreSQL contained one verification row and the Docker upload volume contained one corresponding file under an opaque generated key.

### Problems encountered

- Sandboxed dependency installation could not reach PyPI. The approved network path installed Pillow and python-multipart.
- The first persistence test passed a JSON UUID string directly to SQLAlchemy's UUID key type. Parsing it to `UUID` fixed the test; the application persistence path was unchanged.
- The host PowerShell version does not support the newer multipart `-Form` parameter. Direct API verification was rerun successfully with `curl.exe`.

### Still not done

- No authentication, Gemini integration, vision metadata, embeddings, background worker, matching, mismatch guard, recommendations, evaluation, or frontend feature exists.

## 2026-08-24 - Phase 4 vision auto-tagging

### AI assistance

- Used Codex to implement the strict metadata contract, compact taxonomy, Gemini-backed `VisionProvider`, deterministic fake provider, synchronous analysis service, persistence migration, endpoint, and tests.
- Used Codex to verify the current Google Gen AI SDK image-input, JSON-schema, timeout, and retry configuration against official SDK documentation.

### Decisions

- Keep Gemini SDK calls entirely inside `GeminiVisionProvider`; the service accepts only the provider interface and treats every returned value as untrusted.
- Use the documented compact subject taxonomy (`red_fox`, `gray_wolf`, `domestic_dog`, `brown_bear`, and `white_tailed_deer`) and require the human subject and broad category to match the selected taxonomy code.
- Normalize taxonomy strings and collection values to lowercase, trim whitespace, and deduplicate collections while preserving order. Reject extra fields, blank captions/tags, unknown taxonomy values, invalid types, and out-of-range confidence.
- Store exactly one metadata row per image. Ordinary analyze calls reuse it without a provider call; `reprocess=true` updates the same row only after the replacement validates.
- Use a configurable provisional low-confidence threshold (`VISION_LOW_CONFIDENCE_THRESHOLD`, default `0.70`). Low-confidence results complete processing but are explicitly stored and returned as `flagged`.
- Keep the endpoint synchronous for Phase 4. SDK retries are disabled (`attempts=1`), call logs record retry count zero, and durable background execution/retries remain Phase 5 work.
- Persist every attempted provider call with provider, model, operation, outcome, latency, retry count, optional cost, error code, and timestamp. Unknown provider cost remains null rather than being guessed.
- Preserve the last valid metadata if explicit reprocessing fails. First-time failures set the image to `failed`; failed replacement attempts restore `processed` because valid prior metadata still exists.

### Verification performed

- Local full suite on Python 3.13.1: `29 passed in 5.22s` on the final run.
- Container full suite on Python 3.12.14: `29 passed in 1.93s` on the final rebuild.
- PostgreSQL applied Alembic revision `0003`; `alembic check` reported no new upgrade operations.
- Docker reported healthy PostgreSQL and API services; live `/health` and `/ready` returned successful JSON.
- Deterministic endpoint tests exercised accepted, flagged, malformed, invalid, failed, reused, and explicitly reprocessed results without a Gemini key.
- `git diff --check` completed with no whitespace errors (Git emitted only line-ending conversion warnings).

### Problems encountered

- The first local `pytest` command used a system interpreter without SQLAlchemy. Running through the repository `.venv` resolved the environment mismatch.
- Docker CLI access to the user configuration and daemon required the approved elevated path. Verification used an isolated temporary Docker CLI directory, which was removed afterward.

### Still not done

- No live Gemini call was performed because no credential was provided.
- No embeddings, semantic matching, mismatch guard, recommendations, evaluation, frontend, durable background worker, worker retries, or budget enforcement exists.

## 2026-08-24 - Phase 5 durable background processing

### AI assistance

- Used Codex to implement PostgreSQL-backed processing jobs/items, idempotent batch creation, inspection endpoints, a separate worker command, row-lock claiming, leases, retry scheduling, budget reservations, and deterministic worker tests.
- Used Codex to run local and container suites, a real PostgreSQL two-worker concurrency test, migration round trips in disposable PostgreSQL databases, and live Docker queue/recovery probes.

### Decisions

- Return `202 Accepted` from `POST /images/process` after persisting a job and one item per unique requested image. The idempotency key is globally unique and can be reused only for the exact same image set.
- Claim eligible rows with PostgreSQL `FOR UPDATE SKIP LOCKED`, then assign a unique lease token and commit before calling vision. Only the current token can apply an item outcome.
- Configure three attempts by default with capped exponential backoff (`5`, `10`, then terminal failure; maximum delay `300` seconds). Only timeouts, temporary provider failures, and unexpected worker failures retry.
- Treat malformed/schema-invalid output, missing or invalid stored images, provider misconfiguration, and budget denial as permanent.
- Make leases longer than provider timeouts. Expired processing items below their attempt limit are reclaimable; expired final attempts become failed. Metadata remains a one-row upsert under at-least-once execution.
- Use a total-demo vision budget. PostgreSQL advisory locking serializes checks and insertion of a `reserved` call record. The configured conservative estimate counts against the cap even after failure or crash; a missing estimate blocks paid-provider calls when budgeting is enabled.
- Keep the synchronous analyze route deprecated and only for explicit development/debug use. Production processing uses durable jobs and the separate worker.
- Use `ON DELETE RESTRICT` for images referenced by job history so deleting an asset cannot silently remove an item and corrupt job totals.

### Verification performed

- Local Python 3.13.1 suite: `46 passed, 1 PostgreSQL-only test skipped in 8.21s`.
- Container Python 3.12.14 suite with PostgreSQL concurrency enabled: `47 passed in 4.72s`.
- Two simultaneous PostgreSQL sessions produced exactly one claim for a single item.
- Live database reached Alembic `0005 (head)` and `alembic check` reported no new upgrade operations.
- A disposable PostgreSQL database successfully ran `base -> 0005 -> 0003 -> 0005`; it was removed afterward without modifying live job history.
- Docker reported healthy API/database containers and a running separate worker.
- With the worker stopped, a real API job was observed as `pending`; after worker start it reached `completed`, progress `1.0`, one succeeded item, trusted fake metadata, and one zero-cost call record.
- A controlled expired-lease fixture in `processing` was reclaimed after worker restart and completed on attempt two with its lease cleared.

### Problems encountered

- Docker initially passed an empty optional cost estimate as a string, causing settings validation to fail during API startup. Optional numeric settings now normalize an empty environment value to unset.
- Job progress initially stayed `running` because test sessions disable autoflush. Explicit flushes before aggregate counter queries fixed terminal job updates.
- A proposed downgrade of the live local database was blocked because it would delete job history. Migration reversibility was instead verified against uniquely named disposable databases.
- The image foreign key was hardened after the first `0004` application. An additive `0005` migration preserves immutable migration history and changes deletion behavior safely.

### Still not done

- No live Gemini call was performed; Docker verification used the deterministic fake provider.
- No embeddings, semantic matching, mismatch guard, recommendations, evaluation, frontend, or Phase 6 functionality exists.

## 2026-08-24 — Phase 6 embeddings and vector persistence

### AI assistance

- Used Codex to implement the provider-isolated embedding layer, deterministic
  semantic text, post domain/API, pgvector persistence, call accounting,
  migration, tests, and documentation.

### Decisions

- Use `sentence-transformers/all-MiniLM-L6-v2` for images and posts with 384
  dimensions and L2 normalization. Pin model loading and persistence identity to
  Hugging Face revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`.
- Keep sentence-transformers behind `EmbeddingProvider`, load it lazily, and use
  a hash-derived normalized fake so ordinary tests never download a model.
- Add explicit image/post embedding endpoints instead of changing the approved
  Phase 5 vision job. Embedding failures therefore cannot rewrite vision-job
  completion semantics.
- Hash the centralized semantic text with SHA-256. Reuse an unchanged
  resource/model/version row, replace its vector after content changes, and create
  a separate constrained row after a compatible model/version change.
- Permit flagged low-confidence image metadata to be embedded without changing
  its flag. The later mismatch guard remains responsible for rejecting it.
- Validate provider dimensions, vector length, numeric types, and finiteness before
  persistence. Store every actual local call with zero estimated cost and a clear
  `embedding_generate` operation.
- Add exact `vector(384)` columns without FAISS, HNSW, ranking, or recommendations.

### Verification performed

- Final local deterministic suite: `56 passed, 2 PostgreSQL-only tests skipped in 3.53s`.
- Final PostgreSQL-enabled host suite: `58 passed in 5.51s`, including a real pgvector
  384-value round trip and the existing two-worker concurrency test.
- Final rebuilt CPU-only Python 3.12 container suite: `58 passed in 3.77s`; API and
  PostgreSQL were healthy and the separate worker was running afterward.
- Container runtime import check reported sentence-transformers `3.4.1` and
  PyTorch `2.13.0+cpu`. Model weights were intentionally not downloaded.
- Live PostgreSQL reached Alembic `0006`; `alembic check` reported no new upgrade
  operations; both vector columns reported `vector(384)` under pgvector `0.8.6`.
- A uniquely named disposable database completed `base -> 0006 -> 0005 -> 0006`
  and was removed. The live development database was not downgraded.

### Problems encountered

- The first container rebuild selected CUDA-enabled PyTorch packages. It was
  stopped before that unnecessary multi-gigabyte download; the Dockerfile now
  installs PyTorch from the official CPU wheel index before sentence-transformers.
- The first compile command referenced `backend/.venv`; rerunning with the root
  virtual environment succeeded.
- The first PostgreSQL-enabled pytest command omitted `DATABASE_URL`, so its two
  opt-in tests failed before connecting. Exporting the explicit Compose database
  URL produced the final 57-test passing run.

### Still not done

- No real sentence-transformers smoke test has been claimed.
- Semantic ranking, mismatch guard, recommendations, evaluation, review workflow,
  authentication/tenant work, and frontend remain unimplemented.
