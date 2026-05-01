"""Parse MinerU layout.json into scaled elements (MinerU-only, no hybrid)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Skip painting text under these (raster / structural)
RASTER_TYPES = frozenset({"image", "figure", "chart", "diagram", "table"})


def _extract_text_from_lines(lines: list[dict]) -> list[str]:
    line_texts: list[str] = []
    for line in lines:
        span_texts: list[str] = []
        for span in line.get("spans", []):
            st = span.get("type", "")
            sc = span.get("content", "")
            if st == "text" and sc:
                span_texts.append(sc)
            elif st == "inline_equation" and sc:
                span_texts.append(sc)
        if span_texts:
            line_texts.append("".join(span_texts))
    return line_texts


def _process_block(block: dict, mineru_dir: Path, scale_x: float, scale_y: float) -> dict[str, Any] | None:
    bbox = block.get("bbox")
    block_type = block.get("type", "text")
    if not bbox or len(bbox) != 4:
        return None

    if block_type in ("header", "footer"):
        all_text: list[str] = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("type") == "text" and span.get("content"):
                    all_text.append(span["content"])
        if "".join(all_text).strip() == "#":
            return None

    scaled_bbox = [
        bbox[0] * scale_x,
        bbox[1] * scale_y,
        bbox[2] * scale_x,
        bbox[3] * scale_y,
    ]

    actual_type = block_type
    if block_type in ("header", "footer"):
        has_image = False
        for sub in block.get("blocks", []):
            if sub.get("type") == "image_body":
                has_image = True
                break
        has_text = False
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("type") in ("text", "inline_equation") and (span.get("content") or "").strip():
                    has_text = True
                    break
            if has_text:
                break
        if has_image and not has_text:
            actual_type = "image"
        else:
            actual_type = "text"

    content: str | None = None
    if actual_type in ("text", "title", "table_caption", "image_caption"):
        if block.get("lines"):
            lt = _extract_text_from_lines(block["lines"])
            if lt:
                content = "\n".join(lt).strip()
    elif actual_type == "list":
        if block.get("blocks"):
            all_lines: list[str] = []
            for sub in block["blocks"]:
                if sub.get("lines"):
                    all_lines.extend(_extract_text_from_lines(sub["lines"]))
            if all_lines:
                content = "\n".join(all_lines).strip()

    img_path: str | None = None
    if actual_type in ("image", "table"):
        for sub in block.get("blocks", []):
            for line in sub.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("image_path"):
                        rel = span["image_path"]
                        if not str(rel).startswith("images/"):
                            rel = "images/" + str(rel)
                        abs_path = mineru_dir / rel
                        if abs_path.exists():
                            img_path = str(abs_path)
                        break
                if img_path:
                    break
            if img_path:
                break

    return {
        "bbox": scaled_bbox,
        "type": actual_type,
        "content": content,
        "image_path": img_path,
        "metadata": block,
    }


def elements_from_mineru_dir(mineru_dir: Path, target_image_size: tuple[int, int]) -> list[dict[str, Any]]:
    """Read layout.json and return elements scaled to target_image_size (width, height)."""
    layout_file = mineru_dir / "layout.json"
    if not layout_file.is_file():
        logger.warning("Missing layout.json in %s", mineru_dir)
        return []

    layout_data = json.loads(layout_file.read_text(encoding="utf-8"))
    if "pdf_info" not in layout_data or not layout_data["pdf_info"]:
        return []

    page_info = layout_data["pdf_info"][0]
    source_page_size = page_info.get("page_size", list(target_image_size))
    sw, sh = float(source_page_size[0]), float(source_page_size[1])
    tw, th = float(target_image_size[0]), float(target_image_size[1])
    scale_x = tw / sw if sw else 1.0
    scale_y = th / sh if sh else 1.0

    elements: list[dict[str, Any]] = []

    def collect_from_blocks(blocks: list[dict]) -> None:
        for block in blocks:
            el = _process_block(block, mineru_dir, scale_x, scale_y)
            if el:
                elements.append(el)
            if block.get("type", "") != "list":
                for sub in block.get("blocks", []):
                    sub_el = _process_block(sub, mineru_dir, scale_x, scale_y)
                    if sub_el:
                        elements.append(sub_el)

    collect_from_blocks(page_info.get("para_blocks", []))
    collect_from_blocks(page_info.get("discarded_blocks", []))

    logger.info("Parsed %d layout elements from MinerU", len(elements))
    return elements


def should_whiteout(el: dict[str, Any]) -> bool:
    t = el.get("type", "")
    if t in RASTER_TYPES:
        return False
    if el.get("content"):
        return True
    return t in ("text", "title", "list", "paragraph", "header", "footer")
