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
- [ ] **Pending — Background processing:** Images are processed through a batch background job with retries.
- [ ] **Pending — Full cost accounting:** Phase 4 durably logs each vision attempt, including unknown cost as null; embedding accounting and budget enforcement remain unimplemented.

## Matching system

- [ ] **Pending — Stored embeddings:** Image and post embeddings are persisted, and posts return ranked image suggestions.
- [ ] **Pending — Equivalent concepts:** Semantic matching demonstrates that `red fox` matches `Vulpes vulpes`.

## Safety layer

- [ ] **Pending — Fox/wolf rejection:** The mismatch guard provably rejects a wolf recommendation for a fox article.
- [ ] **Pending — Explanations:** Rejections contain human-readable explanations.
- [ ] **Pending — Safe refusal:** When no candidate clears the guard, the system returns `No confident match` with reasons.

## Backend

- [ ] **Pending — Persistence:** Migrated database models exist for images, tags/metadata, embeddings, posts, suggestions, and approvals/rejections, with required indexes.
- [ ] **Pending — API validation:** Endpoint input is validated and bad requests produce clean 4xx responses.
- [ ] **Pending — Review workflow:** A user can inspect why a suggestion was made and approve or reject it.
- [ ] **Pending — Authorization:** Minimum real authentication and authorization protect non-public endpoints.
- [ ] **Pending — Tenant isolation:** Cross-workspace access is prevented and tested.
- [ ] **Pending — Idempotency:** Retried job-triggering operations happen once.
- [ ] **Pending — Failure handling:** Background failures retry and produce a visible failure alert/event.
- [ ] **Pending — Budget guard:** AI calls are attributed, metered, and stopped by a configured budget policy when required.

## Quality and documentation

- [x] **Phase 4 evidence — Schema tests:** The deterministic suite covers valid metadata, malformed output, required fields, confidence bounds, blank/empty tags, collection normalization, taxonomy rejection, low-confidence flags, persistence, state transitions, provider timeout/failure, missing images, idempotent reuse, and explicit replacement.
- [ ] **Pending — Mismatch tests:** Automated tests cover the forced fox-versus-wolf rejection.
- [ ] **Pending — Matching tests:** Automated tests cover matching accuracy and equivalent concepts.
- [ ] **Pending — Resilience tests:** Tests cover dependency failure and duplicate job delivery.
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
