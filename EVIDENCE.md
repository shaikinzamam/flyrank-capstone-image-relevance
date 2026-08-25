# Definition-of-Done Evidence

Every item starts as **Pending**. Evidence will be added only after the corresponding command, test, request, log, or evaluation has actually been produced.

## Phase 2 walking-skeleton verification

These checks establish infrastructure only and do not complete the feature-level Definition of Done below.

- `GET /health` returned `{"status":"ok"}` from the Docker API.
- `GET /ready` returned `{"status":"ready","database":"reachable"}` after a real `SELECT 1`.
- Docker reported both `db` and `api` as healthy.
- PostgreSQL reported pgvector `0.8.6` and Alembic revision `0001`.
- `pytest` under containerized Python 3.12.14: `3 passed in 0.09s`.

## Phase 3 secure-ingestion verification

- `POST /images` accepted decoded JPEG and PNG fixtures and returned `201` with status `uploaded`.
- Unsupported MIME types, fake JPEG bytes, MIME/decoded-format disagreement, and oversized bodies returned clean 4xx responses.
- A byte-identical second upload returned `409`; automated checks confirmed one database row and one stored file.
- `GET /images` and `GET /images/{image_id}` returned persisted asset metadata; an unknown UUID returned `404`.
- PostgreSQL applied Alembic revision `0002`, including the `image_assets` table, status/size constraints, and unique SHA-256 index.
- `alembic check` reported `No new upgrade operations detected.`
- Docker reported both `db` and `api` healthy. Live upload, list, detail, duplicate, row, and file checks succeeded.
- `pytest` under containerized Python 3.12.14: `14 passed in 0.49s` on the final rebuild.

## Phase 8 guarded-recommendation verification

- Local deterministic suite: `77 passed, 4 PostgreSQL-only tests skipped`.
- PostgreSQL-enabled suite: `81 passed`, including the persisted fox-over-wolf
  recommendation test against real pgvector ranking.
- Final Python 3.12 container suite: `77 passed, 4 PostgreSQL-only tests skipped
  in 8.03s`.
- Alembic `0007` adds required post tags, recommendation runs, candidate decisions,
  constraints, indexes, and foreign keys. Live upgrade and `alembic check` passed.
- A disposable PostgreSQL database passed clean upgrade, `0007 -> 0006` downgrade,
  re-upgrade, and drift check; it was then removed and absence verified.
- Direct deterministic output: gray wolf `0.93` was `SUBJECT_MISMATCH`, red fox
  `0.90` was `ACCEPTED` at rank 2, and wolf/dog-only input returned
  `NO_CONFIDENT_MATCH`.
- Rebuilt Compose API/database were healthy and the worker was running.

## Phase 9 labeled-evaluation verification

- Baseline command output: 10 examples; 3 eligible; 3 correct top-1; 0 incorrect
  top-1; 7 correct refusals; 0 incorrect refusals; 0 unsafe acceptances; top-1
  precision `1.0000`.
- Per-example evidence records expected/actual results, selected fixture ID, guard
  decisions, reason codes, similarities, thresholds, and correctness.
- Acceptance evidence includes higher-ranked wolf `0.93 -> SUBJECT_MISMATCH`, fox
  rank 2 `0.90 -> ACCEPTED`, `Vulpes vulpes -> red fox`, no-suitable-image refusal,
  and low-confidence fox `0.54 -> LOW_CONFIDENCE`.
- Generated JSON lives at ignored `backend/artifacts/evaluation/latest.json`; the
  full report is also durably stored in `evaluation_runs`.
- Automated results: local `85 passed, 5 skipped`; PostgreSQL-enabled `90 passed`;
  the PostgreSQL test inspects all ten persisted per-example reports.
- Final Python 3.12 container suite: `85 passed, 5 PostgreSQL-only tests skipped
  in 13.32s`.
- Alembic `0008` passed live upgrade and drift checks plus disposable clean upgrade,
  downgrade to `0007`, re-upgrade, and verified cleanup.
- Live `POST /evaluation/run`, `GET /evaluation/latest`, and by-ID retrieval agreed
  on the same run and measured metrics.

## Phase 10 guarded-review verification

- Local suite: `92 passed, 5 PostgreSQL-only tests skipped in 13.16s`.
- Fully enabled PostgreSQL suite: `97 passed in 13.77s`, including append-only
  review persistence and immutable recommendation evidence in PostgreSQL.
- Final Python 3.12 container suite: `92 passed, 5 PostgreSQL-only tests skipped
  in 13.35s`.
- Live database upgraded forward only from `0008` to `0009`; `alembic check`
  reported no drift. A disposable PostgreSQL database passed clean upgrade,
  `0009 -> 0008` downgrade, re-upgrade, and drift check, then was removed.
- Live HTTP probe inspected a red fox at similarity `0.90`, confidence `0.95`,
  guard `ACCEPTED`, and review `pending`; approval changed review to `approved`
  without changing evidence. A later rejection produced retained history
  `[approved, rejected]`.
- Live gray-wolf approval returned `409` for `SUBJECT_MISMATCH`. The uniquely
  identified live fixture and temporary SQL file were removed afterward.
- Evaluation regression output remained top-1 precision `1.0000` with zero unsafe
  acceptances. Rebuilt API/PostgreSQL were healthy and the worker was restored.

## Phase 11 Next.js frontend verification

- Pinned Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, and Motion;
  `npm install` audited 472 packages with zero vulnerabilities.
- Ten focused UI checks cover landing content, typed image cards, rank order,
  guard rejection, safe refusal, allowed/blocked review actions, API metrics,
  human-readable errors, and reduced-motion tilt logic.
- Strict TypeScript, ESLint, and the production build pass. Static and dynamic
  page routes compile successfully without remote font downloads.
- Added validated image content, composed detail reads, and explicit local CORS.
  Backend local suite passed `96` tests; fully enabled PostgreSQL passed `101`.
- Rebuilt Python 3.12 API image passed `96` tests with the five explicitly gated
  PostgreSQL tests skipped; no Alembic drift was detected.
- Live `/`, `/images`, `/match`, `/evaluation`, and dynamic review routes returned
  `200`. Image detail/content returned metadata and validated PNG bytes with
  `nosniff`; CORS returned only the configured origin.
- Headless-browser responsive checks covered 375, 768, 1024, and 1440 pixel widths;
  the mobile pass caught and fixed 3D-layer horizontal overflow.
- Docker built the standalone Next.js image and reported database, API, and
  frontend healthy; the worker is restored after database concurrency tests.

## AI processing

- [x] **Phase 4 evidence — Structured output:** Gemini is isolated behind `VisionProvider`; all returned JSON is validated locally by strict Pydantic rules before the single metadata row is inserted or replaced. Deterministic tests reject malformed JSON, missing fields, invalid confidence, blank tags, unknown taxonomy values, and inconsistent taxonomy combinations; the schema also forbids extra fields.
- [x] **Phase 4 evidence — Confidence policy:** The configurable provisional threshold flags low-confidence metadata in both `is_low_confidence` and `metadata_status`, and the API exposes both fields.
- [x] **Phase 5 evidence — Background processing:** `POST /images/process` durably creates batch jobs and returns `202`; a separate worker claims leased PostgreSQL items, applies bounded transient retries, recovers expired leases, and reports completed, partial-error, or failed outcomes.
- [x] **Phase 6 evidence — Full AI-call accounting:** Vision attempts retain
  Phase 4/5 accounting. Every actual local embedding call records its resource,
  provider/model, operation, outcome, latency, retry count, and zero estimated cost;
  tests cover successful, invalid-vector, and provider-failure logs.

## Matching system

- [x] **Phase 6 evidence — Stored embeddings:** Image and post vectors round-trip
  through PostgreSQL `vector(384)` columns with model/version/dimension/source-hash
  metadata and uniqueness constraints.
- [x] **Phase 7 evidence — Ranked candidates:** The post candidate endpoint uses
  exact pgvector cosine distance, converts it to descending similarity, limits in
  SQL, and returns typed metadata snapshots with deterministic UUID tie handling.
- [x] **Phase 8 evidence — Guarded suggestions:** `POST
  /posts/{post_id}/recommendations` evaluates ranked candidates and persists a
  versioned run plus every accepted/rejected decision.
- [x] **Phase 8 evidence — Equivalent concepts:** Deterministic tests prove that
  `red fox`, `red_fox`, and `Vulpes vulpes` normalize to the same concept.

## Safety layer

- [x] **Phase 8 evidence — Fox/wolf rejection:** A forced `0.93` wolf at rank 1
  is persisted as `SUBJECT_MISMATCH`; the `0.90` fox at rank 2 is recommended.
- [x] **Phase 8 evidence — Explanations:** Every candidate decision contains a
  stable reason code and a human-readable explanation.
- [x] **Phase 8 evidence — Safe refusal:** Wolf/dog-only candidates return and
  persist `NO_CONFIDENT_MATCH`; no closest-candidate fallback exists.

## Backend

- [x] **Phase 10 evidence — Review persistence:** Migration `0009` adds constrained,
  indexed, append-only reviews with a recommendation foreign key and nullable
  future reviewer identity.
- [ ] **Pending — API validation:** Endpoint input is validated and bad requests produce clean 4xx responses.
- [x] **Phase 10 evidence — Review workflow:** Typed endpoints inspect evidence,
  approve/reject accepted candidates, persist comments, expose state/history, and
  reject safety-boundary bypasses with `409`.
- [ ] **Pending — Authorization:** Minimum real authentication and authorization protect non-public endpoints.
- [ ] **Pending — Tenant isolation:** Cross-workspace access is prevented and tested.
- [x] **Phase 5 evidence — Idempotency:** Reusing an idempotency key with the same image set returns the same job; using it with a different set returns `409`. Job/image uniqueness and metadata upsert constraints prevent duplicate durable rows.
- [x] **Phase 5 evidence — Failure handling:** Transient failures retry with capped exponential backoff; permanent and exhausted failures are visible on items and aggregate into job terminal status and failure summary. Expired leases are reclaimable.
- [x] **Phase 5 evidence — Vision budget guard:** A PostgreSQL-serialized total-demo budget reservation runs before provider calls; deterministic tests prove exhaustion prevents the provider invocation. Embedding budget accounting remains future work.

## Quality and documentation

- [x] **Phase 4 evidence — Schema tests:** The deterministic suite covers valid metadata, malformed output, required fields, confidence bounds, blank/empty tags, collection normalization, taxonomy rejection, low-confidence flags, persistence, state transitions, provider timeout/failure, missing images, idempotent reuse, and explicit replacement.
- [x] **Phase 8 evidence — Mismatch tests:** Automated tests cover forced
  fox-versus-wolf rejection, decision order, low confidence/similarity, category,
  required tags, invalid metadata, explanations, refusal, persistence, and no
  provider/log calls.
- [ ] **Partial — Matching tests:** Automated tests cover deterministic guard
  behavior and equivalent concepts; the Phase 9 labeled baseline now covers all
  declared matching cases, while broader corpus accuracy remains future work.
- [x] **Phase 5 evidence — Resilience tests:** Tests cover provider failure, successful retry, permanent failure, exhaustion, active-lease exclusion, expired-lease recovery, idempotent job requests, budget denial, inaccessible storage, and real PostgreSQL concurrent claiming.
- [x] **Phase 6 evidence — Embedding tests:** Deterministic tests cover semantic
  text, image/post persistence, reuse and regeneration, compatible version changes,
  dimensions/non-finite rejection, missing resources/metadata, low confidence,
  provider failure, zero-cost logs, and a real PostgreSQL pgvector round trip.
- [x] **Phase 7 evidence — Retrieval tests:** Deterministic API tests cover scores,
  order, limits, missing state, compatibility, low-confidence visibility, metadata,
  corrupt-metadata exclusion, ties, and no false AI logs. A PostgreSQL integration
  test proves fox/wolf/dog ordering with known 384-dimensional vectors.
- [x] **Phase 9 evidence — Evaluation:** `evaluation-v1` contains ten explicit,
  human-readable label records. The actual application pipeline produced 3 correct
  top-1 recommendations, 0 incorrect top-1 recommendations, 7 correct refusals,
  0 incorrect refusals, 10 correct unsafe-candidate rejections, and 0 unsafe
  acceptances under unchanged `phase8-v1`.
- [x] **Phase 9 evidence — README metric:** CLI output and README both report
  top-1 precision `1.0000`, defined as `3 / (3 + 0)` issued recommendations.
- [x] **Phase 10 evidence — Review tests:** Tests prove pending, approve, reject,
  comments, idempotent retry, conflicting append-only history, missing `404`,
  rejected-candidate `409`, immutable evidence, no provider/log calls, and no
  approvable candidate for `NO_CONFIDENT_MATCH`.
- [ ] **Pending — Reproducible setup:** A clean machine can run and seed the application using documented commands.
- [ ] **Pending — Submission pack:** All required files are complete and the architecture diagram is current.

## Acceptance probes

- [ ] **Pending — Probe 1:** Batch processing gives every corpus image schema-valid metadata and flags at least one low-confidence result.
- [ ] **Pending — Probe 2:** A red-fox article ranks a fox first and ranks wolf and dog clearly lower.
- [x] **Phase 8 evidence — Probe 3:** A forced higher-ranked wolf is rejected with
  `SUBJECT_MISMATCH` and an expected-red-fox/detected-gray-wolf explanation.
- [x] **Phase 8 evidence — Probe 4:** A post with only wolf and dog returns
  `NO_CONFIDENT_MATCH` and per-candidate reasons.
- [x] **Phase 9 evidence — Probe 5:** `python -m scripts.evaluate` reports dataset
  `evaluation-v1`, 10 examples, and top-1 precision `1.0000`, matching README.
- [ ] **Pending — Probe 6:** Every vision and embedding call has a corresponding cost-log entry.
