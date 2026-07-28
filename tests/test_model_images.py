import os
from utils.model_images import model_image_path, _slugify, MODEL_IMAGE_DIR


def test_slug_matches_known_model_label():
    assert _slugify("Royal Enfield Bullet 350") == "royal_enfield_bullet_350"


def test_slug_handles_punctuation_and_case():
    assert _slugify("Royal Enfield Continental GT 650") == "royal_enfield_continental_gt_650"


def test_missing_image_returns_none():
    assert model_image_path("Some Model That Does Not Exist") is None


def test_finds_existing_image(tmp_path, monkeypatch):
    import utils.model_images as mi
    monkeypatch.setattr(mi, "MODEL_IMAGE_DIR", str(tmp_path))
    (tmp_path / "royal_enfield_bullet_350.jpg").write_bytes(b"fake")
    assert mi.model_image_path("Royal Enfield Bullet 350") == str(tmp_path / "royal_enfield_bullet_350.jpg")
