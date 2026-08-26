# Interview Talking Points

- **Why embeddings are insufficient:** similarity measures related meaning, not
  factual subject identity. A fox and wolf can share habitat, visual descriptors,
  and article context while remaining mutually wrong recommendations.
- **Subject versus category:** both fox and wolf belong to `animal`; the narrower
  normalized subject comparison catches the dangerous mismatch that a category
  check alone would miss.
- **Deterministic guard:** provider output informs retrieval, but explicit ordered
  rules decide acceptance. Invalid metadata, low confidence, category/subject
  conflicts, missing required tags, and low similarity all produce stable codes
  and readable explanations.
- **Schema validation:** Pydantic validates AI JSON locally before persistence.
  Invalid or extra fields are rejected or retried, never silently trusted.
- **Durable queue:** PostgreSQL jobs use leases, `FOR UPDATE SKIP LOCKED`, capped
  retries, progress, terminal errors, and idempotency. Image success requires both
  metadata and an image vector; post embeddings use the same worker.
- **Tenant isolation:** bearer-key hashes resolve a workspace. Top-level rows own
  that workspace, child ownership is derived by foreign keys, repository queries
  are scoped, and foreign IDs deliberately look absent (`404`).
- **pgvector:** compatible 384-dimensional vectors are ranked with exact cosine
  distance in PostgreSQL, avoiding a second database for a bounded corpus.
- **Metrics:** official top-1 is `3/10 = 0.3000` because all posts—including safe
  refusals—are in the denominator. Issued precision is `3/3 = 1.0000`; it answers
  how often a recommendation was correct when the system chose to issue one.
- **Safe refusal:** seven correct refusals and zero unsafe acceptances demonstrate
  the intended product behavior: abstention is preferable to a wrong image.
- **Human review:** accepted evidence can be approved or rejected through an
  append-only trail. Review cannot override a guard-rejected candidate.
- **CSS 3D instead of Three.js:** perspective and Motion provide restrained depth
  with less bundle/runtime complexity, simpler accessibility, and no WebGL need.

