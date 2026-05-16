"""Constrained text OCR/transcription helpers for hybrid layout recovery."""

from __future__ import annotations

import base64
import io
import json
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from editable_pptx.env import chat_completions_url, vlm_api_key, vlm_enabled, vlm_style_model
from editable_pptx.openai_style import _chat, _parse_json_content

logger = logging.getLogger(__name__)


def crop_to_data_url(image_path: str, bbox: list[float], pad: float = 0.04) -> str:
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = bbox
    bw, bh = max(1.0, x1 - x0), max(1.0, y1 - y0)
    px, py = bw * pad, bh * pad
    crop = im.crop(
        (
            max(0, int(x0 - px)),
            max(0, int(y0 - py)),
            min(w, int(x1 + px)),
            min(h, int(y1 + py)),
        )
    )
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=92)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def transcribe_text_crop(image_path: str, bbox: list[float]) -> str:
    """Ask the configured VLM to transcribe one known text region."""
    if not vlm_enabled():
        return ""
    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    crop_url = crop_to_data_url(image_path, bbox)
    prompt = (
        "Transcribe all readable text in this slide crop. Preserve line breaks when useful. "
        "Return ONLY valid JSON: {\"text\":\"...\"}. If there is no readable text, return an empty string."
    )
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
        text = data.get("text") if isinstance(data, dict) else ""
        return str(text or "").strip()
    except Exception as e:
        logger.debug("Text crop transcription failed for %s %s: %s", image_path, bbox, e)
        return ""


def merge_mineru_text_fallback(
    elements: list[dict[str, Any]],
    mineru_elements: list[dict[str, Any]],
    *,
    max_iou: float = 0.3,
) -> None:
    """Append MinerU text not already covered by hybrid regions.

    This is a fallback only; MinerU does not own layout in the hybrid engine.
    """
    for mel in mineru_elements:
        if not (mel.get("content") or "").strip():
            continue
        mb = mel.get("bbox")
        if not mb or len(mb) != 4:
            continue
        if any(_iou(mb, el.get("bbox") or []) > max_iou for el in elements):
            continue
        elements.append(
            {
                "bbox": [float(v) for v in mb],
                "type": mel.get("type") or "text",
                "content": mel.get("content"),
                "metadata": {"source": "mineru_fallback"},
            }
        )


def _area(bb: list[float]) -> float:
    if len(bb) != 4:
        return 0.0
    return max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])


def _iou(a: list[float], b: list[float]) -> float:
    if len(a) != 4 or len(b) != 4:
        return 0.0
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = _area([x0, y0, x1, y1])
    if inter <= 0:
        return 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union else 0.0


def save_debug_json(path: Path, data: Any) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
