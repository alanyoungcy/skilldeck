"""Hybrid OpenCV + VLM slide analysis.

OpenCV proposes pixel-grounded geometry; the VLM labels candidates and
transcribes text. MinerU is only used as a fallback text source.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from editable_pptx.cv_detect import Candidate, cv2_available, detect_candidates, dominant_background_rgb, load_rgb
from editable_pptx.layout import elements_from_mineru_dir
from editable_pptx.som import classify_candidates
from editable_pptx.snap import edge_snap_bboxes
from editable_pptx.text_ocr import merge_mineru_text_fallback, transcribe_text_crop

logger = logging.getLogger(__name__)


def analyze_slide_hybrid(
    image_path: str,
    *,
    mineru_dir: Path | None,
    min_area_fraction: float,
    recursion_depth: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[int, int, int] | None, dict[str, Any]]:
    """Return (elements, shapes, page_bg, debug)."""
    im = Image.open(image_path).convert("RGB")
    slide_size = im.size
    page_bg = dominant_background_rgb(load_rgb(image_path))

    if not cv2_available():
        logger.warning("OpenCV unavailable; hybrid engine falling back to MinerU layout for %s", image_path)
        fallback = elements_from_mineru_dir(mineru_dir, slide_size) if mineru_dir else []
        return fallback, [], page_bg, {"engine": "mineru_fallback", "reason": "cv2_unavailable"}

    candidates, page_bg = detect_candidates(image_path, min_area_fraction=min_area_fraction)
    candidates = _add_recursive_candidates(
        image_path,
        candidates,
        min_area_fraction=min_area_fraction,
        max_depth=recursion_depth,
    )
    classification = classify_candidates(image_path, candidates, slide_size)
    role_by_id = {row["id"]: row for row in classification.get("candidates", []) if isinstance(row, dict)}

    elements: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    for cand in candidates:
        row = role_by_id.get(cand.id) or {}
        role = row.get("role") or _heuristic_role(cand, slide_size)
        if role == "noise":
            continue
        if role in {"container", "decorative"}:
            shapes.append(_shape_from_candidate(cand, z=row.get("z") or "under"))
            if role == "container":
                maybe_text = str(row.get("text") or "").strip()
                if maybe_text and _looks_like_text_container(cand, slide_size):
                    elements.append(_text_element(cand.bbox, maybe_text, source="som_container"))
        elif role == "text_block":
            text = str(row.get("text") or "").strip() or transcribe_text_crop(image_path, cand.bbox)
            if text:
                elements.append(_text_element(cand.bbox, text, source="som_candidate"))
        elif role == "atomic_figure":
            # Keep in the inpainted/full-slide background; don't emit native geometry.
            continue

    missing_elements: list[dict[str, Any]] = []
    for miss in classification.get("missing", []) or []:
        if not isinstance(miss, dict):
            continue
        role = miss.get("role")
        bbox = miss.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        if role == "text_block":
            text = str(miss.get("text") or "").strip() or transcribe_text_crop(image_path, bbox)
            if text:
                missing_elements.append(_text_element([float(v) for v in bbox], text, source="vlm_missing"))
        elif role == "decorative":
            shapes.append(
                {
                    "kind": _normalize_shape_kind(str(miss.get("kind") or "rect")),
                    "bbox": [float(v) for v in bbox],
                    "fill_rgb": None,
                    "stroke_rgb": None,
                    "stroke_width_px": 1.0,
                    "corner_radius_px": 0.0,
                    "z": "under",
                    "source": "vlm_missing",
                    "confidence": 0.45,
                }
            )
    if missing_elements:
        edge_snap_bboxes(image_path, missing_elements, only_sources={"vlm_missing"})
        elements.extend(missing_elements)

    if mineru_dir:
        try:
            merge_mineru_text_fallback(elements, elements_from_mineru_dir(mineru_dir, slide_size))
        except Exception as e:
            logger.debug("MinerU text fallback skipped for %s: %s", image_path, e)

    _assign_text_parents(elements, shapes)
    _apply_sampled_text_colors(image_path, elements, page_bg)

    debug = {
        "engine": "hybrid_cv",
        "candidate_count": len(candidates),
        "shape_count": len(shapes),
        "text_count": len(elements),
        "layout_architype": classification.get("layout_architype", "unknown"),
    }
    return elements, shapes, page_bg, debug


def _add_recursive_candidates(
    image_path: str,
    candidates: list[Candidate],
    *,
    min_area_fraction: float,
    max_depth: int,
) -> list[Candidate]:
    if max_depth <= 0:
        return _dedupe_and_reid(candidates)
    im = Image.open(image_path).convert("RGB")
    slide_area = float(im.width * im.height)
    work: list[tuple[Candidate, int]] = [
        (c, 1)
        for c in candidates
        if (c.contains_ids or _area(c.bbox) > slide_area * 0.08) and c.kind != "line"
    ]
    extra: list[Candidate] = []
    with tempfile.TemporaryDirectory(prefix="skilldeck_cv_crop_") as tmp:
        tmp_dir = Path(tmp)
        while work:
            parent, depth = work.pop(0)
            if depth > max_depth:
                continue
            crop_box = _padded_crop_box(parent.bbox, im.size, pad_ratio=0.05)
            if crop_box[2] - crop_box[0] < 32 or crop_box[3] - crop_box[1] < 32:
                continue
            crop = im.crop(crop_box)
            crop_path = tmp_dir / f"{parent.id}_{depth}.png"
            crop.save(crop_path)
            sub, _bg = detect_candidates(
                crop_path,
                min_area_fraction=max(min_area_fraction / (4 * depth), 0.0004),
                offset=(crop_box[0], crop_box[1]),
                prefix=f"{parent.id}_",
            )
            for cand in sub:
                if _area(cand.bbox) < _area(parent.bbox) * 0.96:
                    extra.append(cand)
                    if depth < max_depth and (cand.contains_ids or _area(cand.bbox) > _area(parent.bbox) * 0.16):
                        work.append((cand, depth + 1))
    return _dedupe_and_reid(candidates + extra)


def _shape_from_candidate(cand: Candidate, *, z: str) -> dict[str, Any]:
    return {
        "kind": _normalize_shape_kind(cand.kind),
        "bbox": cand.bbox,
        "fill_rgb": cand.fill_rgb,
        "stroke_rgb": cand.stroke_rgb,
        "stroke_width_px": cand.stroke_width_px,
        "corner_radius_px": cand.corner_radius_px,
        "z": "over" if str(z).lower() == "over" else "under",
        "source": cand.source,
        "candidate_id": cand.id,
        "confidence": cand.confidence,
        "parent_id": cand.parent_id,
    }


def _text_element(bbox: list[float], text: str, *, source: str) -> dict[str, Any]:
    return {
        "bbox": [float(v) for v in bbox],
        "type": "text",
        "content": text,
        "style": {},
        "source": source,
        "metadata": {"source": source},
    }


def _apply_sampled_text_colors(
    image_path: str,
    elements: list[dict[str, Any]],
    page_bg: tuple[int, int, int] | None,
) -> None:
    import numpy as np

    arr = load_rgb(image_path)
    for el in elements:
        if not (el.get("content") or "").strip():
            continue
        bb = el.get("bbox")
        if not bb or len(bb) != 4:
            continue
        rgb = _sample_foreground_rgb(arr, [float(v) for v in bb], page_bg)
        if not rgb:
            continue
        sty = el.setdefault("style", {})
        sty.setdefault("color_rgb", rgb)


def _assign_text_parents(elements: list[dict[str, Any]], shapes: list[dict[str, Any]]) -> None:
    containers = [s for s in shapes if s.get("candidate_id") and s.get("bbox")]
    for el in elements:
        bb = el.get("bbox")
        if not bb or len(bb) != 4:
            continue
        parents = [s for s in containers if _contains(s["bbox"], bb, tol=8.0)]
        if not parents:
            continue
        parent = min(parents, key=lambda s: _area(s["bbox"]))
        el["parent_id"] = parent.get("candidate_id")


def _sample_foreground_rgb(
    arr,
    bbox: list[float],
    page_bg: tuple[int, int, int] | None,
) -> tuple[int, int, int] | None:
    import numpy as np

    h, w = arr.shape[:2]
    x0 = max(0, min(w, int(bbox[0])))
    y0 = max(0, min(h, int(bbox[1])))
    x1 = max(0, min(w, int(bbox[2])))
    y1 = max(0, min(h, int(bbox[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    crop = arr[y0:y1, x0:x1].reshape(-1, 3)
    if crop.size == 0:
        return None
    quant = (crop // 16) * 16
    vals, counts = np.unique(quant, axis=0, return_counts=True)
    if len(vals) < 2:
        return tuple(int(x) for x in vals[0]) if len(vals) else None
    bg = np.array(page_bg if page_bg is not None else vals[int(np.argmax(counts))])
    # Text is usually a high-contrast minority color inside a bbox.
    scores = []
    total = float(crop.shape[0])
    for val, count in zip(vals, counts):
        contrast = float(np.linalg.norm(val.astype(float) - bg.astype(float)))
        minority = 1.0 - min(float(count) / total, 0.95)
        scores.append(contrast * minority)
    best = vals[int(np.argmax(scores))]
    return tuple(int(x) for x in best)


def _normalize_shape_kind(kind: str) -> str:
    if kind in {"roundRect", "rect", "ellipse", "pill", "chevron", "line", "arrow", "diamond", "triangle"}:
        return kind
    if kind.lower() in {"rounded", "rounded_rect", "roundrect"}:
        return "roundRect"
    if kind.lower() in {"image", "photo"}:
        return "rect"
    return "rect"


def _heuristic_role(cand: Candidate, slide_size: tuple[int, int]) -> str:
    slide_area = float(slide_size[0] * slide_size[1])
    area = _area(cand.bbox)
    if cand.kind == "line":
        return "decorative"
    if cand.contains_ids or area > slide_area * 0.08:
        return "container"
    return "decorative"


def _looks_like_text_container(cand: Candidate, slide_size: tuple[int, int]) -> bool:
    area = _area(cand.bbox)
    return area < float(slide_size[0] * slide_size[1]) * 0.08


def _padded_crop_box(bbox: list[float], size: tuple[int, int], pad_ratio: float) -> tuple[int, int, int, int]:
    w, h = size
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    return (
        max(0, int(x0 - bw * pad_ratio)),
        max(0, int(y0 - bh * pad_ratio)),
        min(w, int(x1 + bw * pad_ratio)),
        min(h, int(y1 + bh * pad_ratio)),
    )


def _area(bb: list[float]) -> float:
    return max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])


def _iou(a: list[float], b: list[float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = _area([x0, y0, x1, y1])
    if inter <= 0:
        return 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union else 0.0


def _dedupe_and_reid(candidates: list[Candidate]) -> list[Candidate]:
    ordered = sorted(candidates, key=lambda c: (c.bbox[1], c.bbox[0], -_area(c.bbox)))
    kept: list[Candidate] = []
    for cand in ordered:
        if _area(cand.bbox) <= 0:
            continue
        if any(_iou(cand.bbox, old.bbox) > 0.88 for old in kept):
            continue
        kept.append(cand)
    for idx, cand in enumerate(kept, start=1):
        cand.id = f"m{idx:03d}"
        cand.parent_id = None
        cand.contains_ids = []
    for child in kept:
        parents = [p for p in kept if _contains(p.bbox, child.bbox)]
        if parents:
            parent = min(parents, key=lambda p: _area(p.bbox))
            child.parent_id = parent.id
            parent.contains_ids.append(child.id)
    return kept


def _contains(parent: list[float], child: list[float], tol: float = 3.0) -> bool:
    return (
        child[0] >= parent[0] - tol
        and child[1] >= parent[1] - tol
        and child[2] <= parent[2] + tol
        and child[3] <= parent[3] + tol
        and _area(child) < _area(parent) * 0.96
    )
