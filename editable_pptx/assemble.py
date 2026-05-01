"""Build editable PPTX with python-pptx (background + native shapes + pictures + text)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from editable_pptx.background import build_background
from editable_pptx.fonts import (
    WEIGHT_TO_BOLD,
    fit_font_size_pt,
    resolve_family,
    text_has_cjk,
)
from editable_pptx.layout import RASTER_TYPES

logger = logging.getLogger(__name__)

DEFAULT_DPI = 96


def _pixels_to_inches(px: float) -> float:
    return px / DEFAULT_DPI


def _px_to_emu(px: float) -> int:
    return int(round(px / DEFAULT_DPI * 914400))


def _pp_align(name: str | None) -> int:
    n = (name or "left").lower()
    if n == "center":
        return PP_ALIGN.CENTER
    if n == "right":
        return PP_ALIGN.RIGHT
    if n == "justify":
        return PP_ALIGN.JUSTIFY
    return PP_ALIGN.LEFT


_KIND_TO_MSO: dict[str, int] = {
    "rect": MSO_SHAPE.RECTANGLE,
    "roundRect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "pill": MSO_SHAPE.ROUNDED_RECTANGLE,
    "ellipse": MSO_SHAPE.OVAL,
    "chevron": MSO_SHAPE.CHEVRON,
    "arrow": MSO_SHAPE.RIGHT_ARROW,
    "line": MSO_SHAPE.RECTANGLE,  # rendered as a thin filled rect; LINE shape needs end-points
    "diamond": MSO_SHAPE.DIAMOND,
    "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
}


def _add_native_shape(slide, shape: dict[str, Any]) -> None:
    bb = shape["bbox"]
    x0, y0, x1, y1 = bb
    w = max(1.0, x1 - x0)
    h = max(1.0, y1 - y0)
    kind = shape["kind"]

    # `line` becomes a 1-2px filled rectangle so we keep one consistent path.
    if kind == "line":
        thickness = max(1.0, shape.get("stroke_width_px") or 2.0)
        if w >= h:
            h = thickness
        else:
            w = thickness

    mso = _KIND_TO_MSO.get(kind, MSO_SHAPE.RECTANGLE)
    sp = slide.shapes.add_shape(
        mso,
        Emu(_px_to_emu(x0)),
        Emu(_px_to_emu(y0)),
        Emu(_px_to_emu(w)),
        Emu(_px_to_emu(h)),
    )

    # Corner radius for round-rects and pills via the first adjustment handle.
    if kind in ("roundRect", "pill"):
        try:
            short_side = min(w, h)
            if kind == "pill":
                adj = 0.5
            else:
                cr = shape.get("corner_radius_px") or 0
                adj = max(0.0, min(0.5, (cr / short_side) if short_side else 0))
                if adj < 0.05 and (cr or 0) > 0:
                    adj = 0.1
            if sp.adjustments:
                sp.adjustments[0] = adj
        except Exception:
            pass

    fill_rgb = shape.get("fill_rgb")
    stroke_rgb = shape.get("stroke_rgb")
    stroke_w_px = shape.get("stroke_width_px") or 0
    try:
        if fill_rgb:
            sp.fill.solid()
            sp.fill.fore_color.rgb = RGBColor(*fill_rgb)
        else:
            sp.fill.background()
    except Exception:
        pass
    try:
        if stroke_rgb:
            sp.line.color.rgb = RGBColor(*stroke_rgb)
            if stroke_w_px:
                sp.line.width = Emu(_px_to_emu(stroke_w_px))
        elif stroke_w_px == 0 and not fill_rgb:
            # neither fill nor stroke -> at least keep a faint outline so user can find it
            pass
        else:
            sp.line.fill.background()
    except Exception:
        pass

    try:
        if sp.has_text_frame:
            sp.text_frame.text = ""
    except Exception:
        pass


def _add_flat_background(slide, slide_w_px: int, slide_h_px: int, page_bg: tuple[int, int, int] | None) -> None:
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        Emu(_px_to_emu(slide_w_px)),
        Emu(_px_to_emu(slide_h_px)),
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(*(page_bg or (255, 255, 255)))
    bg.line.fill.background()


def add_slide_from_image(
    prs: Presentation,
    slide_image_path: str,
    elements: list[dict[str, Any]],
    *,
    bg_mode: str,
    set_presentation_dimensions: bool,
    text_pad: float = 1.005,
    font_body: str | None = None,
    font_title: str | None = None,
    shapes: list[dict[str, Any]] | None = None,
    page_bg: tuple[int, int, int] | None = None,
    flat_background: bool = False,
) -> None:
    """
    Add one slide. python-pptx uses one slide size for the whole deck — set
    `set_presentation_dimensions=True` only for the first slide (all PNGs should match).
    """
    im = Image.open(slide_image_path)
    slide_w_px, slide_h_px = im.size
    if set_presentation_dimensions:
        prs.slide_width = Inches(_pixels_to_inches(slide_w_px))
        prs.slide_height = Inches(_pixels_to_inches(slide_h_px))

    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)

    shapes = shapes or []

    # --- background layer ---
    if flat_background:
        _add_flat_background(slide, slide_w_px, slide_h_px, page_bg)
    else:
        bg_img = build_background(slide_image_path, elements, mode=bg_mode)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            bg_img.save(tmp_path, "PNG")
        try:
            slide.shapes.add_picture(
                str(tmp_path),
                left=0,
                top=0,
                width=prs.slide_width,
                height=prs.slide_height,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    # --- native shapes that go UNDER text/pictures ---
    for sh in shapes:
        if sh.get("z", "under") == "under":
            try:
                _add_native_shape(slide, sh)
            except Exception as e:
                logger.warning("under shape %s failed: %s", sh.get("kind"), e)

    # --- pictures (images / tables / charts from MinerU) ---
    pictures: list[dict[str, Any]] = []
    texts: list[dict[str, Any]] = []
    for el in elements:
        t = el.get("type", "")
        if t in RASTER_TYPES and el.get("image_path"):
            pictures.append(el)
        elif el.get("content"):
            texts.append(el)

    for el in pictures:
        path = el["image_path"]
        bb = el["bbox"]
        if not path or not Path(path).is_file():
            continue
        left = Inches(_pixels_to_inches(bb[0]))
        top = Inches(_pixels_to_inches(bb[1]))
        w = Inches(_pixels_to_inches(bb[2] - bb[0]))
        h = Inches(_pixels_to_inches(bb[3] - bb[1]))
        try:
            slide.shapes.add_picture(path, left=left, top=top, width=w, height=h)
        except Exception as e:
            logger.warning("add_picture failed: %s", e)

    # --- text boxes ---
    for el in texts:
        text = el.get("content") or ""
        if not text.strip():
            continue
        bb = el["bbox"]
        pad = text_pad
        cx = (bb[0] + bb[2]) / 2
        cy = (bb[1] + bb[3]) / 2
        bw = (bb[2] - bb[0]) * pad
        bh = (bb[3] - bb[1]) * pad
        x0 = cx - bw / 2
        y0 = cy - bh / 2
        left = Inches(_pixels_to_inches(x0))
        top = Inches(_pixels_to_inches(y0))
        width = Inches(_pixels_to_inches(bw))
        height = Inches(_pixels_to_inches(bh))
        box = slide.shapes.add_textbox(left, top, width, height)
        try:
            box.fill.background()
        except Exception:
            pass
        try:
            box.line.fill.background()
        except Exception:
            pass
        tf = box.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.TOP
        try:
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        except Exception:
            pass
        p = tf.paragraphs[0]
        p.text = text
        sty = el.get("style") or {}
        p.alignment = _pp_align(sty.get("align"))
        try:
            p.line_spacing = 1.08
        except Exception:
            pass

        is_title = el.get("type") == "title"
        # Pick font family.
        family_override = font_title if is_title and font_title else font_body
        family = resolve_family(
            sty.get("font_family_hint"),
            text_has_cjk(text),
            override=family_override,
        )
        # Shrink-to-fit using the chosen family.
        fs = fit_font_size_pt(text, bw, bh, family)
        # Bold from weight if VLM gave one, else from `bold` flag, else title heuristic.
        weight = (sty.get("weight") or "regular").lower()
        bold_from_weight = WEIGHT_TO_BOLD.get(weight)
        bold = sty.get("bold")
        if bold is None:
            bold = bold_from_weight if bold_from_weight is not None else is_title
        italic = bool(sty.get("italic", False))
        underline = bool(sty.get("underline", False))
        rgb = sty.get("color_rgb")

        for run in p.runs:
            run.font.size = Pt(max(6, int(round(fs))))
            run.font.bold = bool(bold)
            run.font.italic = italic
            if underline:
                run.font.underline = True
            if rgb and isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                try:
                    run.font.color.rgb = RGBColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
                except Exception:
                    pass
            try:
                run.font.name = family
            except Exception:
                pass

    # --- native shapes that go OVER text ---
    for sh in shapes:
        if sh.get("z", "under") == "over":
            try:
                _add_native_shape(slide, sh)
            except Exception as e:
                logger.warning("over shape %s failed: %s", sh.get("kind"), e)


def export_editable_deck(
    ordered_image_paths: list[str],
    mineru_dirs: list[Path],
    output_pptx: Path,
    *,
    bg_mode: str,
    deck_dir: Path | None = None,
) -> None:
    if len(ordered_image_paths) != len(mineru_dirs):
        raise ValueError("image paths and mineru_dirs length mismatch")
    if not ordered_image_paths:
        raise ValueError("no slides")

    w0, h0 = Image.open(ordered_image_paths[0]).size
    for p in ordered_image_paths[1:]:
        w, h = Image.open(p).size
        if (w, h) != (w0, h0):
            logger.warning(
                "Slide size mismatch: first is %sx%s but %s is %sx%s — PPT uses first size; positions may drift.",
                w0,
                h0,
                p,
                w,
                h,
            )

    from editable_pptx.env import (
        bg_flatten_enabled,
        crosscheck_enabled,
        font_config,
        layout_snap_enabled,
        shape_detect_enabled,
        snap_cluster_tol_px,
        snap_grid_px,
        text_pad_ratio,
        vlm_enabled,
    )
    from editable_pptx.layout import elements_from_mineru_dir
    from editable_pptx.openai_style import apply_openai_element_styles
    from editable_pptx.shapes import detect_shapes
    from editable_pptx.snap import snap_bboxes

    fc = font_config(deck_dir)
    pad = text_pad_ratio()
    do_snap = layout_snap_enabled()
    do_shapes = shape_detect_enabled()
    do_flat_bg = bg_flatten_enabled()
    grid = snap_grid_px()
    cluster_tol = snap_cluster_tol_px()

    prs = Presentation()
    first = True
    for img, mdir in zip(ordered_image_paths, mineru_dirs):
        im = Image.open(img)
        slide_size = im.size
        els = elements_from_mineru_dir(mdir, slide_size)

        page_bg: tuple[int, int, int] | None = None
        if vlm_enabled():
            logger.info("VLM style extraction for %s", img)
            page_bg = apply_openai_element_styles(img, els)

        # Optional spec hints from upstream planning (Stage 1).
        layout_hints: list[str] = []
        spec = _read_spec_for(img, deck_dir)
        if spec:
            arch = spec.get("layout")
            if arch:
                layout_hints.append(f"layout={arch}")
            for sh in spec.get("shape_hints") or []:
                k = sh.get("kind")
                if k:
                    layout_hints.append(f"hint:{k}")

        shapes_list: list[dict[str, Any]] = []
        if do_shapes:
            shapes_list = detect_shapes(img, els, slide_size, layout_hints=layout_hints)

        if do_snap:
            snap_bboxes(
                els,
                grid_px=grid,
                cluster_tol_px=cluster_tol,
                slide_w_px=slide_size[0],
                slide_h_px=slide_size[1],
            )
            snap_bboxes(
                shapes_list,
                grid_px=grid,
                cluster_tol_px=cluster_tol,
                slide_w_px=slide_size[0],
                slide_h_px=slide_size[1],
            )

        add_slide_from_image(
            prs,
            img,
            els,
            bg_mode=bg_mode,
            set_presentation_dimensions=first,
            text_pad=pad,
            font_body=fc["body"],
            font_title=fc["title"],
            shapes=shapes_list,
            page_bg=page_bg,
            flat_background=do_flat_bg,
        )
        first = False

    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    prs.core_properties.title = output_pptx.stem
    prs.save(str(output_pptx))

    if crosscheck_enabled():
        try:
            from editable_pptx.crosscheck import crosscheck_deck

            logger.info("Crosscheck rendering via LibreOffice...")
            crosscheck_deck(output_pptx, [Path(p) for p in ordered_image_paths])
        except Exception as e:
            logger.warning("Crosscheck skipped: %s", e)


def _read_spec_for(image_path: str, deck_dir: Path | None = None) -> dict[str, Any] | None:
    """Look for `<deck_dir>/prompts/NN-slide-*.spec.json` (deck_dir defaults to image parent)."""
    import json
    import re as _re

    p = Path(image_path)
    m = _re.match(r"^(\d+)-slide-(.+)\.(png|jpg|jpeg)$", p.name, _re.IGNORECASE)
    if not m:
        return None
    base = deck_dir if deck_dir is not None else p.parent
    prompts_dir = base / "prompts"
    if not prompts_dir.is_dir():
        return None
    stem = f"{m.group(1)}-slide-{m.group(2)}"
    spec = prompts_dir / f"{stem}.spec.json"
    if not spec.is_file():
        return None
    try:
        return json.loads(spec.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
