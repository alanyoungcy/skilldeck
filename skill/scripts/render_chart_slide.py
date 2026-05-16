"""Render a chart-slide SVG from a CHART_SPEC dict.

The 1280x720 viewBox matches skill/templates/charts/*.svg so a fresh-rendered
chart sits inside the same canvas the LLM-edited templates use.

Spec shape:
    {
      "template": "bar_chart" | "line_chart" | "pie_chart" | "donut_chart" |
                  "area_chart" | "kpi_cards" | "basic_table" | "comparison_columns",
      "title":    "...",
      "subtitle": "...",
      "x_axis":   ["Q1", "Q2", ...],         # categories (bar/line/area)
      "series":   [{"name": "...", "values": [...], "color": "blue|emerald|..." | "#hex"}],
      "items":    [...],                     # pie/donut/kpi/table-specific
      "palette":  {"accent": "#hex", "background": "#hex"},
      "data_source": "..."
    }

Public API: render_chart_svg(spec) -> str
"""

from __future__ import annotations

import math
from typing import Any

VIEWBOX = (0, 0, 1280, 720)

PALETTE = {
    "blue":    ("#3B82F6", "#2563EB"),
    "emerald": ("#10B981", "#059669"),
    "amber":   ("#F59E0B", "#D97706"),
    "violet":  ("#8B5CF6", "#7C3AED"),
    "rose":    ("#FB7185", "#E11D48"),
    "pink":    ("#EC4899", "#BE185D"),
}

TEXT_PRIMARY   = "#0F172A"
TEXT_SECONDARY = "#64748B"
TEXT_AXIS      = "#475569"
TEXT_FOOTNOTE  = "#94A3B8"
GRID           = "#E0E0E0"
AXIS_LINE      = "#94A3B8"
CARD_BG        = "#F8FAFC"
CARD_STROKE    = "#E2E8F0"
FONT_STACK     = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


def _color_pair(token: str) -> tuple[str, str]:
    """Resolve color token (palette name or hex) to (light, dark) pair."""
    if token in PALETTE:
        return PALETTE[token]
    if token.startswith("#"):
        # Single hex → use it for both stops (no gradient effect).
        return (token, token)
    return PALETTE["blue"]


def _esc(s: Any) -> str:
    """Minimal XML escape for text content."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _header(title: str, subtitle: str) -> str:
    return (
        f'<text x="60" y="80" font-family="{FONT_STACK}" font-size="34" '
        f'font-weight="bold" fill="{TEXT_PRIMARY}">{_esc(title)}</text>\n'
        f'<text x="60" y="115" font-family="{FONT_STACK}" font-size="18" '
        f'fill="{TEXT_SECONDARY}">{_esc(subtitle)}</text>\n'
    )


def _footer(text: str) -> str:
    if not text:
        return ""
    return (
        f'<text x="60" y="700" font-family="{FONT_STACK}" font-size="12" '
        f'fill="{TEXT_FOOTNOTE}">{_esc(text)}</text>\n'
    )


def _gradient_def(grad_id: str, light: str, dark: str) -> str:
    return (
        f'<linearGradient id="{grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'  <stop offset="0%" style="stop-color:{light};stop-opacity:1" />\n'
        f'  <stop offset="100%" style="stop-color:{dark};stop-opacity:1" />\n'
        f'</linearGradient>\n'
    )


def _shadow_def() -> str:
    return (
        '<filter id="barShadow" x="-15%" y="-15%" width="130%" height="130%">\n'
        '  <feGaussianBlur in="SourceAlpha" stdDeviation="2"/>\n'
        '  <feOffset dx="0" dy="1" result="offsetBlur"/>\n'
        '  <feFlood flood-color="#0F172A" flood-opacity="0.15" result="shadowColor"/>\n'
        '  <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>\n'
        '  <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
        '</filter>\n'
    )


def _wrap_svg(defs: str, body: str) -> str:
    vb = " ".join(str(v) for v in VIEWBOX)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" '
        f'width="{VIEWBOX[2]}" height="{VIEWBOX[3]}">\n'
        f'<defs>\n{defs}</defs>\n'
        f'<rect width="{VIEWBOX[2]}" height="{VIEWBOX[3]}" fill="#FFFFFF"/>\n'
        f'{body}'
        f'</svg>\n'
    )


def _nice_max(values: list[float]) -> float:
    """Round max value up to a clean axis bound."""
    if not values:
        return 1.0
    raw = max(values)
    if raw <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(raw))
    for step in (1, 2, 2.5, 5, 10):
        candidate = step * magnitude
        if candidate >= raw:
            return candidate
    return 10 * magnitude


# ---------- Renderers ----------

def render_bar(spec: dict) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    cats = spec.get("x_axis") or []
    series_list = spec.get("series") or []
    if not series_list or not cats:
        return _placeholder("bar_chart needs x_axis + series")

    series = series_list[0]  # single series; multi-series → switch to comparison_columns
    values = [float(v) for v in series.get("values", [])]
    color_token = series.get("color", "blue")
    light, dark = _color_pair(color_token)
    max_v = _nice_max(values)

    # Chart plot area: x 140-1160 (1020 px), y 150-550 (400 px)
    plot_x0, plot_x1 = 140, 1160
    plot_y0, plot_y1 = 150, 550
    plot_h = plot_y1 - plot_y0
    plot_w = plot_x1 - plot_x0

    n = len(values)
    bar_w = min(80, int(plot_w / (n * 2.2)))
    slot_w = plot_w / n

    bars = []
    for i, (cat, v) in enumerate(zip(cats, values)):
        cx = plot_x0 + slot_w * (i + 0.5)
        bx = cx - bar_w / 2
        bh = (v / max_v) * plot_h if max_v else 0
        by = plot_y1 - bh
        bars.append(
            f'<g id="bar-{i+1}">\n'
            f'  <rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" '
            f'rx="4" fill="url(#barGrad)" filter="url(#barShadow)"/>\n'
            f'  <text x="{cx:.1f}" y="{by - 12:.1f}" font-family="{FONT_STACK}" '
            f'font-size="16" font-weight="600" fill="{TEXT_PRIMARY}" text-anchor="middle">{_esc(_fmt_number(v))}</text>\n'
            f'  <text x="{cx:.1f}" y="{plot_y1 + 30:.1f}" font-family="{FONT_STACK}" '
            f'font-size="16" fill="{TEXT_AXIS}" text-anchor="middle">{_esc(cat)}</text>\n'
            f'</g>'
        )

    # Y axis ticks at 0%, 25%, 50%, 75%, 100% of max
    ticks = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y1 - frac * plot_h
        v = frac * max_v
        ticks.append(
            f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4,4"/>\n'
            f'<text x="{plot_x0 - 15}" y="{y + 5:.1f}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_SECONDARY}" text-anchor="end">{_esc(_fmt_number(v))}</text>'
        )

    body = (
        _header(title, subtitle)
        + '<g id="chartArea">\n'
        + "\n".join(ticks) + "\n"
        + f'<line x1="{plot_x0}" y1="{plot_y0}" x2="{plot_x0}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + "\n".join(bars) + "\n"
        + '</g>\n'
        + _footer(spec.get("data_source", ""))
    )
    defs = _gradient_def("barGrad", light, dark) + _shadow_def()
    return _wrap_svg(defs, body)


def render_comparison_columns(spec: dict) -> str:
    """Multi-series grouped bars."""
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    cats = spec.get("x_axis") or []
    series_list = spec.get("series") or []
    if not cats or not series_list:
        return _placeholder("comparison_columns needs x_axis + series")

    plot_x0, plot_x1 = 140, 1160
    plot_y0, plot_y1 = 180, 560
    plot_h = plot_y1 - plot_y0
    plot_w = plot_x1 - plot_x0

    all_vals: list[float] = []
    for s in series_list:
        all_vals.extend(float(v) for v in s.get("values", []))
    max_v = _nice_max(all_vals)

    n_cats = len(cats)
    n_series = len(series_list)
    slot_w = plot_w / n_cats
    group_w = slot_w * 0.7
    bar_w = group_w / n_series

    grad_defs = []
    bars = []
    legend_items = []
    for si, s in enumerate(series_list):
        light, dark = _color_pair(s.get("color", list(PALETTE.keys())[si % len(PALETTE)]))
        gid = f"barGrad{si}"
        grad_defs.append(_gradient_def(gid, light, dark))
        legend_items.append((s.get("name", f"Series {si+1}"), light))
        for i, v in enumerate(s.get("values", [])):
            v = float(v)
            cx = plot_x0 + slot_w * (i + 0.5)
            bx = cx - group_w / 2 + si * bar_w
            bh = (v / max_v) * plot_h if max_v else 0
            by = plot_y1 - bh
            bars.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'rx="3" fill="url(#{gid})"/>\n'
                f'<text x="{bx + bar_w/2:.1f}" y="{by - 6:.1f}" font-family="{FONT_STACK}" '
                f'font-size="13" font-weight="600" fill="{TEXT_PRIMARY}" text-anchor="middle">{_esc(_fmt_number(v))}</text>'
            )

    cat_labels = [
        f'<text x="{plot_x0 + slot_w*(i+0.5):.1f}" y="{plot_y1 + 30}" '
        f'font-family="{FONT_STACK}" font-size="16" fill="{TEXT_AXIS}" '
        f'text-anchor="middle">{_esc(c)}</text>'
        for i, c in enumerate(cats)
    ]

    legend_x = plot_x0
    legend_y = 130
    legend = []
    for label, color in legend_items:
        legend.append(
            f'<rect x="{legend_x}" y="{legend_y - 10}" width="14" height="14" rx="3" fill="{color}"/>\n'
            f'<text x="{legend_x + 22}" y="{legend_y + 2}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_AXIS}">{_esc(label)}</text>'
        )
        legend_x += len(label) * 9 + 60

    ticks = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y1 - frac * plot_h
        v = frac * max_v
        ticks.append(
            f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4,4"/>\n'
            f'<text x="{plot_x0 - 15}" y="{y + 5:.1f}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_SECONDARY}" text-anchor="end">{_esc(_fmt_number(v))}</text>'
        )

    body = (
        _header(title, subtitle)
        + "\n".join(legend) + "\n"
        + '<g id="chartArea">\n'
        + "\n".join(ticks) + "\n"
        + f'<line x1="{plot_x0}" y1="{plot_y0}" x2="{plot_x0}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + "\n".join(bars) + "\n"
        + "\n".join(cat_labels) + "\n"
        + '</g>\n'
        + _footer(spec.get("data_source", ""))
    )
    return _wrap_svg("\n".join(grad_defs), body)


def render_line(spec: dict) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    cats = spec.get("x_axis") or []
    series_list = spec.get("series") or []
    if not cats or not series_list:
        return _placeholder("line_chart needs x_axis + series")

    plot_x0, plot_x1 = 140, 1160
    plot_y0, plot_y1 = 180, 560
    plot_h = plot_y1 - plot_y0
    plot_w = plot_x1 - plot_x0

    all_vals: list[float] = []
    for s in series_list:
        all_vals.extend(float(v) for v in s.get("values", []))
    max_v = _nice_max(all_vals)
    n = len(cats)

    paths = []
    points_layer = []
    legend_items = []
    for si, s in enumerate(series_list):
        light, _ = _color_pair(s.get("color", list(PALETTE.keys())[si % len(PALETTE)]))
        legend_items.append((s.get("name", f"Series {si+1}"), light))
        values = [float(v) for v in s.get("values", [])]
        pts = []
        for i, v in enumerate(values):
            x = plot_x0 + (plot_w if n == 1 else plot_w * i / (n - 1))
            y = plot_y1 - (v / max_v) * plot_h if max_v else plot_y1
            pts.append((x, y, v))
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in pts)
        paths.append(
            f'<path d="{d}" fill="none" stroke="{light}" stroke-width="3" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y, v in pts:
            points_layer.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#FFFFFF" stroke="{light}" stroke-width="2.5"/>\n'
                f'<text x="{x:.1f}" y="{y - 14:.1f}" font-family="{FONT_STACK}" '
                f'font-size="13" font-weight="600" fill="{TEXT_PRIMARY}" text-anchor="middle">{_esc(_fmt_number(v))}</text>'
            )

    cat_labels = []
    for i, c in enumerate(cats):
        x = plot_x0 + (plot_w if n == 1 else plot_w * i / (n - 1))
        cat_labels.append(
            f'<text x="{x:.1f}" y="{plot_y1 + 30}" font-family="{FONT_STACK}" '
            f'font-size="16" fill="{TEXT_AXIS}" text-anchor="middle">{_esc(c)}</text>'
        )

    ticks = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y1 - frac * plot_h
        v = frac * max_v
        ticks.append(
            f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4,4"/>\n'
            f'<text x="{plot_x0 - 15}" y="{y + 5:.1f}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_SECONDARY}" text-anchor="end">{_esc(_fmt_number(v))}</text>'
        )

    legend_x = plot_x0
    legend = []
    for label, color in legend_items:
        legend.append(
            f'<rect x="{legend_x}" y="120" width="14" height="14" rx="3" fill="{color}"/>\n'
            f'<text x="{legend_x + 22}" y="132" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_AXIS}">{_esc(label)}</text>'
        )
        legend_x += len(label) * 9 + 60

    body = (
        _header(title, subtitle)
        + "\n".join(legend) + "\n"
        + '<g id="chartArea">\n'
        + "\n".join(ticks) + "\n"
        + f'<line x1="{plot_x0}" y1="{plot_y0}" x2="{plot_x0}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + "\n".join(paths) + "\n"
        + "\n".join(points_layer) + "\n"
        + "\n".join(cat_labels) + "\n"
        + '</g>\n'
        + _footer(spec.get("data_source", ""))
    )
    return _wrap_svg("", body)


def render_area(spec: dict) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    cats = spec.get("x_axis") or []
    series_list = spec.get("series") or []
    if not cats or not series_list:
        return _placeholder("area_chart needs x_axis + series")
    s = series_list[0]
    light, dark = _color_pair(s.get("color", "blue"))
    values = [float(v) for v in s.get("values", [])]
    max_v = _nice_max(values)
    plot_x0, plot_x1 = 140, 1160
    plot_y0, plot_y1 = 180, 560
    plot_h = plot_y1 - plot_y0
    plot_w = plot_x1 - plot_x0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = plot_x0 + (plot_w if n == 1 else plot_w * i / (n - 1))
        y = plot_y1 - (v / max_v) * plot_h if max_v else plot_y1
        pts.append((x, y, v))
    line_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in pts)
    area_d = (
        f"M {pts[0][0]:.1f} {plot_y1} "
        + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in pts)
        + f" L {pts[-1][0]:.1f} {plot_y1} Z"
    )
    ticks = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y1 - frac * plot_h
        v = frac * max_v
        ticks.append(
            f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x1}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4,4"/>\n'
            f'<text x="{plot_x0 - 15}" y="{y + 5:.1f}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_SECONDARY}" text-anchor="end">{_esc(_fmt_number(v))}</text>'
        )
    cat_labels = []
    for i, c in enumerate(cats):
        x = plot_x0 + (plot_w if n == 1 else plot_w * i / (n - 1))
        cat_labels.append(
            f'<text x="{x:.1f}" y="{plot_y1 + 30}" font-family="{FONT_STACK}" '
            f'font-size="16" fill="{TEXT_AXIS}" text-anchor="middle">{_esc(c)}</text>'
        )
    point_marks = [
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#FFFFFF" stroke="{light}" stroke-width="2.5"/>\n'
        f'<text x="{x:.1f}" y="{y - 14:.1f}" font-family="{FONT_STACK}" '
        f'font-size="13" font-weight="600" fill="{TEXT_PRIMARY}" text-anchor="middle">{_esc(_fmt_number(v))}</text>'
        for x, y, v in pts
    ]
    defs = _gradient_def("areaGrad", light, dark)
    body = (
        _header(title, subtitle)
        + '<g id="chartArea">\n'
        + "\n".join(ticks) + "\n"
        + f'<line x1="{plot_x0}" y1="{plot_y0}" x2="{plot_x0}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + f'<line x1="{plot_x0}" y1="{plot_y1}" x2="{plot_x1}" y2="{plot_y1}" stroke="{AXIS_LINE}" stroke-width="2"/>\n'
        + f'<path d="{area_d}" fill="url(#areaGrad)" fill-opacity="0.55"/>\n'
        + f'<path d="{line_d}" fill="none" stroke="{dark}" stroke-width="3" stroke-linejoin="round"/>\n'
        + "\n".join(point_marks) + "\n"
        + "\n".join(cat_labels) + "\n"
        + '</g>\n'
        + _footer(spec.get("data_source", ""))
    )
    return _wrap_svg(defs, body)


def render_pie(spec: dict, *, donut: bool = False) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    items = spec.get("items") or []
    if not items:
        return _placeholder(("donut" if donut else "pie") + "_chart needs items")
    total = sum(float(it.get("value", 0)) for it in items) or 1.0

    cx, cy = 460, 400
    r = 200
    inner_r = 110 if donut else 0

    palette_keys = list(PALETTE.keys())
    paths = []
    legend = []
    angle = -math.pi / 2  # Start at top
    for i, it in enumerate(items):
        v = float(it.get("value", 0))
        frac = v / total
        sweep = frac * 2 * math.pi
        a0, a1 = angle, angle + sweep
        large = 1 if sweep > math.pi else 0
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        color_token = it.get("color", palette_keys[i % len(palette_keys)])
        light, _ = _color_pair(color_token)
        if donut:
            ix0, iy0 = cx + inner_r * math.cos(a0), cy + inner_r * math.sin(a0)
            ix1, iy1 = cx + inner_r * math.cos(a1), cy + inner_r * math.sin(a1)
            d = (
                f"M {x0:.2f} {y0:.2f} "
                f"A {r} {r} 0 {large} 1 {x1:.2f} {y1:.2f} "
                f"L {ix1:.2f} {iy1:.2f} "
                f"A {inner_r} {inner_r} 0 {large} 0 {ix0:.2f} {iy0:.2f} Z"
            )
        else:
            d = f"M {cx} {cy} L {x0:.2f} {y0:.2f} A {r} {r} 0 {large} 1 {x1:.2f} {y1:.2f} Z"
        paths.append(f'<path d="{d}" fill="{light}" stroke="#FFFFFF" stroke-width="2"/>')

        # Label at midpoint
        amid = (a0 + a1) / 2
        lr = r * 0.65 if donut else r * 0.6
        lx = cx + lr * math.cos(amid)
        ly = cy + lr * math.sin(amid)
        if frac > 0.05:
            paths.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-family="{FONT_STACK}" '
                f'font-size="16" font-weight="600" fill="#FFFFFF" '
                f'text-anchor="middle" dominant-baseline="middle">{frac*100:.0f}%</text>'
            )

        legend.append((it.get("name", f"Item {i+1}"), light, v))
        angle = a1

    if donut:
        paths.append(
            f'<text x="{cx}" y="{cy - 10}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_SECONDARY}" text-anchor="middle">Total</text>\n'
            f'<text x="{cx}" y="{cy + 22}" font-family="{FONT_STACK}" '
            f'font-size="34" font-weight="bold" fill="{TEXT_PRIMARY}" text-anchor="middle">{_esc(_fmt_number(total))}</text>'
        )

    legend_x = 760
    legend_y = 220
    leg = []
    for name, color, v in legend:
        leg.append(
            f'<rect x="{legend_x}" y="{legend_y - 14}" width="18" height="18" rx="4" fill="{color}"/>\n'
            f'<text x="{legend_x + 28}" y="{legend_y}" font-family="{FONT_STACK}" '
            f'font-size="16" fill="{TEXT_PRIMARY}">{_esc(name)}</text>\n'
            f'<text x="{legend_x + 380}" y="{legend_y}" font-family="{FONT_STACK}" '
            f'font-size="16" font-weight="600" fill="{TEXT_AXIS}" text-anchor="end">{_esc(_fmt_number(v))} ({v/total*100:.1f}%)</text>'
        )
        legend_y += 36

    body = (
        _header(title, subtitle)
        + "\n".join(paths) + "\n"
        + "\n".join(leg) + "\n"
        + _footer(spec.get("data_source", ""))
    )
    return _wrap_svg("", body)


def render_donut(spec: dict) -> str:
    return render_pie(spec, donut=True)


def render_kpi_cards(spec: dict) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    items = spec.get("items") or []
    n = len(items)
    if n == 0:
        return _placeholder("kpi_cards needs items")
    n = min(n, 4)
    items = items[:n]

    margin = 60
    gap = 30
    total_w = VIEWBOX[2] - margin * 2
    card_w = (total_w - gap * (n - 1)) / n
    card_h = 280
    card_y = 220

    cards = []
    for i, it in enumerate(items):
        x = margin + i * (card_w + gap)
        accent_token = it.get("color", list(PALETTE.keys())[i % len(PALETTE)])
        accent, _ = _color_pair(accent_token)
        cards.append(
            f'<g id="kpi-{i+1}">\n'
            f'  <rect x="{x:.1f}" y="{card_y}" width="{card_w:.1f}" height="{card_h}" '
            f'rx="14" fill="{CARD_BG}" stroke="{CARD_STROKE}" stroke-width="1.5"/>\n'
            f'  <rect x="{x:.1f}" y="{card_y}" width="6" height="{card_h}" fill="{accent}"/>\n'
            f'  <text x="{x + 28:.1f}" y="{card_y + 56}" font-family="{FONT_STACK}" '
            f'font-size="16" fill="{TEXT_SECONDARY}">{_esc(it.get("label", ""))}</text>\n'
            f'  <text x="{x + 28:.1f}" y="{card_y + 130}" font-family="{FONT_STACK}" '
            f'font-size="56" font-weight="bold" fill="{TEXT_PRIMARY}">{_esc(it.get("value", ""))}</text>\n'
            f'  <text x="{x + 28:.1f}" y="{card_y + 175}" font-family="{FONT_STACK}" '
            f'font-size="18" font-weight="600" fill="{accent}">{_esc(it.get("delta", ""))}</text>\n'
            f'  <text x="{x + 28:.1f}" y="{card_y + 230}" font-family="{FONT_STACK}" '
            f'font-size="14" fill="{TEXT_AXIS}">{_esc(it.get("note", ""))}</text>\n'
            f'</g>'
        )

    body = (
        _header(title, subtitle)
        + "\n".join(cards) + "\n"
        + _footer(spec.get("data_source", ""))
    )
    return _wrap_svg("", body)


def render_basic_table(spec: dict) -> str:
    title = spec.get("title", "")
    subtitle = spec.get("subtitle", "")
    columns = spec.get("columns") or []
    rows = spec.get("rows") or []
    if not columns or not rows:
        return _placeholder("basic_table needs columns + rows")

    margin = 60
    table_w = VIEWBOX[2] - margin * 2
    col_w = table_w / len(columns)
    header_y = 180
    row_h = min(60, max(36, int((520 - 60) / max(1, len(rows)))))

    out = []
    out.append(
        f'<rect x="{margin}" y="{header_y}" width="{table_w}" height="56" '
        f'rx="8" fill="#1E293B"/>'
    )
    for ci, col in enumerate(columns):
        out.append(
            f'<text x="{margin + ci*col_w + 18:.1f}" y="{header_y + 36:.1f}" '
            f'font-family="{FONT_STACK}" font-size="16" font-weight="600" '
            f'fill="#FFFFFF">{_esc(col)}</text>'
        )

    for ri, row in enumerate(rows):
        ry = header_y + 56 + ri * row_h
        if ri % 2 == 1:
            out.append(
                f'<rect x="{margin}" y="{ry}" width="{table_w}" height="{row_h}" fill="{CARD_BG}"/>'
            )
        for ci, val in enumerate(row[: len(columns)]):
            out.append(
                f'<text x="{margin + ci*col_w + 18:.1f}" y="{ry + row_h*0.62:.1f}" '
                f'font-family="{FONT_STACK}" font-size="15" fill="{TEXT_PRIMARY}">{_esc(val)}</text>'
            )
        out.append(
            f'<line x1="{margin}" y1="{ry + row_h:.1f}" x2="{margin + table_w}" '
            f'y2="{ry + row_h:.1f}" stroke="{CARD_STROKE}" stroke-width="1"/>'
        )

    body = _header(title, subtitle) + "\n".join(out) + "\n" + _footer(spec.get("data_source", ""))
    return _wrap_svg("", body)


def _placeholder(message: str) -> str:
    body = (
        f'<rect x="60" y="60" width="1160" height="600" rx="20" fill="#FEF2F2" stroke="#FCA5A5" stroke-width="2"/>\n'
        f'<text x="640" y="380" font-family="{FONT_STACK}" font-size="28" '
        f'font-weight="bold" fill="#991B1B" text-anchor="middle">{_esc(message)}</text>\n'
    )
    return _wrap_svg("", body)


def _fmt_number(v: float) -> str:
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.1f}"


RENDERERS = {
    "bar_chart":          render_bar,
    "line_chart":         render_line,
    "area_chart":         render_area,
    "pie_chart":          render_pie,
    "donut_chart":        render_donut,
    "kpi_cards":          render_kpi_cards,
    "basic_table":        render_basic_table,
    "comparison_columns": render_comparison_columns,
}


def render_chart_svg(spec: dict) -> str:
    template = spec.get("template", "bar_chart")
    fn = RENDERERS.get(template)
    if fn is None:
        return _placeholder(f"Unknown chart template: {template}")
    return fn(spec)


SUPPORTED_TEMPLATES = tuple(RENDERERS.keys())


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Render a chart-slide SVG from a CHART_SPEC JSON file.")
    parser.add_argument("spec_json", type=Path, help="Path to chart-spec JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Output SVG path (default: stdout)")
    args = parser.parse_args()

    with open(args.spec_json, "r", encoding="utf-8") as f:
        spec = json.load(f)
    svg = render_chart_svg(spec)
    if args.output:
        args.output.write_text(svg, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(svg)
