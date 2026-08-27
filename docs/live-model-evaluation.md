# Live-model evaluation

> This small representative live subset does not establish universal model accuracy and is separate from the deterministic official evaluation.

Generated: `2026-08-27T04:50:54.611476+00:00`

## Configuration

- Vision: `gemini` / `gemini-3.6-flash`
- Embeddings: `local` / `sentence-transformers/all-MiniLM-L6-v2` at `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`
- Guard configuration: `phase8-v1` (unchanged baseline)

## Measured metrics

- Images evaluated: `10`
- Schema validation: `9/10` (`0.9000`)
- Vision classification correctness: `9/10` (`0.9000`)
- Raw retrieval top-1: `5/5` (`1.0000`)
- Recommendation coverage: `0.2000`
- Abstention rate: `0.8000`
- Issued-recommendation precision: `1.0000`
- Unsafe acceptances: `0`
- Gemini calls: `10`
- Estimated Gemini cost: `$0.010000`
- Real embedding calls: `14/14` succeeded (9 image metadata records and 5 article scenarios)

## Live vision calls

| Image | Provider / model | Status | Expected | Gemini subject | Category | Confidence | Schema | Correct | Latency ms | Estimated cost |
|---|---|---|---|---|---|---:|---|---|---:|---:|
| red_fox_01 | gemini / gemini-3.6-flash | succeeded | red fox | red fox | animal | 0.98 | True | True | 8935 | 0.001 |
| red_fox_02 | gemini / gemini-3.6-flash | succeeded | red fox | red fox | animal | 0.98 | True | True | 6993 | 0.001 |
| gray_wolf_01 | gemini / gemini-3.6-flash | succeeded | gray wolf | gray wolf | animal | 0.98 | True | True | 8252 | 0.001 |
| gray_wolf_02 | gemini / gemini-3.6-flash | succeeded | gray wolf | gray wolf | animal | 0.98 | True | True | 5721 | 0.001 |
| domestic_dog_01 | gemini / gemini-3.6-flash | succeeded | domestic dog | domestic dog | animal | 0.98 | True | True | 9137 | 0.001 |
| domestic_dog_02 | gemini / gemini-3.6-flash | succeeded | domestic dog | domestic dog | animal | 0.99 | True | True | 5842 | 0.001 |
| brown_bear_01 | gemini / gemini-3.6-flash | succeeded | brown bear | brown bear | animal | 0.98 | True | True | 5548 | 0.001 |
| brown_bear_02 | gemini / gemini-3.6-flash | succeeded | brown bear | brown bear | animal | 0.98 | True | True | 7314 | 0.001 |
| white_tailed_deer_01 | gemini / gemini-3.6-flash | succeeded | white-tailed deer | white-tailed deer | animal | 0.98 | True | True | 5432 | 0.001 |
| white_tailed_deer_02 | gemini / gemini-3.6-flash | failed | white-tailed deer | n/a | n/a | n/a | False | False | 733 | 0.001 |

### Captions, tags, and failures

- `red_fox_01` caption: A close-up portrait of a red fox looking directly forward against a background of dry grass.
- `red_fox_01` tags: red fox, fox, wildlife, mammal, animal, nature, fur
- `red_fox_02` caption: A close-up profile view of a red fox with snow dusted on its nose in a snowy winter landscape.
- `red_fox_02` tags: red fox, fox, wildlife, animal, mammal, winter, snow, nature
- `gray_wolf_01` caption: A close-up portrait of a gray wolf with striking amber eyes looking directly forward, resting behind dark rocks against a blurred warm autumn background.
- `gray_wolf_01` tags: gray wolf, wolf, wildlife, canine, animal, mammal, nature
- `gray_wolf_02` caption: A side view of a gray wolf running mid-stride across dry grass with its mouth open and tongue hanging out.
- `gray_wolf_02` tags: gray wolf, wolf, canine, mammal, wildlife, animal, running, outdoors
- `domestic_dog_01` caption: A happy young girl with pigtails stands behind a light brown domestic dog, hugging it around the neck while smiling brightly in an outdoor field.
- `domestic_dog_01` tags: dog, child, girl, hug, happiness, outdoors, pet, friendship
- `domestic_dog_02` caption: A yellow Labrador Retriever standing outdoors on a patch of short green grass.
- `domestic_dog_02` tags: domestic dog, labrador retriever, yellow lab, canine, dog, standing, outdoor
- `brown_bear_01` caption: A brown bear runs dynamically across a green grassy area beside water.
- `brown_bear_01` tags: brown bear, bear, running, wildlife, animal, mammal, nature, water, grass
- `brown_bear_02` caption: A brown bear standing in a shallow, rocky river with green vegetation along the bank in the background.
- `brown_bear_02` tags: brown bear, bear, wildlife, river, nature, standing, grizzly
- `white_tailed_deer_01` caption: A close-up profile shot of a white-tailed deer in the rain, showing its wet fur and moss tangled in its antlers against a blurred natural background.
- `white_tailed_deer_01` tags: white-tailed deer, deer, wildlife, antlers, rain, nature, profile, animal
- `white_tailed_deer_02` failure: VisionProviderFailureError: Vision provider request failed

## Real retrieval and guard results

### red fox

Raw top-k: `[{"rank": 1, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.6903712337987892}, {"rank": 2, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.5580583478177589}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.3920749788239618}, {"rank": 4, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.37036980743768133}, {"rank": 5, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.3650361895561245}]`

Guard decisions: `[{"rank": 1, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.6903712337987892, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.69 is below the configured minimum 0.70."}, {"rank": 2, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.5580583478177589, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.56 is below the configured minimum 0.70."}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.3920749788239618, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected red fox, but the image was classified as gray wolf."}, {"rank": 4, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.37036980743768133, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected red fox, but the image was classified as brown bear."}, {"rank": 5, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.3650361895561245, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected red fox, but the image was classified as gray wolf."}]`

Selected: `NO_CONFIDENT_MATCH`; correct: `False`.

### gray wolf

Raw top-k: `[{"rank": 1, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.6903615593910217}, {"rank": 2, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.6196633946694978}, {"rank": 3, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.4818223427640004}, {"rank": 4, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.47834596166932897}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.46513837575912476}]`

Guard decisions: `[{"rank": 1, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.6903615593910217, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.69 is below the configured minimum 0.70."}, {"rank": 2, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.6196633946694978, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.62 is below the configured minimum 0.70."}, {"rank": 3, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.4818223427640004, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected gray wolf, but the image was classified as brown bear."}, {"rank": 4, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.47834596166932897, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected gray wolf, but the image was classified as brown bear."}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.46513837575912476, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected gray wolf, but the image was classified as red fox."}]`

Selected: `NO_CONFIDENT_MATCH`; correct: `False`.

### domestic dog

Raw top-k: `[{"rank": 1, "fixture_image_id": "domestic_dog_02", "subject": "domestic dog", "similarity_score": 0.5330914100083309}, {"rank": 2, "fixture_image_id": "domestic_dog_01", "subject": "domestic dog", "similarity_score": 0.5225539959238172}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.41944731531880264}, {"rank": 4, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.38548986272483665}, {"rank": 5, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.357458035870136}]`

Guard decisions: `[{"rank": 1, "fixture_image_id": "domestic_dog_02", "subject": "domestic dog", "similarity_score": 0.5330914100083309, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.53 is below the configured minimum 0.70."}, {"rank": 2, "fixture_image_id": "domestic_dog_01", "subject": "domestic dog", "similarity_score": 0.5225539959238172, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.52 is below the configured minimum 0.70."}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.41944731531880264, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected domestic dog, but the image was classified as gray wolf."}, {"rank": 4, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.38548986272483665, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected domestic dog, but the image was classified as red fox."}, {"rank": 5, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.357458035870136, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected domestic dog, but the image was classified as red fox."}]`

Selected: `NO_CONFIDENT_MATCH`; correct: `False`.

### brown bear

Raw top-k: `[{"rank": 1, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.6561081819405339}, {"rank": 2, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.5956057792179847}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.5188024926899387}, {"rank": 4, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.4892978972615074}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.4597781622542054}]`

Guard decisions: `[{"rank": 1, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.6561081819405339, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.66 is below the configured minimum 0.70."}, {"rank": 2, "fixture_image_id": "brown_bear_01", "subject": "brown bear", "similarity_score": 0.5956057792179847, "decision": "LOW_SIMILARITY", "reason_code": "LOW_SIMILARITY", "explanation": "Semantic similarity 0.60 is below the configured minimum 0.70."}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.5188024926899387, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected brown bear, but the image was classified as gray wolf."}, {"rank": 4, "fixture_image_id": "red_fox_02", "subject": "red fox", "similarity_score": 0.4892978972615074, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected brown bear, but the image was classified as red fox."}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.4597781622542054, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected brown bear, but the image was classified as red fox."}]`

Selected: `NO_CONFIDENT_MATCH`; correct: `False`.

### white-tailed deer

Raw top-k: `[{"rank": 1, "fixture_image_id": "white_tailed_deer_01", "subject": "white-tailed deer", "similarity_score": 0.7308442753050176}, {"rank": 2, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.5049628320314197}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.4584932327270508}, {"rank": 4, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.4462840291092387}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.4435119330883026}]`

Guard decisions: `[{"rank": 1, "fixture_image_id": "white_tailed_deer_01", "subject": "white-tailed deer", "similarity_score": 0.7308442753050176, "decision": "ACCEPTED", "reason_code": "ACCEPTED", "explanation": "Subject and category match with sufficient semantic similarity."}, {"rank": 2, "fixture_image_id": "gray_wolf_02", "subject": "gray wolf", "similarity_score": 0.5049628320314197, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected white tailed deer, but the image was classified as gray wolf."}, {"rank": 3, "fixture_image_id": "gray_wolf_01", "subject": "gray wolf", "similarity_score": 0.4584932327270508, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected white tailed deer, but the image was classified as gray wolf."}, {"rank": 4, "fixture_image_id": "brown_bear_02", "subject": "brown bear", "similarity_score": 0.4462840291092387, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected white tailed deer, but the image was classified as brown bear."}, {"rank": 5, "fixture_image_id": "red_fox_01", "subject": "red fox", "similarity_score": 0.4435119330883026, "decision": "SUBJECT_MISMATCH", "reason_code": "SUBJECT_MISMATCH", "explanation": "Expected white tailed deer, but the image was classified as red fox."}]`

Selected: `white_tailed_deer_01`; correct: `True`.
