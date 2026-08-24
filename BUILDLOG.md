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
