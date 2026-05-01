"""Render the produced PPTX back to PNGs via LibreOffice and ask the VLM
to score similarity vs the source slides. Quality gate, not auto-retry.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from editable_pptx.env import (
    chat_completions_url,
    crosscheck_enabled,
    soffice_path,
    vlm_api_key,
    vlm_style_model,
)
from editable_pptx.openai_style import (
    _chat,
    _image_to_data_url,
    _parse_json_content,
)

logger = logging.getLogger(__name__)


def _convert_pptx_to_pdf(pptx: Path, out_dir: Path) -> Path | None:
    cmd = [
        soffice_path(),
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(pptx),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("soffice conversion failed: %s", e)
        return None
    pdf = out_dir / (pptx.stem + ".pdf")
    return pdf if pdf.is_file() else None


def _pdf_to_pngs(pdf: Path, out_dir: Path) -> list[Path]:
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf), dpi=120)
        paths: list[Path] = []
        for i, im in enumerate(images, 1):
            p = out_dir / f"rendered_{i:03d}.png"
            im.save(p, "PNG")
            paths.append(p)
        return paths
    except Exception as e:
        logger.warning("pdf2image failed (poppler missing?): %s", e)
        return []


def _score_pair(source_png: Path, rendered_png: Path) -> dict | None:
    url = chat_completions_url()
    api_key = vlm_api_key()
    model = vlm_style_model()
    src_url = _image_to_data_url(str(source_png))
    rnd_url = _image_to_data_url(str(rendered_png))
    prompt = (
        "Compare the SOURCE slide (first image) with the RECONSTRUCTED slide (second image). "
        "Return ONLY valid JSON: "
        '{"similarity":0.0-1.0,"missing":["..."],"wrong":["..."],"notes":"short"}'
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": src_url}},
                {"type": "image_url", "image_url": {"url": rnd_url}},
            ],
        }
    ]
    try:
        raw = _chat(url, api_key, model, messages, use_json_mode=True)
        return _parse_json_content(raw)
    except Exception as e:
        logger.debug("crosscheck score failed: %s", e)
        return None


def crosscheck_deck(
    pptx: Path,
    source_pngs: list[Path],
    *,
    threshold: float = 0.6,
) -> list[dict]:
    """Convert pptx -> pdf -> per-slide pngs, score each vs source. Returns per-slide reports."""
    if not crosscheck_enabled():
        return []
    if not pptx.is_file():
        return []
    with tempfile.TemporaryDirectory(prefix="crosscheck_") as work:
        wd = Path(work)
        pdf = _convert_pptx_to_pdf(pptx, wd)
        if not pdf:
            return []
        rendered = _pdf_to_pngs(pdf, wd)
        if not rendered:
            return []
        reports: list[dict] = []
        for i, src in enumerate(source_pngs):
            if i >= len(rendered):
                break
            r = _score_pair(src, rendered[i]) or {}
            r["slide_index"] = i + 1
            r["source"] = str(src)
            reports.append(r)
            sim = r.get("similarity")
            if isinstance(sim, (int, float)) and sim < threshold:
                logger.warning(
                    "Slide %s reconstruction below threshold (sim=%.2f): %s",
                    i + 1,
                    sim,
                    r.get("notes", ""),
                )
        report_path = pptx.parent / "crosscheck_report.json"
        try:
            report_path.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return reports


# Sanity check that soffice path is callable; intentionally swallow result —
# diagnostic only.
def soffice_available() -> bool:
    try:
        subprocess.run(
            [soffice_path(), "--version"], capture_output=True, timeout=10, check=True
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


_VERSION_RE = re.compile(r"LibreOffice\s+(\d+)\.(\d+)")


def soffice_version() -> str | None:
    try:
        out = subprocess.run(
            [soffice_path(), "--version"], capture_output=True, timeout=10, text=True
        ).stdout
    except Exception:
        return None
    m = _VERSION_RE.search(out or "")
    return f"{m.group(1)}.{m.group(2)}" if m else (out or None)
