"""CLI: slide-deck directory → editable .pptx (MinerU + edge/whiteout mask + python-pptx)."""

from __future__ import annotations

import argparse
import logging
import re
import tempfile
from pathlib import Path

from editable_pptx.assemble import export_editable_deck
from editable_pptx.canvas import materialize_normalized_slides, resolve_target_canvas_wh
from editable_pptx.env import (
    background_mode,
    hybrid_cv_enabled,
    hybrid_mineru_fallback_enabled,
    load_skilldeck_env,
    mineru_config,
    mineru_poll_timeout,
)
from editable_pptx.mineru import MinerUError, parse_slide_image

SLIDE_PATTERN = re.compile(r"^(\d+)-slide-.*\.(png|jpg|jpeg)$", re.IGNORECASE)
BACKUP_PATTERN = re.compile(r"-backup-\d{8}-\d{6}")

logger = logging.getLogger(__name__)


def list_slide_images(deck_dir: Path) -> list[Path]:
    if not deck_dir.is_dir():
        raise SystemExit(f"Not a directory: {deck_dir}")
    slides: list[Path] = []
    for f in deck_dir.iterdir():
        if not f.is_file():
            continue
        if BACKUP_PATTERN.search(f.name):
            continue
        if SLIDE_PATTERN.match(f.name):
            slides.append(f)
    slides.sort(key=lambda p: int(SLIDE_PATTERN.match(p.name).group(1)))
    return slides


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export editable PPTX from slide PNGs (MinerU layout).")
    parser.add_argument("deck_dir", type=Path, help="Directory with 01-slide-*.png, etc.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .pptx path (default: <deck_dir>/<folder-name>.pptx)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).resolve().parent.parent
    load_skilldeck_env(repo_root)

    cfg = mineru_config()
    use_hybrid = hybrid_cv_enabled()
    use_mineru = bool(cfg["token"]) and (not use_hybrid or hybrid_mineru_fallback_enabled())
    if not cfg["token"] and not use_hybrid:
        raise SystemExit(
            "MINERU_TOKEN is missing. Set it in .env (see .env.example for editable export variables)."
        )

    deck_dir = args.deck_dir.resolve()
    slides = list_slide_images(deck_dir)
    if not slides:
        raise SystemExit(f"No slide images matching NN-slide-*.(png|jpg|jpeg) in {deck_dir}")

    out = args.output
    if not out:
        name = deck_dir.name
        out = deck_dir / f"{name}.pptx"
    out = out.resolve()

    bg_mode = background_mode()
    timeout = mineru_poll_timeout()

    with tempfile.TemporaryDirectory(prefix="editable_pptx_") as work:
        work_root = Path(work)
        tw, th = resolve_target_canvas_wh(slides)
        normalized_dir = work_root / "normalized_slides"
        slides_for_pipeline = materialize_normalized_slides(slides, normalized_dir, tw, th)

        mineru_dirs: list[Path | None] = []
        for i, slide_path in enumerate(slides_for_pipeline):
            wd = work_root / f"slide_{i:03d}"
            if use_mineru:
                logger.info("MinerU parse %s/%s: %s", i + 1, len(slides), slide_path.name)
                try:
                    mdir = parse_slide_image(
                        str(slide_path),
                        token=cfg["token"],
                        api_base=cfg["api_base"],
                        model_version=cfg["model_version"],
                        work_dir=wd,
                        poll_timeout=timeout,
                    )
                    mineru_dirs.append(mdir)
                except MinerUError as e:
                    if not use_hybrid:
                        raise SystemExit(f"MinerU failed for {slide_path.name}: {e}") from e
                    logger.warning("MinerU fallback unavailable for %s: %s", slide_path.name, e)
                    mineru_dirs.append(None)
            else:
                logger.info(
                    "Hybrid CV parse %s/%s without whole-slide MinerU fallback: %s",
                    i + 1,
                    len(slides),
                    slide_path.name,
                )
                mineru_dirs.append(None)

        export_editable_deck(
            [str(s) for s in slides_for_pipeline],
            mineru_dirs,
            out,
            bg_mode=bg_mode,
            deck_dir=deck_dir,
        )

    print(f"Wrote {out}")
