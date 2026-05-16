"""VLM-driven decomposition of large image/figure/diagram regions.

When MinerU (or hybrid CV) classifies a slide region as a single bitmap but the
region actually contains a multi-box diagram (boxes + arrows + interior labels),
we want those boxes to become native PowerPoint shapes and the labels to become
editable text. This module crops each large image-typed region and asks the VLM
for a structured decomposition, then maps the result back to slide-level shape
and text element dicts.

Coordinates returned by the VLM are normalized in [0, 1] relative to the
cropped region; we re-project them to slide pixel coordinates using the
region's bbox.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from editable_pptx.env import (
    chat_completions_url,
    vlm_api_key,
    vlm_enabled,
    vlm_style_model,
)
from editable_pptx.openai_style import (
    _chat,
    _crop_to_data_url,
    _normalize_rgb,
    _parse_json_content,
)

logger = logging.getLogger(__name__)

# Element types that may contain a multi-box diagram worth decomposing.
DECOMPOSABLE_TYPES = frozenset({"image", "figure", "diagram"})

# Shape kinds the assembler currently understands; see assemble._KIND_TO_MSO.
_VALID_SHAPE_KINDS = frozenset(
    {"roundRect", "rect", "ellipse", "pill", "chevron", "line", "arrow", "diamond", "triangle"}
)


def _decompose_prompt(region_w: int, region_h: int, max_items: int) -> str:
    """Prompt asking the VLM to enumerate sub-boxes, arrows, and interior text."""
    return (
        "You are reconstructing a multi-box diagram inside a presentation slide "
        "as native PowerPoint shapes. The image you receive is a TIGHT CROP of "
        "ONE diagram region; treat the crop as the full canvas.\n"
        f"Crop size: {region_w}x{region_h} pixels. All coordinates you return must "
        "be NORMALIZED to [0.0, 1.0] of the crop, with origin at top-left. "
        "(0,0)=top-left, (1,1)=bottom-right.\n"
        "Return ONLY valid JSON:\n"
        '{"items":['
        '{"kind":"shape","shape_kind":"roundRect|rect|ellipse|pill|chevron|line|arrow|diamond|triangle",'
        '"bbox":[x0,y0,x1,y1],'
        '"fill_rgb":[R,G,B] or null,'
        '"stroke_rgb":[R,G,B] or null,'
        '"stroke_width_px":N,'
        '"corner_radius_px":N,'
        '"z":"under"|"over",'
        '"text":"interior label or empty",'
        '"confidence":0.0-1.0},'
        '{"kind":"text","bbox":[x0,y0,x1,y1],"text":"...","confidence":0.0-1.0}'
        ']}\n'
        f"Rules: emit at most {max_items} items total. "
        "Use 'shape' for every visible geometric box / pill / chevron / arrow. "
        "When a shape contains a label INSIDE it, put the label in the shape's "
        "'text' field; otherwise emit a separate 'text' item for standalone labels. "
        "Use 'arrow' (or 'chevron') for directional connectors between shapes. "
        "Skip pure background, photo regions, and tiny decorative dots. "
        "If the crop is clearly NOT a multi-box diagram (single illustration, photo, "
        "single icon), return {\"items\":[]}."
    )


def _project_bbox(
    norm_bbox: list[float] | tuple[float, ...],
    region_bbox: list[float],
    crop_w: int,
    crop_h: int,
) -> list[float] | None:
    """Project a normalized [0,1] bbox inside the crop back to slide coords.

    `region_bbox` is the original pixel bbox of the region on the slide.
    """
    if not isinstance(norm_bbox, (list, tuple)) or len(norm_bbox) != 4:
        return None
    try:
        nx0, ny0, nx1, ny1 = (float(v) for v in norm_bbox)
    except (TypeError, ValueError):
        return None
    # Clamp to [0, 1]; small negative or >1 are common VLM artifacts.
    nx0 = max(0.0, min(1.0, nx0))
    nx1 = max(0.0, min(1.0, nx1))
    ny0 = max(0.0, min(1.0, ny0))
    ny1 = max(0.0, min(1.0, ny1))
    if nx1 <= nx0 or ny1 <= ny0:
        return None
    rx0, ry0, rx1, ry1 = region_bbox
    rw = rx1 - rx0
    rh = ry1 - ry0
    if rw <= 0 or rh <= 0:
        return None
    # The crop is the region scaled to (crop_w, crop_h) pixels but the math is
    # the same: norm coords map directly to the original region bbox.
    out = [
        rx0 + nx0 * rw,
        ry0 + ny0 * rh,
        rx0 + nx1 * rw,
        ry0 + ny1 * rh,
    ]
    return out


def _call_vlm_for_region(
    image_path: str,
    region_bbox: list[float],
    max_items: int,
) -> list[dict[str, Any]]:
    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    if not (url and api_key and model):
        return []

    rx0, ry0, rx1, ry1 = region_bbox
    rw = max(1, int(round(rx1 - rx0)))
    rh = max(1, int(round(ry1 - ry0)))

    crop_url = _crop_to_data_url(image_path, list(region_bbox), pad=0.0)
    prompt = _decompose_prompt(rw, rh, max_items)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": crop_url}},
            ],
        }
    ]

    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        data = _parse_json_content(raw)
    except Exception as e:
        logger.warning("Diagram decomposition failed for %s region %s: %s", image_path, region_bbox, e)
        return []

    if isinstance(data, dict):
        items = data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        logger.warning(
            "Unexpected decomposition JSON for %s region %s: %s",
            image_path, region_bbox, type(data).__name__,
        )
        return []

    return [it for it in items if isinstance(it, dict)]


def _normalize_item(
    item: dict[str, Any],
    region_bbox: list[float],
    crop_w: int,
    crop_h: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn one VLM item into (shape_dicts, text_element_dicts).

    A shape with non-empty 'text' produces one shape and one text element
    overlaid on it (so users can edit the label without picking apart the
    shape geometry).
    """
    new_shapes: list[dict[str, Any]] = []
    new_texts: list[dict[str, Any]] = []

    kind = str(item.get("kind", "shape")).lower()
    bbox = _project_bbox(item.get("bbox"), region_bbox, crop_w, crop_h)
    if bbox is None:
        return new_shapes, new_texts
    try:
        confidence = float(item.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7
    if confidence < 0.35:
        return new_shapes, new_texts

    if kind == "shape":
        shape_kind = str(item.get("shape_kind", "")).strip()
        if shape_kind not in _VALID_SHAPE_KINDS:
            return new_shapes, new_texts
        try:
            stroke_w = float(item.get("stroke_width_px") or 0)
        except (TypeError, ValueError):
            stroke_w = 0.0
        try:
            corner_r = float(item.get("corner_radius_px") or 0)
        except (TypeError, ValueError):
            corner_r = 0.0
        new_shapes.append(
            {
                "kind": shape_kind,
                "bbox": bbox,
                "fill_rgb": _normalize_rgb(item.get("fill_rgb")),
                "stroke_rgb": _normalize_rgb(item.get("stroke_rgb")),
                "stroke_width_px": stroke_w,
                "corner_radius_px": corner_r,
                "z": "under" if str(item.get("z", "under")).lower() != "over" else "over",
                "confidence": confidence,
                "source": "diagram_decompose",
            }
        )
        # Interior label: emit as a text element above the shape.
        text = str(item.get("text") or "").strip()
        if text:
            new_texts.append(
                {
                    "bbox": list(bbox),
                    "type": "text",
                    "content": text,
                    "image_path": None,
                    "metadata": {"source": "diagram_decompose"},
                }
            )
        return new_shapes, new_texts

    if kind == "text":
        text = str(item.get("text") or "").strip()
        if not text:
            return new_shapes, new_texts
        new_texts.append(
            {
                "bbox": list(bbox),
                "type": "text",
                "content": text,
                "image_path": None,
                "metadata": {"source": "diagram_decompose"},
            }
        )

    return new_shapes, new_texts


def decompose_image_regions(
    image_path: str,
    elements: list[dict[str, Any]],
    slide_size: tuple[int, int],
    *,
    min_area_fraction: float = 0.05,
    max_items_per_region: int = 30,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    """Decompose every image/figure/diagram region above the size threshold.

    Returns `(extra_shapes, extra_text_elements, removed_indices)` where
    `removed_indices` are positions in `elements` whose source bitmaps were
    successfully replaced and should NOT be painted as pictures by the
    assembler. The caller should:
        * remove those elements before the picture pass, AND
        * append `extra_shapes` to the shapes list, AND
        * append `extra_text_elements` to the elements list.

    The function does not mutate `elements` itself.
    """
    if not vlm_enabled() or not elements:
        return [], [], []

    sw, sh = slide_size
    slide_area = max(1, int(sw) * int(sh))
    min_area = float(min_area_fraction) * slide_area

    extra_shapes: list[dict[str, Any]] = []
    extra_texts: list[dict[str, Any]] = []
    removed: list[int] = []

    for idx, el in enumerate(elements):
        if str(el.get("type", "")).lower() not in DECOMPOSABLE_TYPES:
            continue
        bbox = el.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        if x1 <= x0 or y1 <= y0:
            continue
        area = (x1 - x0) * (y1 - y0)
        if area < min_area:
            continue

        items = _call_vlm_for_region(image_path, list(bbox), max_items_per_region)
        if not items:
            continue

        crop_w = max(1, int(round(x1 - x0)))
        crop_h = max(1, int(round(y1 - y0)))

        produced_shapes: list[dict[str, Any]] = []
        produced_texts: list[dict[str, Any]] = []
        for item in items:
            s, t = _normalize_item(item, list(bbox), crop_w, crop_h)
            produced_shapes.extend(s)
            produced_texts.extend(t)

        # If the VLM returned nothing usable, leave the bitmap alone so we
        # don't end up with a blank region.
        if not produced_shapes and not produced_texts:
            continue

        logger.info(
            "Decomposed %s region %s: %d shapes + %d text elements",
            image_path, [round(v, 1) for v in bbox],
            len(produced_shapes), len(produced_texts),
        )
        extra_shapes.extend(produced_shapes)
        extra_texts.extend(produced_texts)
        removed.append(idx)

    return extra_shapes, extra_texts, removed
