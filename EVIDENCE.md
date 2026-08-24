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
  metadata and uniqueness constraints. Ranking remains pending.
- [ ] **Pending — Ranked suggestions:** Posts return ranked image suggestions.
- [ ] **Pending — Equivalent concepts:** Semantic matching demonstrates that `red fox` matches `Vulpes vulpes`.

## Safety layer

- [ ] **Pending — Fox/wolf rejection:** The mismatch guard provably rejects a wolf recommendation for a fox article.
- [ ] **Pending — Explanations:** Rejections contain human-readable explanations.
- [ ] **Pending — Safe refusal:** When no candidate clears the guard, the system returns `No confident match` with reasons.

## Backend

- [ ] **Partial — Persistence:** Migrated models now exist for images, metadata,
  posts, and embeddings. Suggestions and review records remain pending.
- [ ] **Pending — API validation:** Endpoint input is validated and bad requests produce clean 4xx responses.
- [ ] **Pending — Review workflow:** A user can inspect why a suggestion was made and approve or reject it.
- [ ] **Pending — Authorization:** Minimum real authentication and authorization protect non-public endpoints.
- [ ] **Pending — Tenant isolation:** Cross-workspace access is prevented and tested.
- [x] **Phase 5 evidence — Idempotency:** Reusing an idempotency key with the same image set returns the same job; using it with a different set returns `409`. Job/image uniqueness and metadata upsert constraints prevent duplicate durable rows.
- [x] **Phase 5 evidence — Failure handling:** Transient failures retry with capped exponential backoff; permanent and exhausted failures are visible on items and aggregate into job terminal status and failure summary. Expired leases are reclaimable.
- [x] **Phase 5 evidence — Vision budget guard:** A PostgreSQL-serialized total-demo budget reservation runs before provider calls; deterministic tests prove exhaustion prevents the provider invocation. Embedding budget accounting remains future work.

## Quality and documentation

- [x] **Phase 4 evidence — Schema tests:** The deterministic suite covers valid metadata, malformed output, required fields, confidence bounds, blank/empty tags, collection normalization, taxonomy rejection, low-confidence flags, persistence, state transitions, provider timeout/failure, missing images, idempotent reuse, and explicit replacement.
- [ ] **Pending — Mismatch tests:** Automated tests cover the forced fox-versus-wolf rejection.
- [ ] **Pending — Matching tests:** Automated tests cover matching accuracy and equivalent concepts.
- [x] **Phase 5 evidence — Resilience tests:** Tests cover provider failure, successful retry, permanent failure, exhaustion, active-lease exclusion, expired-lease recovery, idempotent job requests, budget denial, inaccessible storage, and real PostgreSQL concurrent claiming.
- [x] **Phase 6 evidence — Embedding tests:** Deterministic tests cover semantic
  text, image/post persistence, reuse and regeneration, compatible version changes,
  dimensions/non-finite rejection, missing resources/metadata, low confidence,
  provider failure, zero-cost logs, and a real PostgreSQL pgvector round trip.
- [ ] **Pending — Evaluation:** A labeled dataset reports a real top-1 precision value.
- [ ] **Pending — README metric:** The measured evaluation value is recorded in `README.md` and matches evaluator output.
- [ ] **Pending — Reproducible setup:** A clean machine can run and seed the application using documented commands.
- [ ] **Pending — Submission pack:** All required files are complete and the architecture diagram is current.

## Acceptance probes

- [ ] **Pending — Probe 1:** Batch processing gives every corpus image schema-valid metadata and flags at least one low-confidence result.
- [ ] **Pending — Probe 2:** A red-fox article ranks a fox first and ranks wolf and dog clearly lower.
- [ ] **Pending — Probe 3:** A forced wolf candidate is rejected with a subject/category mismatch explanation.
- [ ] **Pending — Probe 4:** A post without a suitable image returns `No confident match` and reasons.
- [ ] **Pending — Probe 5:** The evaluation command reports top-1 precision matching the README.
- [ ] **Pending — Probe 6:** Every vision and embedding call has a corresponding cost-log entry.
