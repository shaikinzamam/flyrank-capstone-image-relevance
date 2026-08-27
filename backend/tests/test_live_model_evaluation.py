import asyncio
from types import SimpleNamespace

import pytest

from scripts import live_model_evaluation


def test_live_subset_selects_stable_records_across_every_subject() -> None:
    records = [
        {
            "image_id": f"{subject}_{index:02d}",
            "subject_code": subject,
        }
        for subject in live_model_evaluation.SUBJECT_CODES
        for index in (3, 1, 2)
    ]

    selected = live_model_evaluation._selected_records(records, per_subject=2)

    assert [record["image_id"] for record in selected] == [
        item
        for subject in live_model_evaluation.SUBJECT_CODES
        for item in (f"{subject}_01", f"{subject}_02")
    ]


def test_live_evaluation_refuses_to_run_without_server_side_gemini_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        live_model_evaluation,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key=None),
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"):
        asyncio.run(live_model_evaluation.run_live_evaluation(per_subject=2))
