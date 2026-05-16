"""Prepare slide background: whiteout, edge-fill, or raw image."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from editable_pptx.layout import should_whiteout

try:
    import cv2  # type: ignore
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional hybrid dependency
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]


def _expand_bbox(
    bbox: list[float],
    pad_ratio: float,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    w = x1 - x0
    h = y1 - y0
    px = w * pad_ratio
    py = h * pad_ratio
    nx0 = max(0, int(x0 - px))
    ny0 = max(0, int(y0 - py))
    nx1 = min(width, int(x1 + px))
    ny1 = min(height, int(y1 + py))
    return nx0, ny0, nx1, ny1


def _edge_average_color(im: Image.Image, box: tuple[int, int, int, int], band: int = 4) -> tuple[int, int, int]:
    """Average RGB from pixels in a band just outside the rectangle (clipped to image)."""
    x0, y0, x1, y1 = box
    w, h = im.size
    samples: list[tuple[int, int, int]] = []

    # Top band: rows [y0-band, y0)
    for y in range(max(0, y0 - band), min(h, y0)):
        for x in range(max(0, x0), min(w, x1)):
            samples.append(im.getpixel((x, y)))
    # Bottom band
    for y in range(min(h, y1), min(h, y1 + band)):
        for x in range(max(0, x0), min(w, x1)):
            samples.append(im.getpixel((x, y)))
    # Left band
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0 - band), min(w, x0)):
            samples.append(im.getpixel((x, y)))
    # Right band
    for y in range(max(0, y0), min(h, y1)):
        for x in range(min(w, x1), min(w, x1 + band)):
            samples.append(im.getpixel((x, y)))

    if not samples:
        return (255, 255, 255)
    r = sum(p[0] for p in samples) // len(samples)
    g = sum(p[1] for p in samples) // len(samples)
    b = sum(p[2] for p in samples) // len(samples)
    return (r, g, b)


def build_background(
    image_path: str,
    elements: list[dict[str, Any]],
    *,
    mode: str = "edge",
    pad_ratio: float = 0.02,
    shapes: list[dict[str, Any]] | None = None,
) -> Image.Image:
    """
    mode=whiteout: solid white over text regions.
    mode=edge: fill with average color sampled outside each bbox (softer on non-white slides).
    mode=inpaint: remove emitted text/shape regions with cv2.inpaint.
    mode=none: original image (double-text risk).
    """
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    mode = (mode or "edge").lower()
    if mode == "none":
        return im
    if mode == "inpaint" and cv2 is not None and np is not None:
        mask = _build_inpaint_mask(elements, shapes or [], w, h, pad_ratio=pad_ratio)
        if mask is not None:
            bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
            out = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
            return Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))

    overlay = im.copy()
    draw = ImageDraw.Draw(overlay)
    for el in elements:
        if not should_whiteout(el):
            continue
        bb = el.get("bbox")
        if not bb or len(bb) != 4:
            continue
        box = _expand_bbox(bb, pad_ratio, w, h)
        if mode == "edge":
            fill = _edge_average_color(im, box)
        else:
            fill = (255, 255, 255)
        draw.rectangle(box, fill=fill)
    return overlay


def _build_inpaint_mask(
    elements: list[dict[str, Any]],
    shapes: list[dict[str, Any]],
    width: int,
    height: int,
    *,
    pad_ratio: float,
):
    if np is None or cv2 is None:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    for el in elements:
        if not should_whiteout(el):
            continue
        bb = el.get("bbox")
        if bb and len(bb) == 4:
            x0, y0, x1, y1 = _expand_bbox(bb, pad_ratio, width, height)
            cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
    for sh in shapes:
        bb = sh.get("bbox")
        if not bb or len(bb) != 4:
            continue
        # Do not erase large container panels; those are re-emitted as shapes
        # but often define the page's visual structure.
        area = max(0.0, bb[2] - bb[0]) * max(0.0, bb[3] - bb[1])
        if area > width * height * 0.18:
            continue
        x0, y0, x1, y1 = _expand_bbox(bb, pad_ratio, width, height)
        cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
    return mask
