"""OpenAI-compatible vision calls for per-element text style (analyze.md step C)."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
from PIL import Image

from editable_pptx.env import chat_completions_url, vlm_api_key, vlm_enabled, vlm_style_model

logger = logging.getLogger(__name__)

TIMEOUT = 120


def _image_to_data_url(image_path: str, max_side: int = 2048) -> str:
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _crop_to_data_url(image_path: str, bbox: list[float], pad: float = 0.02) -> str:
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    px, py = bw * pad, bh * pad
    cx0 = max(0, int(x0 - px))
    cy0 = max(0, int(y0 - py))
    cx1 = min(w, int(x1 + px))
    cy1 = min(h, int(y1 + py))
    crop = im.crop((cx0, cy0, cx1, cy1))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _parse_json_content(raw: str) -> Any:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _chat(url: str, api_key: str, model: str, messages: list[dict], use_json_mode: bool) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": 4096}
    if use_json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code == 400 and use_json_mode:
        body.pop("response_format", None)
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    choice = data["choices"][0]
    msg = choice.get("message") or {}
    return (msg.get("content") or "").strip()


def _normalize_rgb(v: Any) -> tuple[int, int, int] | None:
    if v is None:
        return None
    if isinstance(v, dict) and all(k in v for k in ("r", "g", "b")):
        try:
            return (int(v["r"]), int(v["g"]), int(v["b"]))
        except (TypeError, ValueError):
            return None
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        try:
            return (int(v[0]), int(v[1]), int(v[2]))
        except (TypeError, ValueError):
            return None
    return None


def _global_styles(
    image_path: str,
    text_els: list[dict[str, Any]],
    url: str,
    api_key: str,
    model: str,
) -> tuple[dict[int, dict[str, Any]], tuple[int, int, int] | None]:
    if not text_els:
        return {}, None
    slide_url = _image_to_data_url(image_path)
    catalog = [
        {
            "i": i,
            "text": (el.get("content") or "")[:500],
            "bbox": [round(x, 1) for x in el.get("bbox", [])],
            "type": el.get("type", "text"),
        }
        for i, el in enumerate(text_els)
    ]
    user = (
        "You are analyzing a slide image for PowerPoint reconstruction. "
        "For each text block (index i), infer visual style as seen in the image.\n"
        "Return ONLY valid JSON with this shape:\n"
        '{"page_bg_rgb":[R,G,B],'
        '"styles":[{"i":0,"bold":false,"italic":false,"underline":false,'
        '"align":"left|center|right|justify","color_rgb":[R,G,B],'
        '"font_family_hint":"sans-serif|serif|mono|display|handwritten|script",'
        '"weight":"thin|light|regular|medium|semibold|bold|heavy|black"}]}\n'
        "Rules: align = visual alignment of that text block. color_rgb = dominant TEXT color "
        "(not background) 0-255. page_bg_rgb = the slide's overall background color. "
        "font_family_hint = closest of the listed families. weight = visual stroke thickness.\n"
        f"Blocks: {json.dumps(catalog, ensure_ascii=False)}"
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": slide_url}},
            ],
        }
    ]
    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        data = _parse_json_content(raw)
    except Exception as e:
        logger.warning("Global style extraction failed: %s", e)
        return {}, None
    out: dict[int, dict[str, Any]] = {}
    for row in data.get("styles") or []:
        try:
            idx = int(row["i"])
        except (KeyError, TypeError, ValueError):
            continue
        rgb = _normalize_rgb(row.get("color_rgb"))
        out[idx] = {
            "bold": bool(row.get("bold", False)),
            "italic": bool(row.get("italic", False)),
            "underline": bool(row.get("underline", False)),
            "align": str(row.get("align", "left")).lower(),
            "color_rgb": rgb,
            "font_family_hint": str(row.get("font_family_hint", "sans-serif")).lower(),
            "weight": str(row.get("weight", "regular")).lower(),
        }
    page_bg = _normalize_rgb(data.get("page_bg_rgb"))
    return out, page_bg


def _local_color(
    image_path: str,
    bbox: list[float],
    url: str,
    api_key: str,
    model: str,
) -> tuple[int, int, int] | None:
    crop_url = _crop_to_data_url(image_path, bbox)
    user = (
        "Return ONLY valid JSON: {\"color_rgb\":[R,G,B]} with the dominant TEXT color "
        "(not background) in this crop, each 0-255."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": crop_url}},
            ],
        }
    ]
    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        data = _parse_json_content(raw)
        return _normalize_rgb(data.get("color_rgb"))
    except Exception as e:
        logger.debug("Local color failed: %s", e)
        return None


def apply_openai_element_styles(image_path: str, elements: list[dict[str, Any]]) -> tuple[int, int, int] | None:
    """Mutate elements in place: set el['style'] with bold, italic, underline, align,
    color_rgb, font_family_hint, weight. Returns inferred page background RGB (or None)."""
    if not vlm_enabled():
        return None
    text_els = [e for e in elements if (e.get("content") or "").strip()]
    if not text_els:
        return None
    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    global_map, page_bg = _global_styles(image_path, text_els, url, api_key, model)
    max_workers = min(6, max(1, len(text_els)))

    local_colors: dict[int, tuple[int, int, int] | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {
            ex.submit(_local_color, image_path, el["bbox"], url, api_key, model): i
            for i, el in enumerate(text_els)
            if el.get("bbox") and len(el["bbox"]) == 4
        }
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                local_colors[i] = fut.result()
            except Exception as e:
                logger.debug("local color %s: %s", i, e)
                local_colors[i] = None

    for i, el in enumerate(text_els):
        g = global_map.get(i, {})
        sty: dict[str, Any] = {
            "bold": g.get("bold", False),
            "italic": g.get("italic", False),
            "underline": g.get("underline", False),
            "align": g.get("align", "left"),
            "color_rgb": local_colors.get(i) or g.get("color_rgb"),
            "font_family_hint": g.get("font_family_hint", "sans-serif"),
            "weight": g.get("weight", "regular"),
        }
        el["style"] = sty
    return page_bg
