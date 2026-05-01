"""Unify slide raster dimensions before MinerU so one python-pptx size fits all slides."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def _snap16(n: int, mode: str = "nearest") -> int:
    r = n % 16
    if r == 0:
        return n
    down = n - r
    up = n + (16 - r)
    if mode == "down":
        return down
    if mode == "up":
        return up
    return up if (up - n) <= (n - down) else down


def normalize_size_string(raw: str) -> str:
    """Match Streamlit: WxH with both sides snapped to multiples of 16."""
    s = raw.strip().lower().replace(" ", "").replace("×", "x")
    if not s:
        return "1920x1088"
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        return "1920x1088"
    w = _snap16(int(m.group(1)), "nearest")
    h = _snap16(int(m.group(2)), "nearest")
    return f"{w}x{h}"


def parse_size_to_wh(size: str) -> tuple[int, int]:
    s = size.strip().lower().replace(" ", "").replace("×", "x")
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        raise ValueError(f"Invalid canvas size {size!r} (expected WxH)")
    return int(m.group(1)), int(m.group(2))


def canvas_size_from_env() -> tuple[int, int] | None:
    """IMAGE_SIZE or EDITABLE_PPTX_CANVAS from .env (authoritative when set)."""
    raw = (os.getenv("IMAGE_SIZE") or os.getenv("EDITABLE_PPTX_CANVAS") or "").strip()
    if not raw:
        return None
    norm = normalize_size_string(raw)
    return parse_size_to_wh(norm)


# 16:9 default (width × height); height snapped to multiple of 16 for image backends / MinerU.
DEFAULT_SLIDE_CANVAS_WH: tuple[int, int] = parse_size_to_wh(normalize_size_string("1920x1080"))


def resolve_target_canvas_wh(_slide_paths: list[Path]) -> tuple[int, int]:
    """Target pixel size for all slides before MinerU.

    Uses ``IMAGE_SIZE`` or ``EDITABLE_PPTX_CANVAS`` when set; otherwise **16:9** at 1920×1080
    (snapped to ``1920x1088`` for /16 alignment).
    """
    env_wh = canvas_size_from_env()
    if env_wh is not None:
        logger.info("Canvas from env: %sx%s", env_wh[0], env_wh[1])
        return env_wh
    tw, th = DEFAULT_SLIDE_CANVAS_WH
    logger.info("Canvas default 16:9: %sx%s (set IMAGE_SIZE to override)", tw, th)
    return tw, th


def normalize_slide_to_canvas(src: Path, dst: Path, tw: int, th: int) -> bool:
    """Scale uniformly to fit inside tw×th, center on white, save RGB PNG. Returns True if raster changed."""
    im = Image.open(src).convert("RGBA")
    changed = im.size != (tw, th)
    if not changed:
        rgb = Image.new("RGB", (tw, th), (255, 255, 255))
        rgb.paste(im, mask=im.split()[3])
        dst.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(dst, format="PNG", compress_level=6)
        return False
    fitted = ImageOps.contain(im, (tw, th), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (255, 255, 255, 255))
    ox = (tw - fitted.width) // 2
    oy = (th - fitted.height) // 2
    canvas.paste(fitted, (ox, oy))
    rgb = Image.new("RGB", (tw, th), (255, 255, 255))
    rgb.paste(canvas, mask=canvas.split()[3])
    dst.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(dst, format="PNG", compress_level=6)
    return True


def materialize_normalized_slides(
    slides: list[Path],
    work_root: Path,
    tw: int,
    th: int,
) -> list[Path]:
    """Write each slide into work_root using the original filename; all (tw, th) pixels."""
    work_root.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for src in slides:
        dst = work_root / src.name
        if normalize_slide_to_canvas(src, dst, tw, th):
            logger.info("Normalized %s → %sx%s", src.name, tw, th)
        out.append(dst)
    return out
