# Reviewer Demo — 5–6 Minutes

## Before the call

From a clean PowerShell session, follow the README key-generation block, then run:

```powershell
docker compose up --build -d
docker compose exec -T api python -m scripts.seed
```

Keep the seed JSON visible. It is the concise acceptance transcript: 50/50 batch
completion, one low-confidence item, the raw fox/wolf/dog ranking, mismatch and
no-match explanations, human review, 107 call records, and both metrics.

## Walkthrough

1. **Problem and architecture — 30 seconds.** Open
   `http://localhost:3000/`. Explain that semantic retrieval finds related images,
   while the deterministic guard decides whether any candidate is safe to use.
2. **Image library and batch processing — 45 seconds.** Open
   `http://localhost:3000/images`. Show the licensed five-subject corpus,
   structured metadata, confidence state, and embedding state. Point to the seed
   result `processed: 50`, `failed: 0`, and `low_confidence_records: 1`.
3. **Raw semantic ranking — 45 seconds.** Open
   `http://localhost:3000/match`. Create a red-fox post, queue its embedding, and
   retrieve candidates. Explain why fox and wolf are semantically close. Anchor
   the deterministic acceptance proof in the seed JSON: red fox `1.00`, gray
   wolf `0.80`, domestic dog `0.60`.
4. **Forced wolf rejection — 45 seconds.** Run the guard in the matching page and
   show candidate decisions. The required isolated proof in the seed output is
   `SUBJECT_MISMATCH`: “Expected red fox, but the image was classified as gray
   wolf.” A high similarity score cannot override subject identity.
5. **Safe recommendation and review — 45 seconds.** Open
   `http://localhost:3000/recommendations/<recommendation_id>`, replacing the ID
   with `human_review.recommendation_id` from the seed output. Inspect immutable
   guard evidence and the append-only approval/rejection history.
6. **Safe refusal — 30 seconds.** Show `probe_4_no_safe_candidate` in the seed
   transcript: `recommendation: null`, `NO_CONFIDENT_MATCH`, and the candidate’s
   readable rejection reason. The system never falls back to the closest unsafe
   candidate.
7. **Evaluation — 60 seconds.** Open `http://localhost:3000/evaluation`. Report
   official top-1 `3 / 10 = 0.3000`, issued-recommendation precision
   `3 / 3 = 1.0000`, seven correct refusals, zero incorrect refusals, and zero
   unsafe acceptances. The first metric covers every post; the second covers only
   recommendations that were actually issued.
8. **Close — 20 seconds.** “Good suggestions when confident, safe rejection when
   uncertain—that is the production reliability boundary.”

## Useful verification commands

```powershell
docker compose ps
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
docker compose exec -T api alembic current
docker compose exec -T api python -m scripts.evaluate
```

