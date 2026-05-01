"""Prepare slide background: whiteout, edge-fill, or raw image."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw

from editable_pptx.layout import should_whiteout


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
) -> Image.Image:
    """
    mode=whiteout: solid white over text regions.
    mode=edge: fill with average color sampled outside each bbox (softer on non-white slides).
    mode=none: original image (double-text risk).
    """
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    mode = (mode or "edge").lower()
    if mode == "none":
        return im

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
