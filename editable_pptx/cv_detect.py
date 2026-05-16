"""OpenCV-first geometric candidate detection for editable slide recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime package
    cv2 = None  # type: ignore[assignment]


@dataclass
class Candidate:
    id: str
    kind: str
    bbox: list[float]
    fill_rgb: tuple[int, int, int] | None = None
    stroke_rgb: tuple[int, int, int] | None = None
    stroke_width_px: float = 0.0
    corner_radius_px: float = 0.0
    parent_id: str | None = None
    contains_ids: list[str] = field(default_factory=list)
    source: str = "opencv"
    confidence: float = 0.7

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "bbox": [round(v, 2) for v in self.bbox],
            "fill_rgb": list(self.fill_rgb) if self.fill_rgb else None,
            "stroke_rgb": list(self.stroke_rgb) if self.stroke_rgb else None,
            "stroke_width_px": round(float(self.stroke_width_px), 2),
            "corner_radius_px": round(float(self.corner_radius_px), 2),
            "parent_id": self.parent_id,
            "contains_ids": self.contains_ids,
            "source": self.source,
            "confidence": round(float(self.confidence), 3),
        }


def cv2_available() -> bool:
    return cv2 is not None


def load_rgb(image_path: str | Path) -> np.ndarray:
    return np.array(Image.open(image_path).convert("RGB"))


def dominant_background_rgb(rgb: np.ndarray, k: int = 8) -> tuple[int, int, int]:
    if cv2 is None:
        flat = rgb.reshape(-1, 3)
        vals, counts = np.unique((flat // 16) * 16, axis=0, return_counts=True)
        return tuple(int(x) for x in vals[int(np.argmax(counts))])
    quant = quantize_rgb(rgb, k=k)
    flat = quant.reshape(-1, 3)
    vals, counts = np.unique(flat, axis=0, return_counts=True)
    return tuple(int(x) for x in vals[int(np.argmax(counts))])


def quantize_rgb(rgb: np.ndarray, k: int = 12) -> np.ndarray:
    if cv2 is None:
        return (rgb // 32) * 32
    pixels = rgb.reshape((-1, 3)).astype(np.float32)
    k = max(2, min(k, len(pixels)))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 16, 1.0)
    _compactness, labels, centers = cv2.kmeans(
        pixels,
        k,
        None,
        criteria,
        2,
        cv2.KMEANS_PP_CENTERS,
    )
    centers = np.uint8(np.clip(centers, 0, 255))
    return centers[labels.flatten()].reshape(rgb.shape)


def _clip_bbox(bbox: list[float], w: int, h: int) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [
        float(max(0, min(w, x0))),
        float(max(0, min(h, y0))),
        float(max(0, min(w, x1))),
        float(max(0, min(h, y1))),
    ]


def _bbox_area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _median_rgb(rgb: np.ndarray, bbox: list[float], inset: float = 0.12) -> tuple[int, int, int] | None:
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = _clip_bbox(bbox, w, h)
    bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 2:
        return None
    ix0 = int(x0 + bw * inset)
    iy0 = int(y0 + bh * inset)
    ix1 = int(x1 - bw * inset)
    iy1 = int(y1 - bh * inset)
    if ix1 <= ix0 or iy1 <= iy0:
        return None
    crop = rgb[iy0:iy1, ix0:ix1]
    if crop.size == 0:
        return None
    med = np.median(crop.reshape(-1, 3), axis=0)
    return tuple(int(round(x)) for x in med)


def _edge_rgb(rgb: np.ndarray, bbox: list[float], band: int = 2) -> tuple[int, int, int] | None:
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in _clip_bbox(bbox, w, h)]
    samples: list[np.ndarray] = []
    if y1 - y0 <= 1 or x1 - x0 <= 1:
        return None
    samples.append(rgb[y0 : min(h, y0 + band), x0:x1])
    samples.append(rgb[max(0, y1 - band) : y1, x0:x1])
    samples.append(rgb[y0:y1, x0 : min(w, x0 + band)])
    samples.append(rgb[y0:y1, max(0, x1 - band) : x1])
    arr = np.concatenate([s.reshape(-1, 3) for s in samples if s.size], axis=0)
    if arr.size == 0:
        return None
    med = np.median(arr, axis=0)
    return tuple(int(round(x)) for x in med)


def _iou(a: list[float], b: list[float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = _bbox_area([x0, y0, x1, y1])
    if inter <= 0:
        return 0.0
    union = _bbox_area(a) + _bbox_area(b) - inter
    return inter / union if union else 0.0


def _contains(parent: list[float], child: list[float], tol: float = 3.0) -> bool:
    return (
        child[0] >= parent[0] - tol
        and child[1] >= parent[1] - tol
        and child[2] <= parent[2] + tol
        and child[3] <= parent[3] + tol
        and _bbox_area(child) < _bbox_area(parent) * 0.96
    )


def _corner_radius(mask: np.ndarray, bbox: list[float]) -> float:
    x0, y0, x1, y1 = [int(round(v)) for v in bbox]
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    probe = max(3, int(min(w, h) * 0.12))
    offsets: list[int] = []
    corners = [
        mask[y0 : min(mask.shape[0], y0 + probe), x0 : min(mask.shape[1], x0 + probe)],
        mask[y0 : min(mask.shape[0], y0 + probe), max(0, x1 - probe) : x1],
        mask[max(0, y1 - probe) : y1, x0 : min(mask.shape[1], x0 + probe)],
        mask[max(0, y1 - probe) : y1, max(0, x1 - probe) : x1],
    ]
    for c in corners:
        if c.size:
            empty_frac = 1.0 - float(np.count_nonzero(c)) / float(c.size)
            if empty_frac > 0.18:
                offsets.append(int(probe * min(0.5, empty_frac)))
    return float(np.median(offsets)) if offsets else 0.0


def _contour_candidates(
    rgb: np.ndarray,
    *,
    min_area: float,
    offset: tuple[int, int],
    prefix: str,
) -> list[Candidate]:
    if cv2 is None:
        return []
    ox, oy = offset
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    out: list[Candidate] = []
    for i, cnt in enumerate(contours):
        area = float(cv2.contourArea(cnt))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 6 or h < 6:
            continue
        bbox = [float(x + ox), float(y + oy), float(x + w + ox), float(y + h + oy)]
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        kind = "rect"
        if len(approx) > 8:
            kind = "ellipse" if abs(w - h) < min(w, h) * 0.2 else "roundRect"
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, thickness=-1)
        radius = _corner_radius(mask, [x, y, x + w, y + h])
        if radius > 0 and kind == "rect":
            kind = "roundRect"
        out.append(
            Candidate(
                id=f"{prefix}c{i}",
                kind=kind,
                bbox=bbox,
                fill_rgb=_median_rgb(rgb, [x, y, x + w, y + h]),
                stroke_rgb=_edge_rgb(rgb, [x, y, x + w, y + h]),
                stroke_width_px=1.0,
                corner_radius_px=radius,
                confidence=0.72,
            )
        )
    return out


def _component_candidates(
    rgb: np.ndarray,
    *,
    min_area: float,
    offset: tuple[int, int],
    prefix: str,
) -> list[Candidate]:
    if cv2 is None:
        return []
    ox, oy = offset
    quant = quantize_rgb(rgb, k=12)
    flat = quant.reshape(-1, 3)
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    bg_idx = int(np.argmax(counts)) if len(counts) else -1
    out: list[Candidate] = []
    for ci, color in enumerate(colors):
        if ci == bg_idx:
            continue
        mask = cv2.inRange(quant, color, color)
        n, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
        for li in range(1, n):
            x, y, w, h, area = [int(v) for v in stats[li]]
            if area < min_area or w < 8 or h < 8:
                continue
            fill = tuple(int(v) for v in color)
            out.append(
                Candidate(
                    id=f"{prefix}q{ci}_{li}",
                    kind="rect",
                    bbox=[float(x + ox), float(y + oy), float(x + w + ox), float(y + h + oy)],
                    fill_rgb=fill,
                    stroke_rgb=_edge_rgb(rgb, [x, y, x + w, y + h]),
                    stroke_width_px=0.0,
                    confidence=0.62,
                )
            )
    return out


def _line_candidates(
    rgb: np.ndarray,
    *,
    min_area: float,
    offset: tuple[int, int],
    prefix: str,
) -> list[Candidate]:
    if cv2 is None:
        return []
    ox, oy = offset
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    min_len = max(24, int(min(rgb.shape[:2]) * 0.08))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=min_len, maxLineGap=8)
    out: list[Candidate] = []
    if lines is None:
        return out
    for i, line in enumerate(lines[:80]):
        x1, y1, x2, y2 = [int(v) for v in line[0]]
        if abs(x2 - x1) < 4 and abs(y2 - y1) < 4:
            continue
        x0, xa = sorted([x1, x2])
        y0, ya = sorted([y1, y2])
        if (xa - x0 + 1) * (ya - y0 + 1) < min_area * 0.03:
            continue
        thickness = 2.0
        bbox = [
            float(x0 + ox),
            float(y0 + oy),
            float(max(xa + 1, x0 + thickness) + ox),
            float(max(ya + 1, y0 + thickness) + oy),
        ]
        out.append(
            Candidate(
                id=f"{prefix}l{i}",
                kind="line",
                bbox=bbox,
                fill_rgb=_edge_rgb(rgb, [x0, y0, xa + 1, ya + 1]),
                stroke_rgb=_edge_rgb(rgb, [x0, y0, xa + 1, ya + 1]),
                stroke_width_px=thickness,
                confidence=0.58,
            )
        )
    return out


def _dedupe(candidates: list[Candidate], slide_area: float) -> list[Candidate]:
    ordered = sorted(candidates, key=lambda c: (-(c.confidence), -_bbox_area(c.bbox)))
    kept: list[Candidate] = []
    for cand in ordered:
        area = _bbox_area(cand.bbox)
        if area <= 0 or area > slide_area * 0.98:
            continue
        if any(_iou(cand.bbox, k.bbox) > 0.88 for k in kept):
            continue
        kept.append(cand)
    kept.sort(key=lambda c: (c.bbox[1], c.bbox[0], c.bbox[2] - c.bbox[0]))
    for idx, cand in enumerate(kept, start=1):
        cand.id = f"m{idx:03d}"
    for child in kept:
        parents = [p for p in kept if _contains(p.bbox, child.bbox)]
        if parents:
            parent = min(parents, key=lambda p: _bbox_area(p.bbox))
            child.parent_id = parent.id
            parent.contains_ids.append(child.id)
    return kept


def detect_candidates(
    image_path: str | Path,
    *,
    min_area_fraction: float = 0.005,
    offset: tuple[int, int] = (0, 0),
    prefix: str = "",
) -> tuple[list[Candidate], tuple[int, int, int]]:
    """Return high-recall geometric candidates and dominant background RGB."""
    if cv2 is None:
        return [], dominant_background_rgb(load_rgb(image_path))
    rgb = load_rgb(image_path)
    h, w = rgb.shape[:2]
    slide_area = float(w * h)
    min_area = max(12.0, slide_area * min_area_fraction)
    candidates: list[Candidate] = []
    candidates.extend(_component_candidates(rgb, min_area=min_area, offset=offset, prefix=prefix))
    candidates.extend(_contour_candidates(rgb, min_area=min_area, offset=offset, prefix=prefix))
    candidates.extend(_line_candidates(rgb, min_area=min_area, offset=offset, prefix=prefix))
    return _dedupe(candidates, slide_area), dominant_background_rgb(rgb)
