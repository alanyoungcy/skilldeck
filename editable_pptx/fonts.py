"""Font hint -> installed PPT font, plus PIL-based shrink-to-fit measurement."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)

# (latin, cjk) defaults — rely on fonts shipped with PowerPoint and macOS.
HINT_FONT_MAP: dict[str, tuple[str, str]] = {
    "sans-serif": ("Inter", "PingFang SC"),
    "sans": ("Inter", "PingFang SC"),
    "serif": ("Cambria", "Source Han Serif SC"),
    "mono": ("Consolas", "Source Han Mono SC"),
    "display": ("Bebas Neue", "PingFang SC"),
    "handwritten": ("Patrick Hand", "PingFang SC"),
    "script": ("Brush Script MT", "PingFang SC"),
}

# Common fallbacks PIL can usually find on macOS for measurement purposes.
_PIL_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]

WEIGHT_TO_BOLD = {
    "thin": False,
    "light": False,
    "regular": False,
    "medium": False,
    "semibold": True,
    "bold": True,
    "heavy": True,
    "black": True,
}


def resolve_family(hint: str | None, has_cjk: bool, override: str | None = None) -> str:
    if override:
        return override
    h = (hint or "sans-serif").strip().lower()
    latin, cjk = HINT_FONT_MAP.get(h, HINT_FONT_MAP["sans-serif"])
    return cjk if has_cjk else latin


def text_has_cjk(text: str) -> bool:
    for c in text:
        if "一" <= c <= "鿿" or "぀" <= c <= "ヿ" or "가" <= c <= "힯":
            return True
    return False


@lru_cache(maxsize=64)
def _load_pil_font(family: str, size_px: int) -> ImageFont.ImageFont:
    candidates = [family, f"{family}.ttf", f"{family}.ttc"]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size_px)
        except (OSError, IOError):
            continue
    for fb in _PIL_FALLBACKS:
        if Path(fb).is_file():
            try:
                return ImageFont.truetype(fb, size_px)
            except (OSError, IOError):
                continue
    return ImageFont.load_default()


def _wrap_lines(text: str, font: ImageFont.ImageFont, max_width_px: float) -> list[str]:
    out: list[str] = []
    for raw in text.split("\n"):
        if not raw:
            out.append("")
            continue
        # CJK: wrap per-character; latin: per-word.
        if any("一" <= c <= "鿿" for c in raw):
            tokens = list(raw)
            joiner = ""
        else:
            tokens = re.split(r"(\s+)", raw)
            joiner = ""
        cur = ""
        for tok in tokens:
            trial = cur + (joiner if cur else "") + tok
            w = font.getlength(trial) if hasattr(font, "getlength") else font.getsize(trial)[0]
            if w <= max_width_px or not cur:
                cur = trial
            else:
                out.append(cur.rstrip())
                cur = tok if not tok.isspace() else ""
        if cur:
            out.append(cur.rstrip())
    return out or [""]


def _line_height_px(font: ImageFont.ImageFont, size_px: int) -> float:
    try:
        ascent, descent = font.getmetrics()
        return (ascent + descent) * 1.05
    except Exception:
        return size_px * 1.25


def fit_font_size_pt(
    text: str,
    bbox_w_px: float,
    bbox_h_px: float,
    family: str,
    *,
    dpi: int = 96,
    min_pt: float = 6.0,
    max_pt: float = 120.0,
) -> float:
    """Binary-search the largest pt that wraps within bbox at given DPI."""
    if not text or bbox_w_px <= 0 or bbox_h_px <= 0:
        return min_pt
    lo, hi = min_pt, max_pt
    best = min_pt
    for _ in range(18):
        mid = (lo + hi) / 2
        size_px = max(4, int(round(mid * dpi / 72)))
        font = _load_pil_font(family, size_px)
        lines = _wrap_lines(text, font, bbox_w_px)
        line_h = _line_height_px(font, size_px)
        total_h = line_h * len(lines)
        max_line_w = max(
            (font.getlength(l) if hasattr(font, "getlength") else font.getsize(l)[0]) for l in lines
        ) if lines else 0
        if total_h <= bbox_h_px and max_line_w <= bbox_w_px:
            best = mid
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.25:
            break
    return best
