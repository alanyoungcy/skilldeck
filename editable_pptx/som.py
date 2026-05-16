"""Set-of-Mark VLM classification over OpenCV candidates."""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from editable_pptx.cv_detect import Candidate
from editable_pptx.env import chat_completions_url, vlm_api_key, vlm_enabled, vlm_style_model
from editable_pptx.openai_style import _chat, _parse_json_content

logger = logging.getLogger(__name__)

ROLES = {"container", "atomic_figure", "decorative", "text_block", "noise"}


def _overlay_data_url(image_path: str, candidates: list[Candidate], max_side: int = 2048) -> str:
    im = Image.open(image_path).convert("RGB")
    scale = 1.0
    if max(im.size) > max_side:
        scale = max_side / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(im, "RGBA")
    colors = [
        (255, 80, 80, 220),
        (80, 140, 255, 220),
        (50, 190, 120, 220),
        (245, 180, 40, 220),
        (180, 90, 255, 220),
    ]
    try:
        font = ImageFont.truetype("Arial.ttf", max(12, int(15 * scale)))
    except Exception:
        font = ImageFont.load_default()
    for idx, cand in enumerate(candidates):
        x0, y0, x1, y1 = [v * scale for v in cand.bbox]
        color = colors[idx % len(colors)]
        draw.rectangle((x0, y0, x1, y1), outline=color, width=max(2, int(2 * scale)))
        label = cand.id
        tx, ty = x0 + 3, y0 + 3
        tw = max(30, len(label) * 8)
        draw.rectangle((tx - 2, ty - 2, tx + tw, ty + 16), fill=(0, 0, 0, 180))
        draw.text((tx, ty), label, fill=(255, 255, 255, 255), font=font)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def heuristic_classify(candidates: list[Candidate], slide_size: tuple[int, int]) -> dict[str, Any]:
    w, h = slide_size
    slide_area = float(w * h)
    rows: list[dict[str, Any]] = []
    for cand in candidates:
        x0, y0, x1, y1 = cand.bbox
        area = max(0.0, x1 - x0) * max(0.0, y1 - y0)
        if area < slide_area * 0.0008:
            role = "noise"
        elif cand.kind == "line":
            role = "decorative"
        elif cand.contains_ids or area > slide_area * 0.08:
            role = "container"
        else:
            role = "decorative"
        rows.append({"id": cand.id, "role": role, "confidence": cand.confidence})
    return {"layout_architype": "unknown", "candidates": rows, "missing": []}


def classify_candidates(image_path: str, candidates: list[Candidate], slide_size: tuple[int, int]) -> dict[str, Any]:
    if not candidates:
        return {"layout_architype": "unknown", "candidates": [], "missing": []}
    if not vlm_enabled():
        return heuristic_classify(candidates, slide_size)

    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    overlay_url = _overlay_data_url(image_path, candidates)
    catalog = [c.to_json() for c in candidates]
    prompt = (
        "You are reconstructing a slide as editable PowerPoint. The image has numbered "
        "OpenCV candidates overlaid. Do NOT invent coordinates for numbered candidates; "
        "choose from their ids.\n\n"
        "For each numbered candidate, classify it as exactly one role: "
        "container, atomic_figure, decorative, text_block, or noise. "
        "If a candidate contains readable text, include a transcription in `text`. "
        "Also list any important visible text or shapes not numbered in `missing`; those may include bboxes.\n\n"
        "Return ONLY valid JSON:\n"
        '{"layout_architype":"kpi_grid_3|two_column_compare|timeline_strip|dashboard|unknown",'
        '"candidates":[{"id":"m001","role":"container|atomic_figure|decorative|text_block|noise",'
        '"text":"optional text","z":"under|over","confidence":0.0}],'
        '"missing":[{"role":"text_block|decorative|atomic_figure","bbox":[x0,y0,x1,y1],'
        '"text":"optional","kind":"rect|roundRect|ellipse|line|image"}]}\n\n'
        f"Slide size: {slide_size[0]}x{slide_size[1]} pixels.\n"
        f"Candidates: {json.dumps(catalog, ensure_ascii=False)}"
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": overlay_url}},
            ],
        }
    ]
    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        data = _parse_json_content(raw)
    except Exception as e:
        logger.warning("SoM candidate classification failed for %s: %s", image_path, e)
        return heuristic_classify(candidates, slide_size)
    if not isinstance(data, dict):
        return heuristic_classify(candidates, slide_size)

    known = {c.id for c in candidates}
    cleaned_rows: list[dict[str, Any]] = []
    for row in data.get("candidates") or []:
        if not isinstance(row, dict) or row.get("id") not in known:
            continue
        role = str(row.get("role") or "").strip()
        if role not in ROLES:
            role = "noise"
        cleaned_rows.append(
            {
                "id": row["id"],
                "role": role,
                "text": str(row.get("text") or "").strip(),
                "z": "over" if str(row.get("z", "under")).lower() == "over" else "under",
                "confidence": _float(row.get("confidence"), 0.7),
            }
        )

    missing: list[dict[str, Any]] = []
    for row in data.get("missing") or []:
        if not isinstance(row, dict):
            continue
        bb = row.get("bbox")
        if not isinstance(bb, list) or len(bb) != 4:
            continue
        role = str(row.get("role") or "").strip()
        if role not in {"text_block", "decorative", "atomic_figure"}:
            continue
        try:
            bbox = [float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3])]
        except (TypeError, ValueError):
            continue
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        missing.append(
            {
                "role": role,
                "bbox": bbox,
                "text": str(row.get("text") or "").strip(),
                "kind": str(row.get("kind") or "rect"),
            }
        )
    return {
        "layout_architype": str(data.get("layout_architype") or "unknown"),
        "candidates": cleaned_rows or heuristic_classify(candidates, slide_size)["candidates"],
        "missing": missing,
    }


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
