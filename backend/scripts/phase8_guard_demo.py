import json

from app.services.mismatch_guard import GuardInput, MismatchGuard


def candidate(
    subject: str, subject_code: str, similarity: float, confidence: float
) -> GuardInput:
    return GuardInput(
        similarity_score=similarity,
        expected_subject="red_fox",
        expected_category="animal",
        required_tags=(),
        image_subject=subject,
        image_subject_code=subject_code,
        image_category="animal",
        image_tags=(subject, "winter"),
        vision_confidence=confidence,
        is_low_confidence=False,
        metadata_status="trusted",
        metadata_valid=True,
    )


def run_demo(inputs: list[GuardInput]) -> dict[str, object]:
    guard = MismatchGuard()
    decisions = []
    recommendation = None
    for rank, item in enumerate(inputs, start=1):
        result = guard.evaluate(item)
        decision = {
            "rank": rank,
            "subject": item.image_subject,
            "similarity_score": item.similarity_score,
            "decision": result.decision.value,
            "explanation": result.explanation,
        }
        decisions.append(decision)
        if recommendation is None and result.decision.value == "ACCEPTED":
            recommendation = decision
    return {
        "status": "matched" if recommendation else "no_confident_match",
        "reason_code": None if recommendation else "NO_CONFIDENT_MATCH",
        "recommendation": recommendation,
        "candidate_decisions": decisions,
    }


if __name__ == "__main__":
    matched = run_demo(
        [
            candidate("gray wolf", "gray_wolf", 0.93, 0.96),
            candidate("red fox", "red_fox", 0.90, 0.95),
            candidate("domestic dog", "domestic_dog", 0.20, 0.95),
        ]
    )
    no_match = run_demo(
        [
            candidate("gray wolf", "gray_wolf", 0.93, 0.96),
            candidate("domestic dog", "domestic_dog", 0.20, 0.95),
        ]
    )
    print(json.dumps({"fox_wolf_demo": matched, "refusal_demo": no_match}, indent=2))
