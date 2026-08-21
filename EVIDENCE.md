# Definition-of-Done Evidence

Every item starts as **Pending**. Evidence will be added only after the corresponding command, test, request, log, or evaluation has actually been produced.

## AI processing

- [ ] **Pending — Structured output:** The vision model produces structured output validated against a schema; invalid responses are never trusted.
- [ ] **Pending — Confidence policy:** Low-confidence classifications are flagged instead of accepted.
- [ ] **Pending — Background processing:** Images are processed through a batch background job with retries.
- [ ] **Pending — Cost accounting:** Vision and embedding costs are tracked for every call.

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

- [ ] **Pending — Schema tests:** Automated tests cover valid and invalid model output.
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

