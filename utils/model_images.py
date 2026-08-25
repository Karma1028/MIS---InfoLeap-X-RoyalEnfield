"""Local product-image lookup for RE models on the Model Comparison page.
Local static assets only (assets/models/) — no runtime internet fetching,
per design decision: avoids broken links / licensing risk in a
client-facing deliverable. A model with no matching file on disk is
skipped silently by the caller, never an error."""
import os
import re

MODEL_IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "models")


def _slugify(model_label):
    slug = model_label.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def model_image_path(model_label):
    """Returns the absolute path to model_label's product photo if a
    matching .jpg/.jpeg/.png/.webp file exists in assets/models/, else None."""
    slug = _slugify(model_label)
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = os.path.join(MODEL_IMAGE_DIR, slug + ext)
        if os.path.exists(candidate):
            return candidate
    return None
