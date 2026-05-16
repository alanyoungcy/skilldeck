"""Pure path/IO helpers used by streamlit_app and tests.

Kept Streamlit-free so unit tests can import these directly without spinning
up a Streamlit runtime.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

_BACKUP_RE = re.compile(r"-backup-\d{8}-\d{6}")


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_if_exists(path: Path) -> None:
    if not path.exists():
        return
    backup = path.with_name(f"{path.stem}-backup-{now_ts()}{path.suffix}")
    shutil.move(str(path), str(backup))


def is_active_slide_file(p: Path) -> bool:
    """True for `NN-slide-…` artifacts that aren't backup snapshots."""
    return not _BACKUP_RE.search(p.name)


def list_active_slide_files(root: Path, suffix_glob: str) -> list[Path]:
    """List `NN-slide-*<suffix_glob>` under root, excluding `*-backup-*` files.

    `suffix_glob` is the trailing pattern after the slide stem, e.g. `.md`,
    `.chart.json`, `.png`, `.svg`. Sorted by NN.
    """
    pattern = f"[0-9][0-9]-slide-*{suffix_glob}"
    out = [p for p in root.glob(pattern) if is_active_slide_file(p)]
    out.sort(key=lambda p: p.name)
    return out


def write_text_if_changed(path: Path, text: str) -> bool:
    """Write `text` to `path` only when contents differ.

    If `path` exists with identical content, return False (no-op, no backup).
    Otherwise back up the existing file (if any) and write. Returns True when
    a write happened.
    """
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            existing = None
        if existing == text:
            return False
    backup_if_exists(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def write_bytes_if_changed(path: Path, data: bytes) -> bool:
    """Bytes-mode equivalent of `write_text_if_changed`."""
    if path.exists():
        try:
            if path.read_bytes() == data:
                return False
        except OSError:
            pass
    backup_if_exists(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def resolve_pdf_export_flag(explicit: bool | None) -> bool:
    """Decide whether to export PDF.

    `explicit` wins when not None. Otherwise falls back to the
    `SKILLDECK_EXPORT_PDF` environment variable (default: enabled).
    """
    if explicit is not None:
        return bool(explicit)
    env_pdf = (os.getenv("SKILLDECK_EXPORT_PDF", "1") or "").strip().lower()
    return env_pdf in ("1", "true", "yes", "on")


def pdf_cache_is_fresh(deck_dir: Path, slug: str) -> bool:
    """True when the cached PDF still matches the current PPTX bytes.

    Reads `<deck>/.pdf-cache.sha256`. Compares to sha256 of `<slug>.pptx`.
    Both PPTX and PDF must exist for the cache to be considered valid.
    """
    pptx = deck_dir / f"{slug}.pptx"
    pdf = deck_dir / f"{slug}.pdf"
    cache = deck_dir / ".pdf-cache.sha256"
    if not (pptx.is_file() and pdf.is_file() and cache.is_file()):
        return False
    try:
        cached = cache.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    current = hashlib.sha256(pptx.read_bytes()).hexdigest()
    return cached == current


def write_pdf_cache(deck_dir: Path, slug: str) -> None:
    """Persist the current PPTX hash so future runs can skip PDF conversion."""
    pptx = deck_dir / f"{slug}.pptx"
    if not pptx.is_file():
        return
    cache = deck_dir / ".pdf-cache.sha256"
    cache.write_text(hashlib.sha256(pptx.read_bytes()).hexdigest(), encoding="utf-8")
