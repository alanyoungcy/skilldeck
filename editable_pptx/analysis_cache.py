"""Per-slide VLM analysis cache.

Why only VLM? MinerU and the local CV layout engine are fast. The slow,
expensive calls are:
  * `apply_openai_element_styles` (one VLM call per slide)
  * `detect_shapes` (one VLM call per slide)
  * `decompose_image_regions` (one VLM call per large diagram region)

Repeated runs on the same source image with the same style model and same
decompose flag should not pay those costs again. This module hashes those
inputs and persists the VLM-derived state per slide.

Cache file shape (`<deck>/analysis-cache/<slide-stem>.vlm.json`):
  {
    "key": "sha256:...",
    "version": 1,
    "page_bg": [R,G,B] | null,
    "styles": [
      {"i": 0, "bold": false, "align": "left", "color_rgb": [R,G,B], ...},
      ...
    ],
    "shapes": [...],                          # detect_shapes output
    "decompose": {
      "extra_shapes": [...],
      "extra_texts": [...],
      "removed_indices": [...]
    }
  }

The cache only round-trips JSON-friendly state. It does NOT cache MinerU
layout, picture image_paths, or anything tied to the temp working directory
of a run.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

CACHE_VERSION = 1
CACHE_DIRNAME = "analysis-cache"

logger = logging.getLogger(__name__)


def _hash_image(image_path: str) -> str:
    h = hashlib.sha256()
    with open(image_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_key(
    *,
    image_path: str,
    vlm_model: str,
    decompose_enabled: bool,
    decompose_min_area_fraction: float,
    layout_engine: str,
) -> str:
    """Stable key for a slide's VLM analysis."""
    parts = [
        f"img={_hash_image(image_path)}",
        f"vlm_model={vlm_model}",
        f"decompose={int(bool(decompose_enabled))}",
        f"decompose_min={decompose_min_area_fraction:.4f}",
        f"layout={layout_engine}",
        f"v={CACHE_VERSION}",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def cache_path(deck_dir: Path | None, slide_stem: str) -> Path | None:
    """Return the on-disk cache path for a slide stem, or None when no
    deck_dir is available (the caller should treat that as cache-disabled)."""
    if deck_dir is None:
        return None
    return Path(deck_dir) / CACHE_DIRNAME / f"{slide_stem}.vlm.json"


def load(path: Path | None, key: str) -> dict[str, Any] | None:
    """Read a cache file and return its payload when the key matches."""
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Analysis cache read failed for %s: %s", path, e)
        return None
    if data.get("version") != CACHE_VERSION:
        return None
    if data.get("key") != key:
        return None
    return data


def save(
    path: Path | None,
    key: str,
    *,
    page_bg: tuple[int, int, int] | None,
    styles: list[dict[str, Any]],
    shapes: list[dict[str, Any]],
    decompose_extra_shapes: list[dict[str, Any]],
    decompose_extra_texts: list[dict[str, Any]],
    decompose_removed_indices: list[int],
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "key": key,
        "page_bg": list(page_bg) if page_bg else None,
        "styles": styles,
        "shapes": shapes,
        "decompose": {
            "extra_shapes": decompose_extra_shapes,
            "extra_texts": decompose_extra_texts,
            "removed_indices": list(decompose_removed_indices),
        },
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning("Analysis cache write failed for %s: %s", path, e)
