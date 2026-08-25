from io import BytesIO

import pytest
from PIL import Image

from scripts.seed import DemoEmbeddingProvider, _synthetic_png


def test_demo_vectors_distinguish_image_subject_from_expected_post_subject() -> None:
    provider = DemoEmbeddingProvider()

    post = provider.embed(
        "Title: Winter foxes.\nBody: Red foxes.\nExpected subject: red fox."
    )
    wolf = provider.embed("Subject: gray wolf.\nCategory: animal.")
    fox = provider.embed("Subject: red fox.\nCategory: animal.")

    assert post[:2] == [1.0, 0.0]
    assert wolf[0] == pytest.approx(0.93)
    assert fox[0] == pytest.approx(0.90)


def test_demo_png_is_valid_and_visibly_synthetic() -> None:
    content = _synthetic_png("RED FOX", (198, 78, 30))

    with Image.open(BytesIO(content)) as image:
        image.verify()
        assert image.format == "PNG"
        assert image.size == (640, 420)
