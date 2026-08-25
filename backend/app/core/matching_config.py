from dataclasses import dataclass


MATCHING_CONFIG_VERSION = "phase8-v1"
MIN_SIMILARITY = 0.70
MIN_VISION_CONFIDENCE = 0.70


@dataclass(frozen=True)
class MatchingConfig:
    """Provisional deterministic thresholds; Phase 9 evaluation will tune them."""

    version: str = MATCHING_CONFIG_VERSION
    minimum_similarity: float = MIN_SIMILARITY
    minimum_vision_confidence: float = MIN_VISION_CONFIDENCE
