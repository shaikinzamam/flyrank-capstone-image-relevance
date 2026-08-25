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

## 2026-08-24 — Phase 7 semantic image retrieval

### AI assistance

- Used Codex to implement the retrieval repository/service boundary, typed
  candidate API, deterministic tests, real pgvector ranking proof, and truthful
  architecture/evidence updates.

### Decisions

- Add `GET /posts/{post_id}/image-candidates?top_k=5`, with `top_k` constrained
  to 1–20. It returns raw candidates, never recommendations or guard decisions.
- Use pgvector cosine distance (`<=>`) ordered ascending and expose
  `similarity_score = 1 - cosine_distance`; higher response values are better.
- Filter by exact model, pinned revision, and 384 dimensions in SQL. Rank compatible
  rows in a mixed library, but return `409` when embeddings exist and none match.
- Keep low-confidence metadata visible and flagged. Exclude missing metadata in the
  repository join and schema-invalid metadata in the service rather than returning
  corrupt candidate snapshots.
- Resolve equal distances by ascending image UUID. Use exact search and SQL `LIMIT`;
  do not add HNSW, IVFFlat, FAISS, alias logic, or Python production ranking.
- Retain a Python cosine fallback only for the SQLite test dialect. Production and
  PostgreSQL integration paths execute the pgvector query.
- Do not create AI call logs for retrieval because it invokes no provider.

### Verification performed

- Initial local Phase 2–7 suite: `64 passed, 2 PostgreSQL-only tests skipped in 4.05s`.
- PostgreSQL-enabled host suite: `67 passed in 6.23s`.
- Rebuilt Python 3.12 container suite: `67 passed in 3.93s`.
- Real PostgreSQL known-vector ranking returned fox `0.998618`, wolf `0.919145`,
  and dog `0.110432`, proving raw retrieval order but not safety.
- A live API probe returned the same fox/wolf/dog order with complete metadata and
  the low-confidence wolf flag. Its isolated rows were deleted and absence verified.
- Live `/health` and `/ready` succeeded; API/PostgreSQL were healthy and the worker
  was running. The candidate route returned typed `404` behavior for a missing post.

### Problems encountered

- The first live fixture command used JSON text whose quoting was split by the
  Windows/Docker command boundary. PostgreSQL rejected the statement before any
  insert. A zero-row check confirmed atomic failure; the retry used SQL JSON
  constructors, succeeded, and its fixtures were removed after the probe.

### Still not done

- The mismatch guard, final recommendations/refusal, review workflow, evaluation,
  frontend, and Phase 8+ work remain unimplemented.

## 2026-08-24 — Phase 8 deterministic guarded recommendations

### Decisions

- Keep `GET /posts/{post_id}/image-candidates` unchanged as raw semantic retrieval;
  add `POST /posts/{post_id}/recommendations` as a separate guarded operation.
- Implement a pure `MismatchGuard` with stable codes and strict order: invalid
  metadata, low confidence/flag, subject mismatch, category mismatch, required tag,
  low similarity, then accepted.
- Normalize subject aliases centrally. `red fox`, `red_fox`, and `Vulpes vulpes`
  resolve to `red_fox`; broad category equality cannot override subject conflict.
- Centralize provisional `0.70` similarity and vision-confidence thresholds under
  config version `phase8-v1`; defer threshold tuning and metrics to Phase 9.
- Add the smallest explicit post concept field, `required_tags`, without automatic
  extraction. Match normalized required values against candidate vision tags.
- Persist a run and every candidate decision/signal. Do not add review fields,
  invoke providers, create synthetic AI logs, rerank, or fall back to rejected rows.

### Verification performed

- Deterministic local suite: `77 passed, 4 skipped` (the skipped cases require
  explicitly enabled PostgreSQL).
- PostgreSQL-enabled host suite with the worker paused to isolate its queue fixture:
  `81 passed in 4.35s`, including persisted Phase 8 decisions through real pgvector.
- Final Python 3.12 container suite: `77 passed, 4 skipped in 8.03s`.
- Live dev database upgraded from `0006` to `0007`; `alembic current` reported
  `0007 (head)` and `alembic check` reported no new upgrade operations.
- A verified-new disposable PostgreSQL database completed clean install to head,
  downgrade `0007 -> 0006`, re-upgrade, and drift check, then was removed and its
  absence verified. The live dev database was never downgraded.
- The pure direct demo returned wolf `0.93 -> SUBJECT_MISMATCH`, fox
  `0.90 -> ACCEPTED` at rank 2, and a wolf/dog-only `NO_CONFIDENT_MATCH`.
- Rebuilt Compose API and database were healthy; the worker was restored and
  running. Compilation and `git diff --check` succeeded.

### Problems encountered

- The first test command looked for `.venv` under `backend`; the repository virtual
  environment is one level above. The corrected interpreter ran successfully.
- An early no-provider-log assertion counted the pre-existing vision/embedding logs,
  and a fixture reused byte-identical fox pixels. The tests now compare call-log
  count before/after recommendation and use a distinct image fixture.
- A live fixed-ID SQL probe was rejected because it was not sufficiently isolated
  from shared dev data. It was not retried; the direct evidence instead uses the
  reproducible in-memory demo plus SQLite API and PostgreSQL persistence tests.

### Still not done

- Evaluation metrics/threshold tuning, human review, frontend, and Phase 9+ remain
  intentionally unimplemented.

## 2026-08-25 — Phase 9 labeled deterministic evaluation

### Decisions

- Replace placeholder labels with `evaluation-v1`: ten explicit cases covering
  direct fox, scientific alias, direct wolf, forced wolf/dog hard negatives, no
  suitable image, low confidence, low similarity, required tag, and category.
- Run each example in a separate in-memory database through actual embedding,
  retrieval, guard, and recommendation services. Persist only the report in the
  normal database, preventing evaluation corpus pollution.
- Define top-1 precision as correct acceptable issued recommendations divided by
  all issued recommendations. Keep correct/incorrect refusals separate. The local
  materials and public search did not expose the PDF's mathematical wording, so
  the interpretation is explicit.
- Add `EvaluationRun`, CLI output plus ignored JSON artifact, and minimal run/latest/
  by-ID API endpoints. Store complete per-example evidence in `report_json`.
- Preserve baseline `phase8-v1` thresholds (`0.70` similarity and confidence).
  No alternative threshold was tested or adopted.

### Baseline result

- Dataset `evaluation-v1`: 10 examples, 3 eligible recommendation examples.
- Correct/incorrect top-1: `3/0`; correct/incorrect refusals: `7/0`.
- Correct unsafe-candidate rejections: `10`; unsafe acceptances: `0`.
- Top-1 precision, safe acceptance precision, and unsafe rejection recall: `1.0000`.
- No per-example failures occurred. This is a small deterministic acceptance set,
  not evidence of general-world model performance.

### Verification performed

- Final local suite: `85 passed, 5 PostgreSQL-only tests skipped in 10.97s`.
- PostgreSQL-enabled complete suite: `90 passed in 14.39s`; a final focused
  PostgreSQL evaluation persistence rerun also passed.
- Final Python 3.12 container suite: `85 passed, 5 PostgreSQL-only tests skipped
  in 13.32s`.
- CLI persisted a report and printed evaluator `phase9-v1`, dataset
  `evaluation-v1`, matching config `phase8-v1`, and precision `1.0000`.
- Live evaluation API run/latest/by-ID responses agreed and returned the five
  required acceptance-probe records with complete candidate evidence.
- Docker API/PostgreSQL were healthy, the worker was running, and live `/health`
  plus database-backed `/ready` returned `ok`/`reachable`.
- Live database upgraded only from `0007` to `0008`; drift check passed. A
  disposable database passed clean upgrade, `0008 -> 0007` downgrade, re-upgrade,
  and drift check before verified removal.

### Problems encountered

- The first migration command stalled because Docker Desktop was no longer running
  after the overnight session boundary. It was interrupted without DDL output,
  Docker was restarted, PostgreSQL became healthy, and live upgrade `0007 -> 0008`
  plus drift check then succeeded.
- The first container test used a host-relative test path and looked for `/data`
  instead of the configured `/app/data` mount. Application CLI/API resolution was
  already correct; tests now use `EVALUATION_DATASET_PATH`, and the rebuilt suite
  passes. The cold rebuild also had to refill its dependency cache after the base
  image digest changed.

### Still not done

- Human review workflow, frontend, broad licensed corpus evaluation, authentication,
  and Phase 10+ remain intentionally unimplemented.

## 2026-08-25 — Phase 10 guarded recommendation review

### Decisions

- Add a separate append-only `recommendation_reviews` table so guard evidence and
  human editorial judgment remain independent and inspectable.
- Derive `pending` with no review. Exact retries are idempotent; a different
  decision or comment appends a record and the latest record becomes current.
- Permit approve/reject only for persisted `ACCEPTED` candidates. Rejected
  candidates remain inspectable but return `409` for human actions.
- Keep `reviewer_id` nullable until authentication exists and do not accept it in
  the public request body.
- Add detail, approve, reject, and history endpoints without provider calls,
  threshold/evaluation changes, or frontend work.

### Verification performed

- Local suite: `92 passed, 5 PostgreSQL-only tests skipped in 13.16s`.
- Fully enabled PostgreSQL suite: `97 passed in 13.77s`; the live worker was
  paused during the claim-concurrency test and restored afterward.
- Final Python 3.12 container suite: `92 passed, 5 skipped in 13.35s`.
- Live migration `0008 -> 0009`, final drift check, and disposable clean upgrade /
  downgrade to `0008` / re-upgrade all passed. The disposable database was removed.
- Live HTTP probes proved pending, approve, reject, retained history, immutable
  evidence, and mismatch approval blocked with `409`; exact fixtures were removed.
- Evaluation regression remained top-1 precision `1.0000`, unsafe acceptances `0`.
- Rebuilt Compose API and PostgreSQL were healthy and the worker was running.
- Focused tests cover inspection, state transitions, comments, retry policy,
  append-only history, immutable evidence, clean `404`/`409`, safe refusal, and no
  AI calls/logs.

### Problems encountered

- One focused assertion expected a scientific alias from another fixture; the
  shared fixture correctly stores `red fox`, so the test expectation was aligned.
- The first PostgreSQL command omitted `DATABASE_URL`; rerunning with the same live
  URL used by Alembic fixed the environment. Adding a review commit initially
  expired earlier ORM test objects; required evidence was captured before commit.
- The running worker raced the PostgreSQL claim test; it was temporarily stopped
  for the isolated rerun and then restored.
- Windows split an inline SQL probe and PostgreSQL rejected the malformed JSON;
  the transaction rolled back. An exact temporary SQL file made the probe
  deterministic and was removed after its fixture cleanup.

### Still not done

- Frontend, authentication, workspace isolation, notifications, roles, approval
  chains, and collaboration remain intentionally out of scope.

## 2026-08-25 — Phase 11 Next.js product interface

### Decisions

- Build an App Router frontend with strict TypeScript, Tailwind CSS, Motion,
  native hooks, and a centralized typed fetch client; add no state framework.
- Use restrained CSS perspective/rotation/translation and Motion springs. Disable
  pointer tilt for touch/reduced-motion users; keep Three.js/WebGL excluded.
- Add only browser integration reads to FastAPI: validated image bytes, composed
  image/embedding details, recommendation IDs, and configured local CORS.
- Keep semantic candidates visually separate from guarded results. Never show a
  rejected candidate as usable or expose approval when prohibited.
- Add a non-root standalone Next.js production service to Docker Compose.

### Verification performed

- Frontend dependencies: 472 packages audited, zero vulnerabilities.
- Vitest: 10 focused UI/component tests passed.
- Strict TypeScript and ESLint passed; the production build emitted all routes.
- Backend local regression: `96 passed, 5 skipped`; fully enabled PostgreSQL:
  `101 passed`.
- Rebuilt Python 3.12 API container: `96 passed, 5 skipped in 15.25s`.
- Live four-service route probes and validated image-content/CORS checks passed.
  Responsive screenshots covered 375/768/1024/1440 widths.

### Problems encountered

- Windows npm shims broke on the workspace `&`; scripts now invoke pinned Node
  entrypoints directly while preserving normal `npm run` commands.
- Vitest initially retained DOM between tests; explicit cleanup fixed isolation.
- Next's lint rule misclassified awaited loader callbacks as synchronous effect
  updates; narrow documented suppressions cover only those async loaders.
- `next/font` could not download Google fonts during the restricted build; a
  system-font stack removed that network dependency.
- Docker Desktop was stopped and was restarted for container verification.
- Resumed Docker had subsecond host/container clock skew; the PostgreSQL claim
  fixture now uses an explicit already-available timestamp without changing worker
  logic. Mobile screenshots also exposed and fixed 3D horizontal overflow.

### Still not done

- At the Phase 11 close, final hardening was still pending; authentication,
  workspace isolation, notifications, roles, and collaboration remained out of
  scope and are still not claimed.

## 2026-08-25 — Phase 12 final hardening and demo readiness

### Audits and fixes

- Replaced stale Phase 2 `capstone.yaml` seed/status placeholders with the exact
  verified run, seed, test, URL, and endpoint values.
- Added a prefix-scoped, rerunnable synthetic demo seed. It creates visibly
  labeled generated images and known vectors without downloading a model or
  claiming third-party image provenance; it persists matching, refusal, review,
  and evaluation evidence.
- Closed a stored-image integrity gap by comparing the served file's actual byte
  size with the trusted database value in addition to path, maximum size, hash,
  MIME, and decode checks. Added a regression test.
- Rejected wildcard/malformed CORS origins at configuration load, retained
  credentials-off behavior, and passed the explicit origin into Compose.
- Bounded post bodies at 50,000 characters and added clean malformed-UUID and
  oversized-body checks. No guard threshold, label, or recommendation rule changed.
- Added a no-candidate retrieval state, clearer missing evaluation/recommendation
  errors, live progress announcements, input bounds/hints, pointer-cancel and
  keyboard-blur tilt resets, and narrower mobile candidate grids.
- Added axe-core checks. Axe found skipped heading levels in decorative hero cards;
  converting those labels from headings to styled text fixed the semantic issue.

### Verification performed

- Local backend: `102 passed, 5 skipped in 17.64s`; PostgreSQL-enabled: `107
  passed in 17.63s`; Python 3.12 container: `102 passed, 5 skipped in 17.19s`.
- Frontend: 11 tests including axe passed; strict TypeScript, ESLint, and the
  optimized Next.js production build passed with all six product routes.
- Exact demo seed proved wolf `0.93 -> SUBJECT_MISMATCH`, fox `0.90 -> ACCEPTED`,
  dog `0.82`, review transitions, blocked rejected approval (`409`), and a
  wolf/dog-only `NO_CONFIDENT_MATCH`.
- A second exact seed invocation reproduced the manifest and confirmed the
  prefix-scoped cleanup is rerunnable without touching unrelated records.
- `evaluation-v1` remained 10/3/0/7/0 with zero unsafe acceptances and precision
  `1.0000`. Alembic remained at `0009` with no drift.
- A volume-preserving clean Compose down/up-build passed. Database/API/frontend
  were healthy, worker running, primary routes `200`, validated image bytes `200`,
  malformed UUID `422`, and explicit-origin CORS preflight `200`.
- Headless visual checks covered tablet/laptop/desktop widths. Edge's ordinary
  screenshot mode has a minimum window width, so the 375 pass used an explicit
  375-CSS-pixel DevTools device metric: all six pages reported content width at or
  below the viewport, the mobile menu was visible, and no horizontal overflow
  occurred. Touch fallbacks and overflow constraints were also code-audited.
- Runtime logs were concise normal startup/access output with no secrets, stack
  traces, repeated warnings, or fake success messages.

### Problems encountered

- The first seed post matched an image-vector substring in `Expected subject`;
  requiring image semantic text to begin with `Subject:` restored the exact known
  ranking and received a regression test.
- The seed report initially read evaluation `id`; the public schema correctly
  calls it `run_id`. The serializer was corrected and the exact command rerun.
- Combining elevated Docker operations with local pytest created an inaccessible
  Windows temp directory. PostgreSQL tests themselves passed, and the complete
  matrix was rerun normally with an explicit repository-local temporary path;
  generated temporary directories were removed and the worker restored.

### Intentionally not added

- No authentication, tenancy, object storage, Kubernetes, Redis, Celery, GraphQL,
  Three.js, new production model provider, or Phase 13 packaging work.
