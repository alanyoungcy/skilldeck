"""Layout snap & alignment: round bboxes to a grid, then cluster edges.

Operates on element dicts in place. Each element is expected to have
`bbox = [x0, y0, x1, y1]` in slide-pixel coordinates.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _snap_value(v: float, grid: int) -> float:
    if grid <= 1:
        return v
    return float(round(v / grid) * grid)


def _cluster_1d(values: list[float], tol: float) -> dict[float, float]:
    """Single-link cluster on 1D values; map each value -> cluster centroid."""
    if not values:
        return {}
    sorted_unique = sorted(set(values))
    clusters: list[list[float]] = [[sorted_unique[0]]]
    for v in sorted_unique[1:]:
        if v - clusters[-1][-1] <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    out: dict[float, float] = {}
    for cl in clusters:
        centroid = sum(cl) / len(cl)
        for v in cl:
            out[v] = centroid
    return out


def snap_bboxes(
    elements: list[dict[str, Any]],
    *,
    grid_px: int = 8,
    cluster_tol_px: int = 10,
    slide_w_px: int | None = None,
    slide_h_px: int | None = None,
) -> None:
    """Mutate `bbox` on each element in place.

    Step 1 — round each edge to `grid_px`.
    Step 2 — cluster left edges, right edges, horizontal centers, top edges,
    and bottom edges within `cluster_tol_px`; snap members of each cluster to
    its centroid. This is what produces visible alignment columns.
    """
    if not elements:
        return

    # Step 1: pixel-grid snap.
    for el in elements:
        bb = el.get("bbox")
        if not bb or len(bb) != 4:
            continue
        x0, y0, x1, y1 = bb
        sx0 = _snap_value(x0, grid_px)
        sy0 = _snap_value(y0, grid_px)
        sx1 = _snap_value(x1, grid_px)
        sy1 = _snap_value(y1, grid_px)
        if slide_w_px is not None:
            sx0 = max(0.0, min(sx0, float(slide_w_px)))
            sx1 = max(sx0 + grid_px, min(sx1, float(slide_w_px)))
        if slide_h_px is not None:
            sy0 = max(0.0, min(sy0, float(slide_h_px)))
            sy1 = max(sy0 + grid_px, min(sy1, float(slide_h_px)))
        el["bbox"] = [sx0, sy0, sx1, sy1]

    # Step 2: edge / center clustering.
    lefts = [el["bbox"][0] for el in elements if el.get("bbox")]
    rights = [el["bbox"][2] for el in elements if el.get("bbox")]
    tops = [el["bbox"][1] for el in elements if el.get("bbox")]
    bottoms = [el["bbox"][3] for el in elements if el.get("bbox")]
    h_centers = [(el["bbox"][0] + el["bbox"][2]) / 2 for el in elements if el.get("bbox")]

    left_map = _cluster_1d(lefts, cluster_tol_px)
    right_map = _cluster_1d(rights, cluster_tol_px)
    top_map = _cluster_1d(tops, cluster_tol_px)
    bottom_map = _cluster_1d(bottoms, cluster_tol_px)
    hc_map = _cluster_1d(h_centers, cluster_tol_px)

    for el in elements:
        bb = el.get("bbox")
        if not bb or len(bb) != 4:
            continue
        x0, y0, x1, y1 = bb
        nx0 = left_map.get(x0, x0)
        nx1 = right_map.get(x1, x1)
        ny0 = top_map.get(y0, y0)
        ny1 = bottom_map.get(y1, y1)
        # Center alignment: prefer center cluster if it leaves a sensible width.
        old_cx = (x0 + x1) / 2
        new_cx = hc_map.get(old_cx, old_cx)
        if abs(new_cx - old_cx) > 0 and abs(new_cx - old_cx) <= cluster_tol_px:
            half = (nx1 - nx0) / 2
            nx0 = new_cx - half
            nx1 = new_cx + half
        # Guard against collapsed boxes from over-eager clustering.
        if nx1 - nx0 < grid_px:
            nx1 = nx0 + max(grid_px, x1 - x0)
        if ny1 - ny0 < grid_px:
            ny1 = ny0 + max(grid_px, y1 - y0)
        el["bbox"] = [nx0, ny0, nx1, ny1]
