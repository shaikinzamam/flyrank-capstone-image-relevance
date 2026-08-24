from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyEntry:
    subject: str
    category: str


VISION_TAXONOMY: dict[str, TaxonomyEntry] = {
    "red_fox": TaxonomyEntry(subject="red fox", category="animal"),
    "gray_wolf": TaxonomyEntry(subject="gray wolf", category="animal"),
    "domestic_dog": TaxonomyEntry(subject="domestic dog", category="animal"),
    "brown_bear": TaxonomyEntry(subject="brown bear", category="animal"),
    "white_tailed_deer": TaxonomyEntry(
        subject="white-tailed deer", category="animal"
    ),
}
