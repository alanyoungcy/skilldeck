"""Load `.env` and read configuration for editable export."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_skilldeck_env(repo_root: Path | None = None) -> None:
    """Load `.env` from skilldeck repo root (same pattern as streamlit_app)."""
    root = repo_root or Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def mineru_config() -> dict[str, str]:
    return {
        "token": os.getenv("MINERU_TOKEN", "").strip(),
        "api_base": os.getenv("MINERU_API_BASE", "https://mineru.net").rstrip("/"),
        "model_version": os.getenv("MINERU_MODEL_VERSION", "vlm"),
    }


def background_mode() -> str:
    """edge | whiteout | none"""
    return os.getenv("EDITABLE_PPTX_BG_MODE", "edge").strip().lower()


def mineru_poll_timeout() -> int:
    return int(os.getenv("MINERU_POLL_TIMEOUT", "600"))


def text_pad_ratio() -> float:
    return float(os.getenv("EDITABLE_PPTX_TEXT_PAD", "1.005"))


def chat_completions_url() -> str:
    """OpenAI-compatible chat completions endpoint."""
    raw = (os.getenv("EDITABLE_PPTX_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        raw = (os.getenv("PLANNING_BASE_URL") or "").strip().rstrip("/")
    if not raw:
        return ""
    if raw.endswith("/chat/completions"):
        return raw
    if raw.endswith("/v1"):
        return f"{raw}/chat/completions"
    return f"{raw}/v1/chat/completions"


def vlm_api_key() -> str:
    return (os.getenv("EDITABLE_PPTX_API_KEY") or os.getenv("PLANNING_API_KEY") or "").strip()


def vlm_style_model() -> str:
    return os.getenv("EDITABLE_PPTX_STYLE_MODEL", "").strip()


def vlm_enabled() -> bool:
    return bool(chat_completions_url() and vlm_api_key() and vlm_style_model())


def _flag(name: str, default: str) -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


def shape_detect_enabled() -> bool:
    return vlm_enabled() and _flag("EDITABLE_PPTX_SHAPE_DETECT", "1")


def layout_snap_enabled() -> bool:
    return _flag("EDITABLE_PPTX_LAYOUT_SNAP", "1")


def bg_flatten_enabled() -> bool:
    """When true, drop the full-page background bitmap and paint a flat fill instead."""
    return _flag("EDITABLE_PPTX_BG_FLATTEN", "0")


def snap_grid_px() -> int:
    try:
        return max(1, int(os.getenv("EDITABLE_PPTX_SNAP_GRID_PX", "8")))
    except ValueError:
        return 8


def snap_cluster_tol_px() -> int:
    try:
        return max(0, int(os.getenv("EDITABLE_PPTX_SNAP_CLUSTER_PX", "10")))
    except ValueError:
        return 10


def crosscheck_enabled() -> bool:
    return vlm_enabled() and _flag("EDITABLE_PPTX_CROSSCHECK", "0")


def soffice_path() -> str:
    p = (os.getenv("EDITABLE_PPTX_SOFFICE") or "").strip()
    if p:
        return p
    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "soffice",
    ]
    for c in candidates:
        if c == "soffice" or Path(c).is_file():
            return c
    return "soffice"


def read_deck_style_slug(deck_dir: Path | None) -> str | None:
    if not deck_dir or not deck_dir.is_dir():
        return None
    conf = deck_dir / "confirmation.yaml"
    if conf.is_file():
        try:
            import yaml

            data = yaml.safe_load(conf.read_text(encoding="utf-8")) or {}
            params = data.get("params") or {}
            s = params.get("style")
            if s:
                return str(s).strip()
        except Exception:
            pass
    outline = deck_dir / "outline.md"
    if outline.is_file():
        for line in outline.read_text(encoding="utf-8").splitlines()[:50]:
            stripped = line.strip()
            if stripped.lower().startswith("style:"):
                return stripped.split(":", 1)[1].strip()
    return None


def font_config(deck_dir: Path | None) -> dict[str, str | None]:
    body = os.getenv("EDITABLE_PPTX_FONT_NAME", "").strip() or None
    title = os.getenv("EDITABLE_PPTX_TITLE_FONT_NAME", "").strip() or None
    slug = read_deck_style_slug(deck_dir)
    if slug == "sketch-notes":
        body = body or "Patrick Hand"
        title = title or body
    return {"body": body, "title": title}
