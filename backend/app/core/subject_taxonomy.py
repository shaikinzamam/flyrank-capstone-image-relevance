import re
import unicodedata

from app.core.vision_taxonomy import VISION_TAXONOMY


SUBJECT_ALIASES: dict[str, str] = {
    "red fox": "red_fox",
    "vulpes vulpes": "red_fox",
    "gray wolf": "gray_wolf",
    "grey wolf": "gray_wolf",
    "canis lupus": "gray_wolf",
    "domestic dog": "domestic_dog",
    "canis familiaris": "domestic_dog",
    "canis lupus familiaris": "domestic_dog",
}


def normalize_term(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_") or None


def normalize_subject(value: str | None) -> str | None:
    normalized = normalize_term(value)
    if normalized is None:
        return None
    alias_key = normalized.replace("_", " ")
    if alias_key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[alias_key]
    if normalized in VISION_TAXONOMY:
        return normalized
    return normalized


def display_term(value: str | None) -> str:
    normalized = normalize_term(value)
    return normalized.replace("_", " ") if normalized else "unspecified"
