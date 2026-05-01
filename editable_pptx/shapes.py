"""VLM-driven shape detection.

Given a slide image and the typed regions already returned by MinerU
(`elements_from_mineru_dir`), ask the VLM to enumerate the *decorative*
shapes that aren't text, images, tables, or charts: rounded cards, pills,
dividers, arrows, etc. The result is returned as a list of dicts that
`assemble._add_shapes` maps to native DrawingML preset shapes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from editable_pptx.env import (
    chat_completions_url,
    shape_detect_enabled,
    vlm_api_key,
    vlm_style_model,
)
from editable_pptx.openai_style import (
    _chat,
    _image_to_data_url,
    _normalize_rgb,
    _parse_json_content,
)

logger = logging.getLogger(__name__)

VALID_KINDS = frozenset(
    {"roundRect", "rect", "ellipse", "pill", "chevron", "line", "arrow", "diamond", "triangle"}
)


def _shape_prompt(text_els: list[dict[str, Any]], slide_w: int, slide_h: int, hints: list[str]) -> str:
    occupied = [
        {"bbox": [round(x, 1) for x in el.get("bbox", [])], "type": el.get("type", "")}
        for el in text_els
        if el.get("bbox")
    ]
    hint_line = (
        f"Design hints from upstream: {', '.join(hints)}.\n" if hints else ""
    )
    return (
        "You are reconstructing a slide as native PowerPoint shapes. "
        "List every DECORATIVE geometric shape you see — rounded cards, pills, "
        "background panels, dividers, arrows, simple icons backgrounds. "
        "Skip raster/photo regions, charts, tables, and the text itself.\n"
        f"Slide pixel size: {slide_w}x{slide_h}. "
        "Coordinates are pixel x0,y0,x1,y1 with origin at top-left.\n"
        f"Already-classified text/image regions (do NOT re-emit these): "
        f"{json.dumps(occupied, ensure_ascii=False)}.\n"
        f"{hint_line}"
        "Return ONLY valid JSON:\n"
        '{"shapes":[{"kind":"roundRect|rect|ellipse|pill|chevron|line|arrow|diamond|triangle",'
        '"bbox":[x0,y0,x1,y1],'
        '"fill_rgb":[R,G,B] or null,'
        '"stroke_rgb":[R,G,B] or null,'
        '"stroke_width_px":N,'
        '"corner_radius_px":N,'
        '"z":"under"|"over",'
        '"confidence":0.0-1.0}]}\n'
        "Rules: emit at most 20 shapes. Use 'under' when the shape sits behind text "
        "(typical for cards/panels), 'over' for foreground accents. If a region is too "
        "complex (icon, illustration, photo), DO NOT emit it — it will be kept as bitmap."
    )


def detect_shapes(
    image_path: str,
    elements: list[dict[str, Any]],
    slide_size: tuple[int, int],
    *,
    layout_hints: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not shape_detect_enabled():
        return []
    text_els = [e for e in elements if e.get("bbox")]
    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    slide_url = _image_to_data_url(image_path)
    prompt = _shape_prompt(text_els, slide_size[0], slide_size[1], layout_hints or [])
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": slide_url}},
            ],
        }
    ]
    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        data = _parse_json_content(raw)
    except Exception as e:
        logger.warning("Shape detection failed for %s: %s", image_path, e)
        return []

    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("shapes") or []
    else:
        logger.warning(
            "Unexpected shape detection JSON for %s (want dict or list): %s",
            image_path,
            type(data).__name__,
        )
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", "")).strip()
        if kind not in VALID_KINDS:
            continue
        bb = row.get("bbox")
        if not isinstance(bb, (list, tuple)) or len(bb) != 4:
            continue
        try:
            bbox = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
        except (TypeError, ValueError):
            continue
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        try:
            conf = float(row.get("confidence", 0.7))
        except (TypeError, ValueError):
            conf = 0.7
        if conf < 0.35:
            continue
        out.append(
            {
                "kind": kind,
                "bbox": bbox,
                "fill_rgb": _normalize_rgb(row.get("fill_rgb")),
                "stroke_rgb": _normalize_rgb(row.get("stroke_rgb")),
                "stroke_width_px": float(row.get("stroke_width_px") or 0),
                "corner_radius_px": float(row.get("corner_radius_px") or 0),
                "z": "under" if str(row.get("z", "under")).lower() != "over" else "over",
                "confidence": conf,
            }
        )
    logger.info("VLM detected %d shapes for %s", len(out), image_path)
    return out
