from __future__ import annotations

import base64
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st
import yaml
from PIL import Image, ImageOps
from pypdf import PdfReader
from dotenv import load_dotenv

from notebooklm_style_agent.refs import StylePreset, list_style_presets, load_style_preset_text
from progress import ProgressBus, Stage
from concept import (
    ConceptError,
    generate_style_anchor,
    generate_visual_concept,
    hash_outline_block,
    is_concept_stale,
    read_concept_file,
    render_concept_prompt,
    write_concept_file,
)
from skilldeck_utils import (
    backup_if_exists,
    is_active_slide_file,
    list_active_slide_files,
    now_ts,
    pdf_cache_is_fresh,
    resolve_pdf_export_flag,
    write_bytes_if_changed,
    write_pdf_cache,
    write_text_if_changed,
)

REPO_DIR = Path(__file__).resolve().parent
SKILL_DIR = REPO_DIR / "skill"
DECKS_DIR = REPO_DIR / "slide-deck"


@dataclasses.dataclass(frozen=True)
class Preferences:
    style: str = "blueprint"
    audience: str = "general"
    language: str = "auto"
    review: bool = True
    preferred_image_backend: str = "auto"
    dimensions: dict[str, str] | None = None


SIGNALS_TO_PRESET: list[tuple[list[str], str]] = [
    (["tutorial", "learn", "education", "guide", "beginner"], "sketch-notes"),
    (["hand-drawn", "infographic", "diagram", "process", "onboarding"], "hand-drawn-edu"),
    (["classroom", "teaching", "school", "chalkboard"], "chalkboard"),
    (["architecture", "system", "data", "analysis", "technical"], "blueprint"),
    (["creative", "children", "kids", "cute"], "vector-illustration"),
    (["briefing", "academic", "research", "bilingual"], "intuition-machine"),
    (["executive", "minimal", "clean", "simple"], "minimal"),
    (["saas", "product", "dashboard", "metrics"], "notion"),
    (["investor", "quarterly", "business", "corporate"], "corporate"),
    (["launch", "marketing", "keynote", "magazine"], "bold-editorial"),
    (["entertainment", "music", "gaming", "atmospheric"], "dark-atmospheric"),
    (["explainer", "journalism", "science communication"], "editorial-infographic"),
    (["story", "fantasy", "animation", "magical"], "fantasy-animation"),
    (["gaming", "retro", "pixel", "developer"], "pixel-art"),
    (["biology", "chemistry", "medical", "scientific"], "scientific"),
    (["history", "heritage", "vintage", "expedition"], "vintage"),
    (["lifestyle", "wellness", "travel", "artistic"], "watercolor"),
]


def slugify(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^a-z0-9\s-]+", "", t)
    t = re.sub(r"\s+", "-", t).strip("-")
    return t[:40] or "slide-deck"


def detect_language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def recommend_slide_count(word_count: int) -> int:
    if word_count < 200:
        return 1
    if word_count < 1000:
        return 5
    if word_count < 3000:
        return 14
    if word_count < 5000:
        return 20
    return 26


def recommend_style_preset(text: str) -> str:
    t = text.lower()
    for keywords, preset in SIGNALS_TO_PRESET:
        if any(k in t for k in keywords):
            return preset
    return "blueprint"


def format_style_preset_label(preset_name: str, presets: list[StylePreset]) -> str:
    preset = next((p for p in presets if p.name == preset_name), None)
    return preset.label if preset is not None else preset_name


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def load_extend_md() -> tuple[Preferences, Path | None]:
    candidates = [
        REPO_DIR / ".skilldeck" / "EXTEND.md",
        Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "skilldeck"
        / "EXTEND.md",
        Path.home() / ".skilldeck" / "EXTEND.md",
    ]
    for p in candidates:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            dims = data.get("dimensions")
            prefs = Preferences(
                style=str(data.get("style", "blueprint")),
                audience=str(data.get("audience", "general")),
                language=str(data.get("language", "auto")),
                review=bool(data.get("review", True)),
                preferred_image_backend=str(data.get("preferred_image_backend", "auto")),
                dimensions=dims if isinstance(dims, dict) else None,
            )
            return prefs, p
    return Preferences(), None


def read_ref_text(rel_path: str) -> str:
    p = SKILL_DIR / "references" / rel_path
    return p.read_text(encoding="utf-8")


def resolve_bun_x() -> list[str]:
    if shutil.which("bun"):
        return ["bun"]
    if shutil.which("npx"):
        return ["npx", "-y", "bun"]
    return []


def load_app_config() -> dict[str, Any]:
    cfg_path = REPO_DIR / "app_config.yaml"
    if not cfg_path.exists():
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def _get(cfg: dict[str, Any], path: str, default: Any) -> Any:
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def env_default(key: str, fallback: str = "") -> str:
    v = os.getenv(key)
    return v if v is not None else fallback


def load_dotenv_robust(dotenv_path: Path) -> None:
    """
    python-dotenv does not override existing env vars by default.
    If the shell exports empty PLANNING_* / IMAGE_*, `.env` values would be ignored.
    We override so the file is authoritative for this app.
    """
    load_dotenv(dotenv_path, override=True)


def _http_error(url: str, r: requests.Response) -> RuntimeError:
    return RuntimeError(f"HTTP {r.status_code} at {url}\n\n{r.text}")


def generate_image_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    size: str,
) -> bytes:
    url = base_url.rstrip("/") + "/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt, "size": size, "response_format": "b64_json"}
    r = requests.post(url, headers=headers, json=payload, timeout=300)
    if not r.ok:
        raise _http_error(url, r)
    j = r.json()
    b64 = j["data"][0]["b64_json"]
    return base64.b64decode(b64)


def _parse_image_size_wh(size: str) -> tuple[int, int]:
    s = size.strip().lower().replace(" ", "").replace("×", "x")
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        raise ValueError(f"Invalid image size (expected WxH): {size!r}")
    return int(m.group(1)), int(m.group(2))


def normalize_generated_image_png(png_bytes: bytes, size: str) -> bytes:
    """Force output to exact width×height from Streamlit / IMAGE_SIZE.

    Some image backends ignore `size` or return preset dimensions (e.g. 1024²).
    We scale uniformly to fit inside the target frame, center on white (#FFFFFF),
    then save as RGB PNG so every slide matches for PPTX / MinerU.
    """
    tw, th = _parse_image_size_wh(size)
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if im.size == (tw, th):
        out = io.BytesIO()
        im.save(out, format="PNG", compress_level=6)
        return out.getvalue()
    fitted = ImageOps.contain(im, (tw, th), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (255, 255, 255, 255))
    ox = (tw - fitted.width) // 2
    oy = (th - fitted.height) // 2
    canvas.paste(fitted, (ox, oy))
    rgb = Image.new("RGB", (tw, th), (255, 255, 255))
    rgb.paste(canvas, mask=canvas.split()[3])
    out = io.BytesIO()
    rgb.save(out, format="PNG", compress_level=6)
    return out.getvalue()


def chat_completion_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _extract_error_message(body_text: str) -> str:
        try:
            j = json.loads(body_text)
            err = j.get("error") if isinstance(j, dict) else None
            if isinstance(err, dict) and isinstance(err.get("message"), str):
                return err["message"]
        except Exception:
            pass
        return body_text

    def _post(payload: dict[str, Any]) -> tuple[requests.Response, dict[str, Any] | None]:
        r = requests.post(url, headers=headers, json=payload, timeout=300)
        if r.ok:
            return r, r.json()
        return r, None

    payload: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": int(max_tokens)}

    r, j = _post(payload)
    if not r.ok:
        err_msg = _extract_error_message(r.text).lower()
        if "max_tokens" in err_msg and ("unsupported" in err_msg or "unknown" in err_msg or "invalid" in err_msg):
            payload3: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": int(max_tokens),
            }
            r3, j3 = _post(payload3)
            if r3.ok and j3 is not None:
                return j3["choices"][0]["message"]["content"]
            raise _http_error(url, r3)
        raise _http_error(url, r)

    assert j is not None
    return j["choices"][0]["message"]["content"]


def _snap16(n: int, mode: str) -> int:
    r = n % 16
    if r == 0:
        return n
    down = n - r
    up = n + (16 - r)
    if mode == "down":
        return down
    if mode == "up":
        return up
    # nearest (default): tie -> up
    return up if (up - n) <= (n - down) else down


def normalize_image_size(raw: str) -> str:
    """
    Normalize a size string and enforce the backend constraint:
    width and height must both be divisible by 16.
    """
    s = raw.strip().lower().replace(" ", "")
    s = s.replace("×", "x")
    if not s:
        s = "1920x1080"
    m = re.match(r"^(\d+)x(\d+)$", s)
    if not m:
        return "1920x1088"
    w = int(m.group(1))
    h = int(m.group(2))
    w2 = _snap16(w, "nearest")
    h2 = _snap16(h, "nearest")
    # common case: 1920x1080 -> 1920x1088
    return f"{w2}x{h2}"


def compute_image_size(
    *,
    aspect: str,
    target_width: int,
    target_height: int,
    snap_mode: str,
) -> str:
    if aspect == "custom":
        w = _snap16(int(target_width), snap_mode)
        h = _snap16(int(target_height), snap_mode)
        return f"{w}x{h}"

    # 16:9 or 4:3
    if aspect == "16:9":
        w = _snap16(int(target_width), snap_mode)
        h_raw = int(round(w * 9 / 16))
        h = _snap16(h_raw, snap_mode)
        return f"{w}x{h}"

    if aspect == "4:3":
        w = _snap16(int(target_width), snap_mode)
        h_raw = int(round(w * 3 / 4))
        h = _snap16(h_raw, snap_mode)
        return f"{w}x{h}"

    # fallback
    return normalize_image_size("1920x1080")


def get_session_deck_dir(topic_slug: str) -> Path:
    return DECKS_DIR / topic_slug


def parse_style_instructions(outline_md: str) -> str:
    m = re.search(r"<STYLE_INSTRUCTIONS>([\s\S]*?)</STYLE_INSTRUCTIONS>", outline_md)
    if not m:
        return ""
    return "<STYLE_INSTRUCTIONS>\n" + m.group(1).strip() + "\n</STYLE_INSTRUCTIONS>"


def split_slide_blocks(outline_md: str) -> list[str]:
    """
    Split outline into slide blocks by headings like:
    ## Slide 3 of 10

    The template uses `---` separators, but models often omit them; heading-based splitting is more reliable.
    """
    # Find slide heading positions
    headings = list(re.finditer(r"^## Slide \d+ of \d+\s*$", outline_md, flags=re.MULTILINE))
    if not headings:
        return []

    blocks: list[str] = []
    for i, m in enumerate(headings):
        start = m.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(outline_md)
        block = outline_md[start:end].strip()
        if block:
            blocks.append(block)
    return blocks


def parse_slides(outline_md: str) -> list[str]:
    by_heading = split_slide_blocks(outline_md)
    if by_heading:
        return by_heading
    # Fallback: legacy separator style
    parts = [p.strip() for p in outline_md.split("\n---\n")]
    return [p for p in parts if p.startswith("## Slide ")]


def _extract_design_spec(slide_block: str) -> dict | None:
    """Optional <DESIGN_SPEC>...</DESIGN_SPEC> JSON block per slide.

    Used downstream by `editable_pptx` to hint shape detection and styling.
    Returns None if the block is missing or unparsable.
    """
    return _extract_json_block(slide_block, "DESIGN_SPEC")


def _extract_chart_spec(slide_block: str) -> dict | None:
    """Optional <CHART_SPEC>...</CHART_SPEC> JSON block per slide.

    When present, the slide is rendered as a programmatic SVG chart instead of an AI image.
    """
    return _extract_json_block(slide_block, "CHART_SPEC")


def _extract_json_block(slide_block: str, tag: str) -> dict | None:
    import json as _json

    m = re.search(rf"<{tag}>([\s\S]*?)</{tag}>", slide_block)
    if not m:
        return None
    body = m.group(1).strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", body)
    if fence:
        body = fence.group(1).strip()
    try:
        data = _json.loads(body)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return None


def _slide_render_kind(slide_block: str) -> str:
    """Return 'chart' if a CHART_SPEC block is present (or **Render**: chart line is set), else 'image'."""
    if re.search(r"^\*\*Render\*\*:\s*chart\s*$", slide_block, re.MULTILINE | re.IGNORECASE):
        return "chart"
    if _extract_chart_spec(slide_block) is not None:
        return "chart"
    return "image"


def _slide_filename(slide_block: str, fallback_ext: str = "png") -> str:
    m = re.search(r"^\*\*Filename\*\*:\s*(.+)$", slide_block, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return f"{now_ts()}-slide.{fallback_ext}"


def _slide_field(slide_block: str, name: str) -> str:
    """Extract a `Name: value` line from a slide block.

    Looks for both the Markdown `**Name**: value` form and the inline
    `Name: value` form used inside `// KEY CONTENT` blocks. Returns the
    first match or empty string.
    """
    m = re.search(rf"^\*\*{re.escape(name)}\*\*:\s*(.+)$", slide_block, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(rf"^{re.escape(name)}:\s*(.+)$", slide_block, re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _slide_body_bullets(slide_block: str) -> list[str]:
    """Extract the `Body:` bullet list from a slide block.

    Handles the SKILL outline's two shapes:
      Body:
      - first point
      - second point
    and the inline-on-one-line "Body: text" fallback (rare; treated as one bullet).
    """
    # Find the literal "Body:" line and read the consecutive `- ...` lines below it.
    lines = slide_block.splitlines()
    bullets: list[str] = []
    in_body = False
    for raw in lines:
        stripped = raw.strip()
        if not in_body:
            m = re.match(r"^(?:\*\*Body\*\*|Body)\s*:\s*(.*)$", stripped, re.IGNORECASE)
            if m:
                in_body = True
                tail = m.group(1).strip()
                if tail and not tail.startswith("-"):
                    bullets.append(tail)
                continue
        else:
            if stripped.startswith("- "):
                bullets.append(stripped[2:].strip())
                continue
            if stripped == "" or stripped.startswith("//") or stripped.startswith("**"):
                # End of body block.
                break
    return [b for b in bullets if b]


def _slide_role(slide_block: str) -> str:
    """Slide role: 'cover' | 'back-cover' | 'content' | (custom)."""
    explicit = _slide_field(slide_block, "Role")
    if explicit:
        return explicit.lower()
    typ = _slide_field(slide_block, "Type").lower()
    if "back cover" in typ:
        return "back-cover"
    if typ == "cover":
        return "cover"
    return "content"


def _slide_architype(slide_block: str) -> str:
    """Layout architype name. Falls back to a role-driven default."""
    layout = _slide_field(slide_block, "Layout")
    if layout:
        return layout.lower()
    role = _slide_role(slide_block)
    return {
        "cover": "title-hero",
        "back-cover": "quote-callout",
    }.get(role, "hero_with_bullets")


def _architype_description(name: str) -> str:
    """Short human-readable description for a layout architype.

    Keeps the Stage 4 prompt self-contained; the LLM doesn't need the full
    layout gallery, just enough context to compose. Unknown architypes fall
    back to a generic description.
    """
    desc = {
        "title-hero": "large centered title + subtitle on a hero visual",
        "metaphor_split": "visual metaphor on one side, text reserved on the other",
        "two_column_compare": "side-by-side A vs B, parallel framing",
        "data_with_visual": "chart on one side, illustrative concept on the other",
        "hero_with_bullets": "one focal visual + supporting bullet list",
        "full_bleed_hero": "one dominant image, headline overlaid on a quiet zone",
        "icon-grid": "grid of icons with labels for features or benefits",
        "split-screen": "half image, half text",
        "quote-callout": "featured quote with attribution",
        "key-stat": "single large number as focal point",
        "agenda": "numbered list with highlights",
        "bullet-list": "structured bullet points",
        "linear-progression": "sequential flow left-to-right (timeline / steps)",
        "binary-comparison": "side-by-side A vs B (before/after, pros/cons)",
        "comparison-matrix": "multi-factor grid",
        "hierarchical-layers": "pyramid or stacked levels",
        "hub-spoke": "central node with radiating items",
        "bento-grid": "varied-size tiles",
        "funnel": "narrowing stages",
        "dashboard": "metrics with charts/numbers",
        "venn-diagram": "overlapping circles",
        "circular-flow": "continuous cycle",
        "winding-roadmap": "curved path with milestones",
        "tree-branching": "parent-child hierarchy",
        "iceberg": "visible vs hidden layers",
        "bridge": "gap with connection (problem-solution)",
    }
    return desc.get(name.lower(), "one focal visual + supporting text")


def write_prompt_files(*, deck_dir: Path, outline_md: str) -> None:
    style_block = parse_style_instructions(outline_md)
    slides_blocks = parse_slides(outline_md)
    if not style_block or not slides_blocks:
        raise RuntimeError("Could not parse outline.md (missing <STYLE_INSTRUCTIONS> or slide blocks).")

    base_prompt = read_ref_text("base-prompt.md")
    ensure_dir(deck_dir / "prompts")

    for sb in slides_blocks:
        kind = _slide_render_kind(sb)
        if kind == "chart":
            chart_spec = _extract_chart_spec(sb)
            if chart_spec is None:
                # Fallback: malformed CHART_SPEC, treat as image so it at least renders.
                kind = "image"

        if kind == "chart":
            filename = _slide_filename(sb, fallback_ext="svg")
            stem = Path(filename).with_suffix("").name
            chart_path = deck_dir / "prompts" / f"{stem}.chart.json"
            import json as _json

            write_text_if_changed(
                chart_path,
                _json.dumps(chart_spec, ensure_ascii=False, indent=2),
            )
            continue

        filename = _slide_filename(sb, fallback_ext="png")
        stem = Path(filename).with_suffix("").name
        prompt_md_path = deck_dir / "prompts" / f"{stem}.md"
        prompt_body = (
            base_prompt.strip()
            + "\n\n---\n\n## STYLE_INSTRUCTIONS\n\n"
            + style_block
            + "\n\n---\n\n## SLIDE CONTENT\n\n"
            + sb.strip()
            + "\n"
        )
        write_text_if_changed(prompt_md_path, prompt_body)

        spec = _extract_design_spec(sb)
        if spec is not None:
            import json as _json

            spec_path = deck_dir / "prompts" / f"{stem}.spec.json"
            write_text_if_changed(
                spec_path,
                _json.dumps(spec, ensure_ascii=False, indent=2),
            )


def _render_concept_prompt(*, concept_payload: dict[str, Any], style_anchor: str) -> str:
    """Backwards-compatible wrapper around `concept.render_concept_prompt`."""
    return render_concept_prompt(concept_payload=concept_payload, style_anchor=style_anchor)


def _read_anchor_for_preset(deck_dir: Path) -> str:
    """Read whichever cached style-anchor sits in the deck's anchor cache.

    We don't track which anchor key applies — there's only one preset per
    deck — so we just take the most recent value. Returns "" if no cache.
    """
    cache_path = deck_dir / ".style-anchor-cache.json"
    if not cache_path.is_file():
        return ""
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(cache, dict) and cache:
            # Cache values are anchor sentences; just return any one.
            return next(iter(cache.values()), "")
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def rewrite_image_prompts_with_concepts(*, deck_dir: Path, outline_md: str) -> int:
    """For each image slide that has a `.concept.json`, rewrite the matching
    `prompts/NN-slide-{slug}.md` to the templated concept-driven prompt.

    Slides without a concept.json keep their existing prompt body
    (backwards-compat with `write_prompt_files`).

    Returns the number of prompt files rewritten this call.
    """
    prompts_dir = deck_dir / "prompts"
    if not prompts_dir.is_dir():
        return 0

    style_anchor = _read_anchor_for_preset(deck_dir)
    if not style_anchor:
        # Without an anchor, the templated form would lose its style lock.
        # Leave the existing prompts alone — the old <STYLE_INSTRUCTIONS>
        # path still works.
        return 0

    rewritten = 0
    for prompt_path in list_active_slide_files(prompts_dir, ".md"):
        stem = prompt_path.stem
        concept_path = prompts_dir / f"{stem}.concept.json"
        concept_payload = read_concept_file(concept_path)
        if concept_payload is None:
            continue
        new_body = _render_concept_prompt(
            concept_payload=concept_payload, style_anchor=style_anchor,
        )
        if write_text_if_changed(prompt_path, new_body):
            rewritten += 1
    return rewritten


def sanitize_outline_md(text: str) -> str:
    """
    Models sometimes add chatter or wrap the outline in code fences.
    Extract the actual outline markdown body.
    """
    t = text.strip()
    # Prefer fenced markdown block
    m = re.search(r"```markdown\s*([\s\S]*?)```", t, flags=re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    # Fallback: start from first outline heading if present
    idx = t.find("# Slide Deck Outline")
    if idx != -1:
        t = t[idx:].strip()
    return t


def strip_markdown_fences(text: str) -> str:
    """Remove a single outer ```markdown ... ``` fence if present (do not strip other content)."""
    t = text.strip()
    m = re.search(r"```markdown\s*([\s\S]*?)```", t, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def validate_outline(outline_md: str, expected_slides: int) -> tuple[bool, str]:
    slides = parse_slides(outline_md)
    if not outline_md.strip().startswith("# Slide Deck Outline"):
        return False, "Outline does not start with '# Slide Deck Outline'."
    if "<STYLE_INSTRUCTIONS>" not in outline_md or "</STYLE_INSTRUCTIONS>" not in outline_md:
        return False, "Missing <STYLE_INSTRUCTIONS> block."
    if len(slides) != expected_slides:
        return False, f"Expected {expected_slides} slide blocks, found {len(slides)}."

    # Basic per-slide checks
    for i, block in enumerate(slides, start=1):
        first_line = block.strip().splitlines()[0].strip() if block.strip() else ""
        if first_line != f"## Slide {i} of {expected_slides}":
            return False, f"Slide heading mismatch at position {i}: expected '## Slide {i} of {expected_slides}', got '{first_line}'."
        if "**Type**:" not in block:
            return False, f"Slide {i} missing **Type**: line."
        if "**Filename**:" not in block:
            return False, f"Slide {i} missing **Filename**: line."
        fm = re.search(r"^\*\*Filename\*\*:\s*(.+)$", block, re.MULTILINE)
        if not fm:
            return False, f"Slide {i} has malformed **Filename** line."
        fn = fm.group(1).strip().strip("`").strip()
        if not re.match(r"^\d{2}-slide-.+\.(png|jpg|jpeg|svg)$", fn, flags=re.IGNORECASE):
            return False, f"Slide {i} filename must look like `NN-slide-slug.png` (or `.svg` for chart slides) — got `{fn}`."

    return True, "ok"


def append_missing_slides(
    *,
    planning_base_url: str,
    planning_api_key: str,
    planning_model: str,
    planning_max_tokens: int,
    outline_so_far: str,
    expected_slides: int,
    max_rounds: int = 8,
) -> str:
    """
    If the model truncates, iteratively ask it to append the remaining slides only.
    """
    md = outline_so_far
    for _ in range(max_rounds):
        slides = parse_slides(md)
        have = len(slides)
        if have >= expected_slides:
            return md

        start_idx = have + 1
        cont = f"""You are continuing an existing `outline.md` for skilldeck.

CRITICAL:
- Output ONLY the remaining slide blocks.
- Do NOT repeat the header, metadata, or <STYLE_INSTRUCTIONS>.
- Start at slide {start_idx} and continue through slide {expected_slides} inclusive.
- Each slide MUST begin with EXACTLY this heading format:
  ## Slide k of {expected_slides}
  where k is the slide number.
- Each slide MUST include **Type**: and **Filename**: lines.
- Filenames MUST match pattern: NN-slide-slug.png with zero-padded NN (01, 02, ...).
- {(
            "Single-slide deck: one slide only (self-contained; no separate back cover required)."
            if expected_slides == 1
            else f"Slide 1 should be Cover, slide {expected_slides} should be Back Cover."
        )}

Existing outline (for context — do not repeat):
{md}
"""
        chunk_raw = chat_completion_openai_compatible(
            base_url=planning_base_url,
            api_key=planning_api_key,
            model=planning_model,
            messages=[{"role": "user", "content": cont}],
            max_tokens=int(planning_max_tokens),
        )
        chunk = strip_markdown_fences(str(chunk_raw))
        md = (md.rstrip() + "\n\n---\n\n" + chunk.strip()).strip()
    return md


def generate_outline_with_retry(
    *,
    planning_base_url: str,
    planning_api_key: str,
    planning_model: str,
    planning_max_tokens: int,
    prompt: str,
    expected_slides: int,
    max_attempts: int = 3,
) -> str:
    last_md = ""
    last_reason = ""
    for attempt in range(1, max_attempts + 1):
        extra = ""
        if attempt > 1:
            extra = (
                "\n\nSTRICT REQUIREMENTS:\n"
                "- Output ONLY the outline markdown. No commentary, no bash, no fences.\n"
                f"- Include EXACTLY {expected_slides} slide blocks. Each must start with: ## Slide X of {expected_slides}\n"
                "- Put a line containing only --- between slides (recommended).\n"
                "- Ensure every slide block includes **Type** and **Filename** lines.\n"
                "- **Filename** must be like `NN-slide-slug.png` (two-digit NN).\n"
            )
        md_raw = chat_completion_openai_compatible(
            base_url=planning_base_url,
            api_key=planning_api_key,
            model=planning_model,
            messages=[{"role": "user", "content": prompt + extra}],
            max_tokens=int(planning_max_tokens),
        )
        md = sanitize_outline_md(str(md_raw))
        md = append_missing_slides(
            planning_base_url=planning_base_url,
            planning_api_key=planning_api_key,
            planning_model=planning_model,
            planning_max_tokens=planning_max_tokens,
            outline_so_far=md,
            expected_slides=expected_slides,
        )
        ok, reason = validate_outline(md, expected_slides)
        last_md = md
        last_reason = reason
        if ok:
            return md
    raise RuntimeError(
        f"Failed to generate a valid outline after {max_attempts} attempts. Last reason: {last_reason}"
    )


def render_chart_slides(*, deck_dir: Path, progress: ProgressBus | None = None) -> int:
    """Render every prompts/*.chart.json into a sibling SVG in deck_dir.

    Returns the number of charts rendered. Safe to call when no chart specs exist.
    """
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    try:
        from render_chart_slide import render_chart_svg  # type: ignore
    finally:
        # leave skill/scripts on the path (other helpers may rely on it later)
        pass

    chart_files = list_active_slide_files(deck_dir / "prompts", ".chart.json")
    total = len(chart_files)
    if progress is not None:
        if total:
            progress.start_stage(Stage.CHARTS, items_total=total,
                                 detail=f"Rendering {total} chart slide{'s' if total != 1 else ''}")
        else:
            progress.skip_stage(Stage.CHARTS, "no chart specs")
    rendered = 0
    for cf in chart_files:
        try:
            spec = json.loads(cf.read_text(encoding="utf-8"))
        except Exception as e:
            if progress is not None:
                progress.fail_stage(Stage.CHARTS, f"Bad chart spec in {cf.name}: {e}")
            raise RuntimeError(f"Bad chart spec in {cf.name}: {e}") from e
        stem = cf.name[: -len(".chart.json")]
        out_path = deck_dir / f"{stem}.svg"
        svg = render_chart_svg(spec)
        wrote = write_text_if_changed(out_path, svg)
        msg = (
            f"{'Rendered' if wrote else 'Reused'} chart {rendered + 1}/{total}: "
            f"`{out_path.name}` (template: {spec.get('template')})"
        )
        st.write(msg)
        if progress is not None:
            progress.update_stage(Stage.CHARTS, items_done=rendered + 1,
                                  detail=f"Rendered {rendered + 1}/{total}: {out_path.name}")
            progress.emit_event(msg, stage=Stage.CHARTS)
        rendered += 1
    if progress is not None and total:
        progress.end_stage(Stage.CHARTS, detail=f"{rendered} chart slide{'s' if rendered != 1 else ''} ready")
    return rendered


def generate_concepts(
    *,
    deck_dir: Path,
    outline_md: str,
    style_spec: str,
    style_preset_name: str,
    planning_base_url: str,
    planning_api_key: str,
    planning_model: str,
    planning_max_tokens: int,
    progress: ProgressBus | None = None,
) -> int:
    """Stage 4: write `prompts/NN-slide-{slug}.concept.json` for each image slide.

    Sequential per slide. Skips chart slides (they bypass image gen entirely).
    Skips slides whose concept.json is fresh (outline_hash matches) or has
    been edited by the user (concept hash drifted from `original_hash`).

    Returns the number of concepts generated this run.
    """
    slides_blocks = parse_slides(outline_md)
    image_blocks = [sb for sb in slides_blocks if _slide_render_kind(sb) == "image"]

    if not image_blocks:
        if progress is not None:
            progress.skip_stage(Stage.CONCEPTS, "no image slides")
        return 0

    if progress is not None:
        progress.start_stage(
            Stage.CONCEPTS,
            items_total=len(image_blocks),
            detail="Generating visual concepts",
        )

    def _chat_call(*, messages: list[dict[str, Any]], model: str, max_tokens: int) -> str:
        return chat_completion_openai_compatible(
            base_url=planning_base_url,
            api_key=planning_api_key,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )

    # Stage 4 anchor — once per run, cached by (style_spec, planning_model).
    style_anchor = generate_style_anchor(
        style_spec=style_spec,
        deck_dir=deck_dir,
        planning_model=planning_model,
        chat_call=_chat_call,
    )
    if progress is not None:
        progress.emit_event(
            f"Style anchor: {style_anchor[:140]}{'…' if len(style_anchor) > 140 else ''}",
            stage=Stage.CONCEPTS,
        )

    examples_text = read_ref_text("concept-examples.md")
    prompts_dir = deck_dir / "prompts"
    ensure_dir(prompts_dir)

    generated = 0
    for idx, sb in enumerate(image_blocks, start=1):
        filename = _slide_filename(sb, fallback_ext="png")
        stem = Path(filename).with_suffix("").name
        concept_path = prompts_dir / f"{stem}.concept.json"

        outline_hash = hash_outline_block(sb)
        if not is_concept_stale(concept_path, outline_hash):
            existing = read_concept_file(concept_path)
            tag = "user-edited" if (
                existing
                and existing.get("original_hash")
                and outline_hash != existing.get("outline_hash")
            ) else "fresh"
            msg = f"Reused {idx}/{len(image_blocks)}: {concept_path.name} ({tag})"
            st.write(msg)
            if progress is not None:
                progress.update_stage(
                    Stage.CONCEPTS, items_done=idx,
                    detail=f"Reused {idx}/{len(image_blocks)} (cache hit)",
                )
                progress.emit_event(msg, stage=Stage.CONCEPTS)
            continue

        role = _slide_role(sb)
        architype = _slide_architype(sb)
        architype_desc = _architype_description(architype)
        headline = _slide_field(sb, "Headline")
        subhead = _slide_field(sb, "Sub-headline") or _slide_field(sb, "Subhead")
        body_bullets = _slide_body_bullets(sb)
        slide_number_match = re.search(r"^##\s*Slide\s+(\d+)\s+of\s+\d+", sb, re.MULTILINE)
        slide_number = int(slide_number_match.group(1)) if slide_number_match else idx

        try:
            result = generate_visual_concept(
                slide_block=sb,
                role=role,
                architype=architype,
                architype_description=architype_desc,
                style_preset=style_preset_name,
                style_anchor=style_anchor,
                examples_text=examples_text,
                chat_call=_chat_call,
                planning_model=planning_model,
            )
        except ConceptError as e:
            err = f"Concept generation failed for `{stem}`: {e}"
            if progress is not None:
                progress.fail_stage(Stage.CONCEPTS, err)
            raise RuntimeError(err) from e
        except Exception as e:
            err = f"Concept generation network/API error for `{stem}`: {e}"
            if progress is not None:
                progress.fail_stage(Stage.CONCEPTS, err)
            raise RuntimeError(err) from e

        write_concept_file(
            concept_path,
            slide_id=stem,
            slide_number=slide_number,
            role=role,
            architype=architype,
            style_preset=style_preset_name,
            headline=headline,
            subhead=subhead,
            body=body_bullets,
            concept=result.concept,
            outline_hash=outline_hash,
        )
        generated += 1
        msg = f"Generated {idx}/{len(image_blocks)}: {concept_path.name} (subject: {result.concept['subject'][:60]}…)"
        st.write(msg)
        if progress is not None:
            progress.update_stage(
                Stage.CONCEPTS, items_done=idx,
                detail=f"Generated {idx}/{len(image_blocks)}: {concept_path.name}",
            )
            progress.emit_event(msg, stage=Stage.CONCEPTS)

    if progress is not None:
        progress.end_stage(
            Stage.CONCEPTS,
            detail=f"{generated} new, {len(image_blocks) - generated} cached",
        )
    return generated


def generate_images_from_prompts(
    *,
    deck_dir: Path,
    image_base_url: str,
    image_api_key: str,
    image_model: str,
    image_size: str,
    progress: ProgressBus | None = None,
) -> None:
    prompts_dir = deck_dir / "prompts"
    prompt_files = list_active_slide_files(prompts_dir, ".md")
    if not prompt_files:
        if progress is not None:
            progress.skip_stage(Stage.IMAGES, "no image prompts")
        raise RuntimeError("No prompt files found.")

    total = len(prompt_files)
    if progress is not None:
        progress.start_stage(Stage.IMAGES, items_total=total,
                             detail=f"Generating {total} image slide{'s' if total != 1 else ''}")
    for idx, pf in enumerate(prompt_files, start=1):
        prompt_text = pf.read_text(encoding="utf-8")
        png_name = Path(pf.name).with_suffix(".png").name
        out_path = deck_dir / png_name

        # Skip-if-unchanged: hash prompt + (model, size) — if PNG exists and the
        # sidecar matches, reuse the cached PNG instead of re-calling the API.
        cache_key = hashlib.sha256(
            f"{image_model}|{image_size}|{prompt_text}".encode("utf-8")
        ).hexdigest()
        cache_file = deck_dir / f".{Path(pf.name).stem}.imghash"
        if (
            out_path.exists()
            and cache_file.exists()
            and cache_file.read_text(encoding="utf-8").strip() == cache_key
        ):
            msg = f"Reused {idx}/{total}: `{png_name}` (prompt unchanged)"
            st.write(msg)
            if progress is not None:
                progress.update_stage(Stage.IMAGES, items_done=idx,
                                      detail=f"Reused {idx}/{total} (cache hit)")
                progress.emit_event(msg, stage=Stage.IMAGES)
            continue

        try:
            png_bytes = generate_image_openai_compatible(
                base_url=image_base_url,
                api_key=image_api_key,
                model=image_model,
                prompt=prompt_text,
                size=image_size,
            )
            png_bytes = normalize_generated_image_png(png_bytes, image_size)
            backup_if_exists(out_path)
            out_path.write_bytes(png_bytes)
            cache_file.write_text(cache_key, encoding="utf-8")
            msg = f"Generated {idx}/{total}: `{png_name}`"
            st.write(msg)
            if progress is not None:
                progress.update_stage(Stage.IMAGES, items_done=idx,
                                      detail=f"Generated {idx}/{total}: {png_name}")
                progress.emit_event(msg, stage=Stage.IMAGES)
        except Exception as e:
            err = f"Image generation failed for `{pf.name}` → `{png_name}`: {e}"
            if progress is not None:
                progress.fail_stage(Stage.IMAGES, err)
            raise RuntimeError(err) from e

    if progress is not None:
        progress.end_stage(Stage.IMAGES, detail=f"{total} image slide{'s' if total != 1 else ''} ready")


def merge_deck(
    *,
    deck_dir: Path,
    export_pdf: bool | None = None,
    progress: ProgressBus | None = None,
) -> tuple[str, str]:
    """Build editable PPTX via `python -m deck_assembler` (image + chart slides), then optional PDF via bun script.

    PDF export gating:
      * `export_pdf=True` always runs PDF (when bun available).
      * `export_pdf=False` skips PDF entirely.
      * `export_pdf=None` (default) reads `SKILLDECK_EXPORT_PDF` env (default 1
        for backwards compatibility).
    PDF is also skipped when the PPTX hash matches the previous run's cached
    hash and the PDF already exists.
    """
    bun_x = resolve_bun_x()
    logs: list[str] = []
    err = ""

    export_pdf = resolve_pdf_export_flag(export_pdf)

    has_image_slides = bool(list_active_slide_files(deck_dir, ".png")) or bool(
        list_active_slide_files(deck_dir, ".jpg")
    ) or bool(list_active_slide_files(deck_dir, ".jpeg"))
    has_chart_slides = bool(list_active_slide_files(deck_dir, ".svg"))

    layout_engine = (os.getenv("EDITABLE_PPTX_LAYOUT_ENGINE", "mineru") or "").strip().lower()
    hybrid_cv_active = layout_engine in {"hybrid", "hybrid_cv", "cv"}
    mineru_required = has_image_slides and not hybrid_cv_active

    if mineru_required and not os.getenv("MINERU_TOKEN", "").strip():
        msg = (
            "deck_assembler: skipped — image slides require MINERU_TOKEN (not set in `.env`). "
            "Add it next to PLANNING_* / IMAGE_*; see `.env.example`. "
            "Or set EDITABLE_PPTX_LAYOUT_ENGINE=hybrid_cv to use the local CV layout engine."
        )
        logs.append(msg)
        err = (
            "Editable PPTX was skipped: set **MINERU_TOKEN** in `.env` "
            "or set `EDITABLE_PPTX_LAYOUT_ENGINE=hybrid_cv`. "
            "PDF export still runs below if `bun` is available."
        )
        if progress is not None:
            progress.skip_stage(Stage.PPTX, "MINERU_TOKEN missing (and hybrid_cv not enabled)")
    elif not (has_image_slides or has_chart_slides):
        logs.append("deck_assembler: skipped — no slides found.")
        err = "No slide artifacts to export."
        if progress is not None:
            progress.skip_stage(Stage.PPTX, "no slide artifacts")
    else:
        if progress is not None:
            kinds = []
            if has_image_slides:
                kinds.append("image")
            if has_chart_slides:
                kinds.append("chart")
            progress.start_stage(
                Stage.PPTX,
                detail=f"Assembling editable PPTX ({' + '.join(kinds)} slides)",
            )
        py = sys.executable
        r = subprocess.run(
            [py, "-m", "deck_assembler", str(deck_dir)],
            cwd=str(REPO_DIR),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        logs.append("deck_assembler:\n" + (r.stdout or "") + (r.stderr or ""))
        if r.returncode != 0:
            err = f"deck_assembler failed (exit {r.returncode}). Check log below; PDF may still have been built."
            if progress is not None:
                progress.fail_stage(Stage.PPTX, err)
        elif progress is not None:
            slug = deck_dir.name
            progress.end_stage(Stage.PPTX, detail=f"{slug}.pptx written")

    if not export_pdf:
        logs.append("merge-to-pdf: skipped (SKILLDECK_EXPORT_PDF disabled)")
        if progress is not None:
            progress.skip_stage(Stage.PDF, "PDF export disabled")
        return "\n\n".join(logs), err

    if not bun_x:
        logs.append("merge-to-pdf: skipped (missing `bun` and `npx`)")
        if progress is not None:
            progress.skip_stage(Stage.PDF, "missing bun/npx")
        return "\n\n".join(logs), err

    merge_pdf = SKILL_DIR / "scripts" / "merge-to-pdf.ts"
    if merge_pdf.exists():
        slug = deck_dir.name
        if pdf_cache_is_fresh(deck_dir, slug):
            logs.append("merge-to-pdf: skipped (PPTX unchanged, cached PDF reused)")
            if progress is not None:
                progress.skip_stage(Stage.PDF, "cached PDF reused (PPTX unchanged)")
            return "\n\n".join(logs), err

        if progress is not None:
            progress.start_stage(Stage.PDF, detail=f"Converting {slug}.pptx to PDF")
        p2 = subprocess.run(bun_x + [str(merge_pdf), str(deck_dir)], capture_output=True, text=True)
        logs.append("merge-to-pdf:\n" + (p2.stdout or "") + (p2.stderr or ""))
        if p2.returncode == 0 and (deck_dir / f"{slug}.pdf").is_file():
            write_pdf_cache(deck_dir, slug)
            if progress is not None:
                progress.end_stage(Stage.PDF, detail=f"{slug}.pdf written")
        elif progress is not None:
            progress.fail_stage(Stage.PDF, f"merge-to-pdf exited {p2.returncode}")

    return "\n\n".join(logs), err


def stable_hash(obj: dict[str, Any]) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t and t.strip():
            parts.append(t.strip())
    return "\n\n".join(parts).strip()


def list_deck_history() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not DECKS_DIR.exists():
        return items
    for d in DECKS_DIR.iterdir():
        if not d.is_dir():
            continue
        slug = d.name
        stat = d.stat()
        pdf = d / f"{slug}.pdf"
        pptx = d / f"{slug}.pptx"
        pngs = list_active_slide_files(d, ".png")
        items.append(
            {
                "slug": slug,
                "mtime": stat.st_mtime,
                "has_pdf": pdf.exists(),
                "has_pptx": pptx.exists(),
                "png_count": len(pngs),
            }
        )
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def format_deck_history_row(histories: list[dict[str, Any]], slug: str) -> str:
    h = next((x for x in histories if x["slug"] == slug), None)
    if not h:
        return slug
    ts = datetime.fromtimestamp(h["mtime"]).strftime("%Y-%m-%d %H:%M")
    bits: list[str] = []
    if h["has_pdf"]:
        bits.append("PDF")
    if h["has_pptx"]:
        bits.append("editable PPTX")
    if h["png_count"]:
        bits.append(f"{h['png_count']} PNG")
    suffix = ", ".join(bits) if bits else "no exports yet"
    short = slug if len(slug) <= 44 else slug[:41] + "…"
    return f"{short} · {ts} · {suffix}"


def run_pipeline(
    *,
    source_text: str,
    topic_hint: str,
    analysis: dict[str, Any],
    confirmed_params: dict[str, Any],
    ref_files_meta: list[dict[str, str]],
    planning_base_url: str,
    planning_api_key: str,
    planning_model: str,
    planning_max_tokens: int,
    image_base_url: str,
    image_api_key: str,
    image_model: str,
    image_size: str,
    preset_names: list[str],
    export_pdf: bool = True,
    progress: ProgressBus | None = None,
) -> None:
    topic_slug = analysis["topic_slug"]
    deck_dir = get_session_deck_dir(topic_slug)
    ensure_dir(deck_dir)

    if progress is not None:
        progress.start_pipeline()
        progress.start_stage(
            Stage.SOURCE,
            detail=f"Saving source, analysis, confirmation for `{topic_slug}`",
        )

    # Persist refs + confirmation every pipeline run (mirrors skill bookkeeping)
    ensure_dir(deck_dir / "refs")
    write_text_if_changed(
        deck_dir / "confirmation.yaml",
        yaml.safe_dump({"params": confirmed_params, "refs": ref_files_meta}, sort_keys=False, allow_unicode=True),
    )

    if progress is not None:
        progress.end_stage(Stage.SOURCE, detail="confirmation.yaml saved")

    # Step 3: outline
    if progress is not None:
        progress.start_stage(
            Stage.OUTLINE,
            detail=f"Generating {confirmed_params['slides']}-slide outline via {planning_model}",
        )
    outline_template = read_ref_text("outline-template.md")
    presets_map = read_ref_text("dimensions/presets.md")
    style_spec = (
        load_style_preset_text(SKILL_DIR, confirmed_params["style"])
        if confirmed_params["style"] in preset_names
        else ""
    )
    n_slides = int(confirmed_params["slides"])
    slide_count_line = (
        "- Exactly 1 slide: one self-contained slide (cover + core message combined; no separate back cover)."
        if n_slides == 1
        else f"- Exactly {n_slides} slides (Slide 1=Cover, last=Back Cover)"
    )
    prompt = f"""Generate `outline.md` for the `skilldeck` skill.
Follow the Outline Template exactly. Include:
- Header metadata
- <STYLE_INSTRUCTIONS> block (single source of truth)
{slide_count_line}
- Audience={confirmed_params['audience']}
- Language={confirmed_params['language']} (auto => detected={analysis['detected_language']})

When the source contains numeric data — KPIs, time series, comparisons,
tables, before/after, percentages — emit a chart slide using the
`<CHART_SPEC>` block (see Outline Template). Chart slides bypass image
generation entirely and export as native editable shapes. Use chart slides
liberally for any quantitative content. Use image slides for narrative,
metaphors, hero shots, and anything not numeric. Cover and back-cover are
always image slides.

If preset is chosen, use the preset spec as authoritative. If custom dimensions, use:
{confirmed_params.get('dimensions')}

If the preset spec contains an "SVG Layout Guidance" section, use those SVG
page roles as composition references only. Do not require native SVG template
editing or rendering; image slides and chart slides must continue using the
current skilldeck pipeline.

Outline Template:
{outline_template}

Preset mapping reference:
{presets_map}

Preset spec (if any):
{style_spec}

Source content:
{source_text}
"""
    md = generate_outline_with_retry(
        planning_base_url=planning_base_url,
        planning_api_key=planning_api_key,
        planning_model=planning_model,
        planning_max_tokens=planning_max_tokens,
        prompt=prompt,
        expected_slides=int(confirmed_params["slides"]),
        max_attempts=3,
    )
    write_text_if_changed(deck_dir / "outline.md", str(md))
    if progress is not None:
        progress.end_stage(Stage.OUTLINE, detail="outline.md validated")

    # Step 5: prompts (image .md and/or chart .chart.json)
    if progress is not None:
        progress.start_stage(Stage.PROMPTS, detail="Splitting outline into per-slide prompts")
    outline_md = (deck_dir / "outline.md").read_text(encoding="utf-8")
    write_prompt_files(deck_dir=deck_dir, outline_md=outline_md)
    if progress is not None:
        n_image_prompts = len(list_active_slide_files(deck_dir / "prompts", ".md"))
        n_chart_specs = len(list_active_slide_files(deck_dir / "prompts", ".chart.json"))
        progress.end_stage(
            Stage.PROMPTS,
            detail=f"{n_image_prompts} image prompts, {n_chart_specs} chart specs",
        )

    # Step 5.5: visual concepts (Stage 4 — creative-director per-slide).
    # Sequential per slide. Skips chart slides. Cached on disk by outline_hash.
    style_for_concepts = style_spec or parse_style_instructions(outline_md)
    style_preset_name = confirmed_params.get("style") or "blueprint"
    generate_concepts(
        deck_dir=deck_dir,
        outline_md=outline_md,
        style_spec=style_for_concepts,
        style_preset_name=str(style_preset_name),
        planning_base_url=planning_base_url,
        planning_api_key=planning_api_key,
        planning_model=planning_model,
        planning_max_tokens=planning_max_tokens,
        progress=progress,
    )

    # After concepts exist, rewrite each image prompt to template the concept
    # block + style anchor (replaces the old <STYLE_INSTRUCTIONS> + // VISUAL
    # prose dump). For slides without a concept.json (e.g. chart slides or
    # if Stage 4 was skipped), the original prompt body stays.
    rewrite_image_prompts_with_concepts(deck_dir=deck_dir, outline_md=outline_md)

    # Step 6: render chart slides (CHART_SPEC → SVG); skipped if no chart specs.
    n_charts = render_chart_slides(deck_dir=deck_dir, progress=progress)

    # Step 7: images for prompt .md files. Chart slides have no .md, so they're skipped.
    has_image_prompts = bool(list_active_slide_files(deck_dir / "prompts", ".md"))
    if has_image_prompts:
        generate_images_from_prompts(
            deck_dir=deck_dir,
            image_base_url=image_base_url,
            image_api_key=image_api_key,
            image_model=image_model,
            image_size=image_size,
            progress=progress,
        )
    elif progress is not None:
        progress.skip_stage(Stage.IMAGES, "no image prompts")

    # Step 8: assemble final deck (image-side via editable_pptx, chart-side via svg_to_pptx, merged)
    merge_log, merge_err = merge_deck(deck_dir=deck_dir, export_pdf=export_pdf, progress=progress)
    if merge_err:
        st.warning(merge_err)
        if progress is not None:
            progress.mark_error(merge_err)
    elif (deck_dir / f"{deck_dir.name}.pptx").is_file():
        kind_summary = []
        if has_image_prompts:
            kind_summary.append("image")
        if n_charts:
            kind_summary.append(f"{n_charts} chart")
        kind_str = " + ".join(kind_summary) or "image"
        st.success(f"Exported **editable** `.pptx` ({kind_str} slides; open in PowerPoint to edit).")
        if progress is not None:
            progress.mark_done()
    elif progress is not None:
        progress.mark_done()
    if merge_log.strip():
        st.expander("Editable PPTX + PDF export log").code(merge_log, language="text")


# --- Streamlit UI (cockpit layout) ---

IMAGE_MODEL_CHOICES = ["gpt-image-2-cheap", "gpt-image-2", "nano-banana-pro"]


def _resolve_default_image_model(env_value: str) -> str:
    v = (env_value or "").strip()
    if v in IMAGE_MODEL_CHOICES:
        return v
    # If env points to a non-listed model, prepend it so the user keeps their override.
    return v if v else IMAGE_MODEL_CHOICES[1]


def _inject_theme_css() -> None:
    st.markdown(
        """
<style id="skilldeck-theme">
:root {
  --bg:      oklch(99% 0.002 240);
  --surface: oklch(100% 0 0);
  --fg:      oklch(18% 0.012 250);
  --muted:   oklch(54% 0.012 250);
  --border:  oklch(92% 0.005 250);
  --accent:  oklch(58% 0.18 255);
  --radius: 8px;
}
html, body, .main, .block-container { background: var(--bg); color: var(--fg); }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
section[data-testid="stSidebar"] {
  background: oklch(100% 0 0 / 0.92);
  border-right: 1px solid var(--border);
  backdrop-filter: blur(18px);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

/* topbar */
.sd-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 18px; margin-bottom: 14px;
  background: oklch(99% 0.002 240 / 0.88);
  border: 1px solid var(--border); border-radius: var(--radius);
}
.sd-topbar h2 { margin: 0; font-size: 22px; letter-spacing: 0; }
.sd-topbar p { margin: 3px 0 0; color: var(--muted); font-size: 13px; }
.sd-topbar .actions { display: flex; gap: 8px; }
.sd-topbar .actions span {
  border: 1px solid var(--border); border-radius: 7px; padding: 6px 11px;
  font-size: 12px; color: var(--muted); background: var(--surface);
}

/* status rail */
.sd-rail { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
.sd-step {
  display: grid; grid-template-columns: 26px 1fr; align-items: center; gap: 9px;
  border: 1px solid var(--border); background: var(--surface);
  border-radius: var(--radius); padding: 10px;
}
.sd-step .num {
  width: 26px; height: 26px; border-radius: 999px; display: grid; place-items: center;
  color: var(--muted); border: 1px solid var(--border);
  font: 700 12px/1 ui-monospace, "JetBrains Mono", Menlo, monospace;
}
.sd-step strong { display: block; line-height: 1.1; font-size: 13px; }
.sd-step span.sub { color: var(--muted); font-size: 12px; }
.sd-step.active { border-color: oklch(78% 0.04 255); box-shadow: inset 0 -3px 0 var(--accent); }
.sd-step.active .num { color: white; border-color: var(--accent); background: var(--accent); }
.sd-step.done .num { color: white; border-color: oklch(61% 0.14 145); background: oklch(61% 0.14 145); }

/* panels (wraps a Streamlit container) */
.sd-panel-head {
  border: 1px solid var(--border);
  border-bottom: none;
  border-radius: var(--radius) var(--radius) 0 0;
  padding: 14px 16px;
  background: var(--surface);
  display: flex; align-items: flex-start; justify-content: space-between; gap: 14px;
}
.sd-panel-head .label {
  color: var(--muted);
  font: 700 11px/1 ui-monospace, "JetBrains Mono", Menlo, monospace;
  letter-spacing: 0.06em; text-transform: uppercase;
}
.sd-panel-head h3 { margin: 4px 0 0; font-size: 15px; }
.sd-panel-head p  { margin: 3px 0 0; color: var(--muted); font-size: 12px; max-width: 64ch; }
.sd-panel-body {
  border: 1px solid var(--border);
  border-radius: 0 0 var(--radius) var(--radius);
  background: var(--surface);
  padding: 14px 16px;
}

/* badges */
.sd-badge {
  display: inline-flex; align-items: center; gap: 5px; height: 22px;
  border: 1px solid var(--border); border-radius: 999px; padding: 0 8px;
  color: var(--muted); background: oklch(99% 0.002 240);
  font: 600 11px/1 ui-monospace, "JetBrains Mono", Menlo, monospace; white-space: nowrap;
}
.sd-badge.good { color: oklch(43% 0.12 145); border-color: oklch(85% 0.05 145); }
.sd-badge.warn { color: oklch(55% 0.14 70);  border-color: oklch(84% 0.08 70); }
.sd-badge.bad  { color: oklch(51% 0.19 28);  border-color: oklch(86% 0.045 28); }

/* metric cards */
.sd-metric-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.sd-metric {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px; background: oklch(99% 0.002 240);
}
.sd-metric small { display: block; color: var(--muted); font-weight: 650; font-size: 12px; }
.sd-metric strong {
  display: block; margin-top: 6px;
  font: 760 22px/1 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
}

/* recommendation */
.sd-reco {
  margin-top: 12px; border: 1px solid oklch(85% 0.04 255); border-radius: var(--radius);
  padding: 13px; background: oklch(97% 0.018 255);
}
.sd-reco strong { display: block; }
.sd-reco p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }

/* style cards */
.sd-style-card {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); padding: 12px; min-height: 110px;
  display: flex; flex-direction: column; justify-content: space-between; gap: 10px;
}
.sd-style-card.active { border-color: oklch(76% 0.05 255); box-shadow: inset 0 0 0 1px oklch(76% 0.05 255); }
.sd-swatches { display: flex; gap: 4px; }
.sd-swatch { height: 18px; flex: 1; border-radius: 4px; border: 1px solid oklch(18% 0.012 250 / 0.1); }
.sd-style-card h4 { margin: 0; font-size: 13px; }
.sd-style-card p  { margin: 4px 0 0; color: var(--muted); font-size: 12px; }

/* timeline */
.sd-timeline {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); overflow: hidden; margin-top: 4px;
}
.sd-trow {
  display: grid; grid-template-columns: 30px 1fr auto;
  gap: 12px; align-items: center; padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}
.sd-trow:last-child { border-bottom: 0; }
.sd-dot {
  width: 18px; height: 18px; border-radius: 999px;
  border: 1px solid var(--border); background: var(--surface);
}
.sd-dot.done { background: oklch(61% 0.14 145); border-color: oklch(61% 0.14 145); }
.sd-dot.active { border-color: var(--accent); box-shadow: 0 0 0 5px oklch(58% 0.18 255 / 0.14); }
.sd-dot.warn { background: oklch(70% 0.15 70); border-color: oklch(70% 0.15 70); }
.sd-dot.bad  { background: oklch(64% 0.18 28); border-color: oklch(64% 0.18 28); }
.sd-trow strong { display: block; font-size: 13px; }
.sd-trow span.sub { color: var(--muted); font-size: 12px; }
.sd-runtime {
  font: 12px/1 ui-monospace, "JetBrains Mono", Menlo, monospace;
  color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap;
}

/* recovery callout */
.sd-recovery {
  margin-top: 14px; border: 1px solid oklch(84% 0.08 70); border-radius: var(--radius);
  background: oklch(98% 0.025 80); padding: 14px;
}
.sd-recovery h4 {
  margin: 0; display: flex; align-items: center; justify-content: space-between; gap: 10px;
  font-size: 14px;
}
.sd-recovery p { color: var(--muted); margin: 8px 0 0; font-size: 12px; }

/* deck library cards inside sidebar */
.sd-deck {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); padding: 10px; margin-bottom: 8px;
}
.sd-deck.active { border-color: oklch(76% 0.05 255); box-shadow: inset 3px 0 0 var(--accent); }
.sd-deck .row {
  display: flex; justify-content: space-between; gap: 8px; font-weight: 650; font-size: 13px;
}
.sd-deck .meta { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }

/* download cards */
.sd-dl-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 12px; }
.sd-dl-card {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 13px; background: oklch(99% 0.002 240);
}
.sd-dl-card strong { display: block; }
.sd-dl-card p { margin: 5px 0 10px; color: var(--muted); font-size: 12px; }

/* slide gallery thumbs */
.sd-thumb {
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); overflow: hidden;
}
.sd-thumb .cap {
  padding: 8px 10px; display: flex; justify-content: space-between;
  gap: 6px; font-size: 12px; border-top: 1px solid var(--border);
}

/* misc */
hr { border: 0; border-top: 1px solid var(--border); margin: 18px 0; }
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input,
div[data-baseweb="select"] > div {
  border-radius: 7px !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _panel_head(label: str, title: str, sub: str = "", badge: str | None = None, badge_kind: str = "") -> None:
    badge_html = ""
    if badge:
        cls = f"sd-badge {badge_kind}".strip()
        badge_html = f'<span class="{cls}">{badge}</span>'
    sub_html = f"<p>{sub}</p>" if sub else ""
    st.markdown(
        f"""
<div class="sd-panel-head">
  <div>
    <span class="label">{label}</span>
    <h3>{title}</h3>
    {sub_html}
  </div>
  {badge_html}
</div>
""",
        unsafe_allow_html=True,
    )


def _step_rail(active_idx: int, done_until: int = -1) -> None:
    steps = [
        ("1", "Create Deck", "source and analysis"),
        ("2", "Configure",   "style and outputs"),
        ("3", "Generate",    "resumable pipeline"),
        ("4", "Review",      "preview and download"),
    ]
    parts: list[str] = ['<div class="sd-rail">']
    for i, (num, title, sub) in enumerate(steps):
        cls = "sd-step"
        if i <= done_until:
            cls += " done"
        if i == active_idx:
            cls += " active"
        parts.append(
            f'<div class="{cls}"><span class="num">{num}</span>'
            f'<span><strong>{title}</strong><span class="sub">{sub}</span></span></div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_pipeline_timeline(snap) -> None:
    """Render the live timeline + recent event log from a ProgressBus snapshot.

    Called every autorefresh tick while the pipeline is running, plus once
    after it finishes. The snapshot is plain data (no Streamlit objects),
    so this is safe from any thread.
    """
    state_class = {
        "queued": "",        # plain dot
        "running": "active",
        "done": "done",
        "skipped": "done",   # show as solid green; detail explains it
        "error": "bad",
    }
    rows_html: list[str] = ['<div class="sd-timeline">']
    for stage in Stage:
        info = snap.stages[stage]
        cls = state_class.get(info.state, "queued")
        title = info.label or stage.display
        detail = info.detail or ""
        if info.state == "skipped" and not detail:
            detail = "skipped"
        elif info.items_total and info.state in ("running", "done"):
            detail = f"{detail} — {info.items_done}/{info.items_total}".strip(" —")
        runtime = info.runtime
        if info.state == "running":
            runtime = runtime or "…"
        elif info.state == "queued":
            runtime = "queued"
        elif info.state == "skipped":
            runtime = runtime or "—"
        rows_html.append(
            f'<div class="sd-trow"><span class="sd-dot {cls}"></span>'
            f'<div><strong>{title}</strong><span class="sub">{detail}</span></div>'
            f'<span class="sd-runtime">{runtime}</span></div>'
        )
    rows_html.append("</div>")
    st.markdown("".join(rows_html), unsafe_allow_html=True)

    if snap.events:
        # Show the last ~12 events under the timeline so users see live signals.
        tail = snap.events[-12:]
        log_lines = []
        for ev in tail:
            ts = datetime.fromtimestamp(ev.ts).strftime("%H:%M:%S")
            stage_tag = f"[{ev.stage.value}] " if ev.stage is not None else ""
            log_lines.append(f"{ts} {stage_tag}{ev.text}")
        st.expander(f"Pipeline log ({len(snap.events)} event{'s' if len(snap.events) != 1 else ''})") \
          .code("\n".join(log_lines), language="text")


def _format_history_short(h: dict[str, Any]) -> str:
    ts = datetime.fromtimestamp(h["mtime"])
    today = datetime.now().date()
    if ts.date() == today:
        return ts.strftime("%H:%M")
    if (today - ts.date()).days == 1:
        return "Yesterday"
    return ts.strftime("%b %d")


# Page setup
st.set_page_config(page_title="skilldeck", layout="wide", initial_sidebar_state="expanded")
_dotenv_path = REPO_DIR / ".env"
load_dotenv_robust(_dotenv_path)
_inject_theme_css()

if not SKILL_DIR.exists():
    st.error(f"Missing skill directory: {SKILL_DIR}")
    st.stop()

cfg = load_app_config()
prefs, prefs_path = load_extend_md()

presets = list_style_presets(SKILL_DIR)
preset_names = [p.name for p in presets]
if not preset_names:
    st.error("No style presets found under `skill/references/styles/*.md`.")
    st.stop()

default_preset = _get(cfg, "inputs.default_style_preset", prefs.style or preset_names[0])
if default_preset not in preset_names:
    default_preset = preset_names[0]

planning_base_url = env_default("PLANNING_BASE_URL").strip()
planning_api_key = env_default("PLANNING_API_KEY").strip()
planning_model = env_default("PLANNING_MODEL").strip()
image_base_url = env_default("IMAGE_BASE_URL").strip()
image_api_key = env_default("IMAGE_API_KEY").strip()
image_model_env = env_default("IMAGE_MODEL").strip()
planning_max_tokens = int(env_default("PLANNING_MAX_TOKENS", "8000") or "8000")
image_size_env = normalize_image_size(env_default("IMAGE_SIZE", "1920x1080"))

histories = list_deck_history()
_HISTORY_CURRENT = "__current__"

# ------------------------------- Sidebar (deck library) ----------------------
with st.sidebar:
    st.markdown(
        """
<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px">
  <div style="display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:center">
    <div style="width:28px;height:28px;border:1px solid var(--fg);border-radius:6px;display:grid;place-items:center;
                font:700 12px/1 ui-monospace,Menlo,monospace;background:var(--surface)">SD</div>
    <div>
      <div style="font-weight:700;font-size:15px;line-height:1.1">skilldeck</div>
      <div style="color:var(--muted);font-size:12px">Editable AI deck cockpit</div>
    </div>
  </div>
  <span class="sd-badge good">ready</span>
</div>
""",
        unsafe_allow_html=True,
    )

    if prefs_path:
        st.caption(f"EXTEND.md: `{prefs_path}`")

    st.markdown('<span style="color:var(--muted);font:700 11px/1 ui-monospace,Menlo,monospace;'
                'letter-spacing:.06em;text-transform:uppercase">Deck library</span>',
                unsafe_allow_html=True)

    if histories:
        preview_options = [_HISTORY_CURRENT] + [h["slug"] for h in histories]
        preview_pick = st.selectbox(
            "Preview outputs from",
            options=preview_options,
            format_func=lambda s: "Current session"
            if s == _HISTORY_CURRENT
            else format_deck_history_row(histories, s),
            key="deck_history_pick",
            label_visibility="collapsed",
        )
        st.session_state["_preview_deck_slug"] = None if preview_pick == _HISTORY_CURRENT else preview_pick

        # Render the top 6 most recent decks as styled cards
        for h in histories[:6]:
            slug = h["slug"]
            short = slug if len(slug) <= 28 else slug[:26] + "…"
            when = _format_history_short(h)
            badges: list[str] = []
            if h["has_pptx"]:
                badges.append('<span class="sd-badge good">PPTX</span>')
            if h["has_pdf"]:
                badges.append('<span class="sd-badge good">PDF</span>')
            elif h["has_pptx"]:
                badges.append('<span class="sd-badge warn">PDF missing</span>')
            if h["png_count"]:
                badges.append(f'<span class="sd-badge">{h["png_count"]} PNG</span>')
            if not h["has_pptx"] and not h["has_pdf"] and not h["png_count"]:
                badges.append('<span class="sd-badge bad">empty</span>')
            active = " active" if slug == st.session_state.get("_preview_deck_slug") else ""
            st.markdown(
                f"""
<div class="sd-deck{active}">
  <div class="row"><span>{short}</span><span class="sd-runtime">{when}</span></div>
  <div class="meta">{''.join(badges)}</div>
</div>
""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No decks in `slide-deck/` yet.")
        st.session_state["_preview_deck_slug"] = None

    st.markdown(
        '<div style="margin-top:12px;border:1px solid var(--border);border-radius:8px;'
        'padding:10px;background:oklch(99% 0.002 240);color:var(--muted);font-size:12px">'
        "Library lives here so it stays out of the run flow."
        "</div>",
        unsafe_allow_html=True,
    )

# ------------------------------- Env validation -----------------------------
missing_planning = not (planning_base_url and planning_api_key and planning_model)
missing_image = not (image_base_url and image_api_key)  # image model is now picked in UI
if missing_planning or missing_image:
    missing: list[str] = []
    if not planning_base_url:
        missing.append("PLANNING_BASE_URL")
    if not planning_api_key:
        missing.append("PLANNING_API_KEY")
    if not planning_model:
        missing.append("PLANNING_MODEL")
    if not image_base_url:
        missing.append("IMAGE_BASE_URL")
    if not image_api_key:
        missing.append("IMAGE_API_KEY")

    st.error("Missing required `.env` variables: " + ", ".join(missing))
    st.caption(f"Expected file: `{_dotenv_path}` (exists: `{_dotenv_path.exists()}`)")
    if _dotenv_path.exists():
        env_text = _dotenv_path.read_text(encoding="utf-8", errors="ignore")
        blank_keys: list[str] = []
        for k in missing:
            m = re.search(rf"^{re.escape(k)}\s*=\s*(.*)$", env_text, flags=re.MULTILINE)
            if m is not None and m.group(1).strip() == "":
                blank_keys.append(k)
        if blank_keys:
            st.warning(
                "Your `.env` has blank values for: " + ", ".join(blank_keys)
                + ". Fill them and restart Streamlit."
            )
    st.info(
        "Tip: empty `PLANNING_*` / `IMAGE_*` exports in your shell can hide `.env` values. "
        "This app loads `.env` with **override=True** — restart Streamlit after editing `.env`."
    )
    st.stop()

# ------------------------------- Topbar -------------------------------------
st.markdown(
    """
<div class="sd-topbar">
  <div>
    <h2>Slide Deck Generator</h2>
    <p>Turn source text or PDFs into polished, editable PowerPoint decks.</p>
  </div>
  <div class="actions"><span>auto-saves to <code>slide-deck/&lt;slug&gt;/</code></span></div>
</div>
""",
    unsafe_allow_html=True,
)

# ------------------------------- Workflow state -----------------------------
# Tracks step progression for the rail: 0=Create, 1=Configure, 2=Generate, 3=Review.
if "_active_step" not in st.session_state:
    st.session_state._active_step = 0
if "_done_until" not in st.session_state:
    st.session_state._done_until = -1

# ============================== Step 1: Create ==============================
_step_rail(active_idx=st.session_state._active_step, done_until=st.session_state._done_until)

st.markdown('<div id="create"></div>', unsafe_allow_html=True)
col_create_l, col_create_r = st.columns([1.15, 0.85], gap="medium")

with col_create_l:
    _panel_head(
        "Create Deck",
        "Source content",
        "Paste raw notes, upload a PDF, or use both. Analysis stays readable and non-technical.",
        badge="draft",
    )
    with st.container():
        st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)
        source_text = st.text_area(
            "Source text",
            height=240,
            key="source_text",
            placeholder="Paste meeting notes, a report excerpt, a founder memo, or long-form research…",
            label_visibility="collapsed",
        )
        source_pdf = st.file_uploader(
            "Upload source PDF (text is extracted and combined with the box above)",
            type=["pdf"],
            key="source_pdf",
        )
        topic_hint = st.text_input(
            "Optional topic hint",
            key="topic_hint",
            placeholder="e.g. Market entry briefing",
        )
        st.markdown("</div>", unsafe_allow_html=True)

pdf_extracted = ""
if source_pdf is not None:
    try:
        pdf_extracted = extract_pdf_text(source_pdf.getvalue())
    except Exception as e:
        st.error(f"Could not read this PDF: {e}")

combined_source = "\n\n".join(x for x in (source_text.strip(), pdf_extracted.strip()) if x).strip()

with col_create_r:
    _panel_head(
        "Auto analysis",
        "Recommended setup",
        "Suggestions appear before expensive generation starts.",
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)
    if not combined_source:
        st.markdown(
            '<div style="color:var(--muted);font-size:13px">'
            "Paste source content or upload a PDF on the left to see analysis."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        words = len(re.findall(r"\w+", combined_source))
        detected_language = detect_language(combined_source)
        recommended_style = recommend_style_preset(combined_source)
        recommended_slides = recommend_slide_count(words)
        slug_base = topic_hint.strip() or (
            combined_source.strip().splitlines()[0][:80] if combined_source.strip() else "deck"
        )
        topic_slug = slugify(slug_base)
        st.markdown(
            f"""
<div class="sd-metric-grid">
  <div class="sd-metric"><small>Words</small><strong>{words:,}</strong></div>
  <div class="sd-metric"><small>Language</small><strong>{detected_language.upper()}</strong></div>
  <div class="sd-metric"><small>Slides</small><strong>{recommended_slides}</strong></div>
  <div class="sd-metric"><small>Style</small><strong style="font-size:14px">{recommended_style}</strong></div>
</div>
<div class="sd-reco">
  <strong>Editable PPTX is the primary output</strong>
  <p>Text, charts, dividers, cards, and common shapes are rebuilt as PowerPoint-native objects where possible.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        if source_pdf is not None and pdf_extracted:
            st.caption(f"PDF: extracted {len(pdf_extracted):,} characters from `{source_pdf.name}`.")
        st.markdown("</div>", unsafe_allow_html=True)

# Stop early if no source — Configure / Generate / Review can't proceed.
if not combined_source:
    st.stop()

# Build analysis dict for downstream steps.
analysis = {
    "words": words,
    "detected_language": detected_language,
    "recommended_style": recommended_style,
    "recommended_slides": recommended_slides,
    "topic_slug": topic_slug,
}

# Source has been entered, so Step 1 is effectively done.
if st.session_state._done_until < 0:
    st.session_state._done_until = 0
if st.session_state._active_step < 1:
    st.session_state._active_step = 1

# ============================== Step 2: Configure ===========================
st.markdown('<div id="configure"></div><hr/>', unsafe_allow_html=True)
col_cfg_l, col_cfg_r = st.columns([1.15, 0.85], gap="medium")

with col_cfg_l:
    _panel_head(
        "Configure Deck",
        "Presentation settings",
        "A confirmation file is written here. Generation starts only after these choices are approved.",
        badge="confirmation.yaml",
        badge_kind="good",
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)

    # Row 1: audience / language
    c1, c2 = st.columns(2)
    with c1:
        audience_options = ["beginners", "intermediate", "experts", "executives", "general"]
        audience_index = audience_options.index(prefs.audience) if prefs.audience in audience_options else 4
        audience = st.selectbox("Audience", audience_options, index=audience_index, key="audience")
    with c2:
        lang_options = ["auto", "en", "zh", "ja"]
        lang_index = lang_options.index(prefs.language) if prefs.language in lang_options else 0
        lang = st.selectbox("Language", lang_options, index=lang_index, key="lang")

    # Row 2: slide count / canvas (aspect)
    c3, c4 = st.columns(2)
    with c3:
        slides = st.number_input(
            "Slide count",
            min_value=1, max_value=30,
            value=max(1, min(30, int(recommended_slides))),
            step=1, key="slides",
        )
    with c4:
        aspect = st.selectbox(
            "Output canvas",
            options=["16:9", "4:3", "custom"],
            index=0,
            key="img_aspect",
            help="Image dimensions get snapped to a multiple of 16 for the backend.",
        )

    # Row 3: image model picker (NEW) + image size rounding
    c5, c6 = st.columns(2)
    with c5:
        default_image_model = _resolve_default_image_model(image_model_env)
        if default_image_model not in IMAGE_MODEL_CHOICES:
            # Show the env-supplied custom model alongside the standard three.
            choices = [default_image_model] + IMAGE_MODEL_CHOICES
            default_idx = 0
        else:
            choices = IMAGE_MODEL_CHOICES
            default_idx = choices.index(default_image_model)
        image_model = st.selectbox(
            "Image model",
            options=choices,
            index=default_idx,
            key="image_model_choice",
            help=(
                "gpt-image-2-cheap — fastest/cheapest draft quality.\n"
                "gpt-image-2 — balanced default.\n"
                "nano-banana-pro — highest fidelity, slower & costlier."
            ),
        )
    with c6:
        snap_mode = st.selectbox(
            "Divisible-by-16 rounding",
            options=["nearest", "down", "up"],
            index=0, key="img_snap",
        )

    # Row 4: width / height
    c7, c8 = st.columns(2)
    with c7:
        target_width = st.number_input(
            "Target width (px)",
            min_value=256, max_value=4096, value=1920, step=16, key="img_w",
        )
    with c8:
        target_height = st.number_input(
            "Target height (px) — custom only",
            min_value=256, max_value=4096, value=1080, step=16, key="img_h",
            disabled=(aspect != "custom"),
        )

    computed_size = compute_image_size(
        aspect=aspect,
        target_width=int(target_width),
        target_height=int(target_height),
        snap_mode=snap_mode,
    )
    st.markdown(
        f'<div class="sd-badge good" style="margin-top:6px">image size: {computed_size}</div>',
        unsafe_allow_html=True,
    )

    # Export options
    export_pdf_default = (os.getenv("SKILLDECK_EXPORT_PDF", "1") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    export_pdf = st.checkbox(
        "Also export PDF",
        value=export_pdf_default,
        key="export_pdf",
        help=(
            "PDF runs after the editable PPTX is written. Skipping it makes "
            "long runs return faster; you can always re-run export later. "
            "Default comes from SKILLDECK_EXPORT_PDF (currently "
            f"{'on' if export_pdf_default else 'off'})."
        ),
    )

    # Visual style cards + native preset list
    st.markdown(
        '<div style="display:flex;align-items:center;justify-content:space-between;'
        'margin:18px 0 8px"><span style="color:var(--muted);font:700 11px/1 ui-monospace,Menlo,monospace;'
        'letter-spacing:.06em;text-transform:uppercase">Visual style</span></div>',
        unsafe_allow_html=True,
    )
    style_cards = [
        ("Consulting deck",   "Structured, executive-ready, dense enough for briefing work.",
         ["#fff", "#f3f5f8", "#1f2937", "#2563eb"], "consulting-deck"),
        ("Minimal",           "Quiet slides with strong type and sparse visual marks.",
         ["#fbfbfb", "#111", "#d6d6d6", "#4f46e5"], "minimal"),
        ("Scientific",        "Charts, evidence, tables, and methodical hierarchy.",
         ["#0f172a", "#1e293b", "#94a3b8", "#22c55e"], "scientific"),
    ]
    cards_html: list[str] = ['<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px">']
    chosen_quick_style = (
        recommended_style if recommended_style in [s[3] for s in style_cards]
        else style_cards[0][3]
    )
    for title, desc, swatches, slug in style_cards:
        active = " active" if slug == chosen_quick_style else ""
        sw_html = "".join(f'<span class="sd-swatch" style="background:{c}"></span>' for c in swatches)
        cards_html.append(
            f'<div class="sd-style-card{active}"><div class="sd-swatches">{sw_html}</div>'
            f'<div><h4>{title}</h4><p>{desc}</p></div></div>'
        )
    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    # Full preset selector (the cards above are visual hints; this is the source of truth)
    style_options = preset_names + ["custom-dimensions"]
    if recommended_style in preset_names:
        default_style_idx = preset_names.index(recommended_style)
    elif default_preset in preset_names:
        default_style_idx = preset_names.index(default_preset)
    else:
        default_style_idx = 0
    style_choice = st.selectbox(
        "Style preset",
        options=style_options,
        index=default_style_idx,
        key="style_choice",
        format_func=lambda name: (
            "custom-dimensions"
            if name == "custom-dimensions"
            else format_style_preset_label(str(name), presets)
        ),
        help=(
            "Unified presets from skill/references/styles/. Some entries are backed by "
            "skill/templates/layouts SVG packs and use those SVGs as prompt guidance."
        ),
    )

    dims = None
    if style_choice == "custom-dimensions":
        with st.expander("Custom dimensions", expanded=True):
            dc1, dc2 = st.columns(2)
            with dc1:
                texture = st.selectbox("Texture", ["clean", "grid", "organic", "pixel", "paper"], key="dim_texture")
                typography = st.selectbox(
                    "Typography",
                    ["geometric", "humanist", "handwritten", "editorial", "technical"],
                    key="dim_typography",
                )
            with dc2:
                mood = st.selectbox(
                    "Mood",
                    ["professional", "warm", "cool", "vibrant", "dark", "neutral", "macaron"],
                    key="dim_mood",
                )
                density = st.selectbox("Density", ["minimal", "balanced", "dense"], index=1, key="dim_density")
            dims = {"texture": texture, "mood": mood, "typography": typography, "density": density}

    st.markdown("</div>", unsafe_allow_html=True)

with col_cfg_r:
    _panel_head(
        "Reference assets",
        "Optional style inputs",
        "References are saved with the deck so the run can be audited later.",
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)
    ref_files = st.file_uploader(
        "PNG, JPG, JPEG, WEBP",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="ref_files",
    )
    ref_usage = st.selectbox(
        "Reference usage mode",
        options=["direct", "style", "palette"],
        index=0,
        key="ref_usage",
    )
    st.markdown(
        """
<ul style="display:grid;gap:8px;margin:8px 0 0;padding:0;list-style:none">
  <li style="display:grid;grid-template-columns:18px 1fr;gap:8px;color:var(--muted);font-size:12px">
    <span style="width:7px;height:7px;margin-top:7px;border-radius:999px;background:var(--accent)"></span>
    Image dimensions auto-snap to a multiple of 16 (backend constraint).
  </li>
  <li style="display:grid;grid-template-columns:18px 1fr;gap:8px;color:var(--muted);font-size:12px">
    <span style="width:7px;height:7px;margin-top:7px;border-radius:999px;background:var(--accent)"></span>
    Custom dimensions are available without exposing backend math first.
  </li>
  <li style="display:grid;grid-template-columns:18px 1fr;gap:8px;color:var(--muted);font-size:12px">
    <span style="width:7px;height:7px;margin-top:7px;border-radius:999px;background:var(--accent)"></span>
    Image model is per-run; nano-banana-pro is best for hero/cover slides.
  </li>
</ul>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Confirm button — full-width row below the two columns.
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
confirm_col1, confirm_col2 = st.columns([3, 1])
with confirm_col2:
    confirm_run = st.button("Confirm & generate", type="primary", key="confirm_run", width="stretch")
with confirm_col1:
    st.caption(
        "Hard gate: outline → prompts → images/charts → editable PPTX runs only after confirmation. "
        "Generation auto-saves to `slide-deck/" + topic_slug + "/`."
    )

# Build confirmation dict (used by the pipeline + signature).
confirmed_params: dict[str, Any] = {
    "style": style_choice,
    "audience": audience,
    "language": lang,
    "slides": int(slides),
    "review_outline": False,
    "review_prompts": False,
    "dimensions": dims,
    "ref_usage": ref_usage,
    "image_aspect": aspect,
    "image_size": computed_size,
    "image_model": image_model,
}

# Persist source + analysis bookkeeping (mirrors the skill).
# Use change-detection writes so Streamlit reruns don't create backup storms.
deck_dir = get_session_deck_dir(topic_slug)
ensure_dir(deck_dir)
write_text_if_changed(deck_dir / f"source-{topic_slug}.md", combined_source)
write_text_if_changed(
    deck_dir / "analysis.md",
    yaml.safe_dump(analysis, sort_keys=False, allow_unicode=True),
)

refs_meta: list[dict[str, str]] = []
if ref_files:
    ensure_dir(deck_dir / "refs")
    for i, f in enumerate(ref_files, start=1):
        ext = Path(f.name).suffix.lower() or ".png"
        dest = deck_dir / "refs" / f"{i:02d}-ref-{slugify(Path(f.name).stem)}{ext}"
        write_bytes_if_changed(dest, f.getvalue())
        refs_meta.append({"ref_id": f"{i:02d}", "filename": dest.name, "usage": ref_usage})

# Configure step is interactive — once user clicks Confirm we move on.
if st.session_state._done_until < 1 and confirm_run:
    st.session_state._done_until = 1
if st.session_state._active_step < 2 and confirm_run:
    st.session_state._active_step = 2

# ============================== Step 3: Generate ============================
st.markdown('<div id="generate"></div><hr/>', unsafe_allow_html=True)

# Re-run the rail so it reflects updated state after confirm/run.
# (The earlier rail render at the top is cosmetic; this one is canonical mid-page.)

sig_obj = {
    "source_text": combined_source,
    "topic_hint": topic_hint,
    "analysis": analysis,
    "confirmed_params": confirmed_params,
    "refs": refs_meta,
    "planning_model": planning_model,
    "planning_base_url": planning_base_url,
    "image_model": image_model,
    "image_base_url": image_base_url,
    "image_size": confirmed_params.get("image_size") or image_size_env,
    "planning_max_tokens": planning_max_tokens,
}
sig = stable_hash(sig_obj)

if "last_pipeline_sig" not in st.session_state:
    st.session_state.last_pipeline_sig = ""
if "approved_sig" not in st.session_state:
    st.session_state.approved_sig = ""
if "last_pipeline_error" not in st.session_state:
    st.session_state.last_pipeline_error = ""

if confirm_run:
    st.session_state.approved_sig = sig
    st.session_state.last_pipeline_sig = ""
    st.session_state.last_pipeline_error = ""

# Compute timeline rows from current deck_dir state.
def _read_timeline_state(d: Path) -> list[tuple[str, str, str, str]]:
    """Return [(state, title, sub, runtime), ...] for the 5 pipeline stages."""
    has_source = (d / f"source-{d.name}.md").exists()
    has_analysis = (d / "analysis.md").exists()
    has_outline = (d / "outline.md").exists()
    prompt_dir = d / "prompts"
    n_prompts = len(list_active_slide_files(prompt_dir, ".md")) if prompt_dir.exists() else 0
    n_charts_spec = len(list_active_slide_files(prompt_dir, ".chart.json")) if prompt_dir.exists() else 0
    n_chart_svg = len(list_active_slide_files(d, ".svg"))
    n_pngs = len(list_active_slide_files(d, ".png"))
    has_pptx = (d / f"{d.name}.pptx").exists()

    def state(done: bool, started: bool = False) -> str:
        if done:
            return "done"
        if started:
            return "active"
        return "queued"

    rows: list[tuple[str, str, str, str]] = []
    rows.append((
        state(has_source and has_analysis),
        "Source and analysis saved",
        "source-*.md, analysis.md, confirmation.yaml",
        "✓" if has_source and has_analysis else "—",
    ))
    rows.append((
        state(has_outline, has_source),
        "Outline generated and validated",
        f"outline.md{' (present)' if has_outline else ''}",
        "✓" if has_outline else ("…" if has_source else "—"),
    ))
    rows.append((
        state(n_prompts > 0 or n_charts_spec > 0, has_outline),
        "Per-slide prompts created",
        f"{n_prompts} image prompts, {n_charts_spec} chart specs",
        "✓" if (n_prompts > 0 or n_charts_spec > 0) else ("…" if has_outline else "—"),
    ))
    target_assets = max(int(confirmed_params["slides"]), 1)
    produced_assets = n_pngs + n_chart_svg
    rows.append((
        state(produced_assets >= target_assets, n_prompts + n_charts_spec > 0),
        "Image and chart slides",
        f"{produced_assets} of {target_assets} produced ({n_chart_svg} chart SVGs)",
        f"{produced_assets}/{target_assets}",
    ))
    rows.append((
        state(has_pptx, produced_assets > 0),
        "Editable PPTX assembly",
        f"{d.name}.pptx" if has_pptx else "Waiting for slide assets",
        "✓" if has_pptx else ("…" if produced_assets > 0 else "queued"),
    ))
    return rows


col_gen_l, col_gen_r = st.columns([1.15, 0.85], gap="medium")

with col_gen_l:
    is_running = (
        st.session_state.approved_sig == sig
        and sig != st.session_state.last_pipeline_sig
        and not st.session_state.last_pipeline_error
    )
    if st.session_state.last_pipeline_error:
        head_badge, head_kind = "needs attention", "bad"
    elif is_running:
        head_badge, head_kind = "running", "warn"
    elif st.session_state.last_pipeline_sig == sig:
        head_badge, head_kind = "complete", "good"
    else:
        head_badge, head_kind = "awaiting confirm", ""
    _panel_head(
        "Generate",
        "Resumable production pipeline",
        "Long steps show last completed artifact and the safest restart point.",
        badge=head_badge,
        badge_kind=head_kind,
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)

    # If a live progress bus exists for the current sig, the timeline is rendered
    # below in the run-pipeline block (after the worker is spawned). Skip the
    # filesystem-polled fallback in that case to avoid double rendering.
    live_bus = st.session_state.get(f"pipeline_bus::{sig}")
    if live_bus is None:
        rows = _read_timeline_state(deck_dir)
        timeline_html: list[str] = ['<div class="sd-timeline">']
        for state, title, sub, runtime in rows:
            timeline_html.append(
                f'<div class="sd-trow"><span class="sd-dot {state}"></span>'
                f'<div><strong>{title}</strong><span class="sub">{sub}</span></div>'
                f'<span class="sd-runtime">{runtime}</span></div>'
            )
        timeline_html.append("</div>")
        st.markdown("".join(timeline_html), unsafe_allow_html=True)

    # Recovery card — visible whenever a deck folder has any partial output.
    has_any_output = bool(list_active_slide_files(deck_dir, ".png")) or bool(list_active_slide_files(deck_dir, ".svg"))
    if has_any_output and not (deck_dir / f"{topic_slug}.pptx").exists():
        st.markdown(
            """
<div class="sd-recovery">
  <h4>Mid-step recovery available <span class="sd-badge warn">timeout-safe</span></h4>
  <p>If the process times out or the browser disconnects, resume from the last completed stage instead of starting over. Existing slide images, SVG charts, the outline, and prompts are preserved on disk.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        rc1, rc2 = st.columns([1, 1])
        with rc1:
            if st.button("Re-run export only (PPTX + PDF)", key="recovery_export", width="stretch"):
                with st.status("Re-running export…", expanded=True) as export_status:
                    export_status.write("Starting editable PPTX and PDF merge…")
                    retry_log, retry_err = merge_deck(deck_dir=deck_dir, export_pdf=export_pdf)
                    export_status.code(retry_log or "(no log)", language="text")
                if retry_err:
                    st.warning(retry_err)
                else:
                    st.success("Export finished — editable PPTX updated.")
                st.rerun()
        with rc2:
            if st.button("Restart full pipeline", key="recovery_restart", width="stretch"):
                st.session_state.last_pipeline_sig = ""
                st.session_state.last_pipeline_error = ""
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

with col_gen_r:
    _panel_head(
        "Recovery paths",
        "Actionable error states",
        "Errors describe what to fix, then offer the narrowest retry.",
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)
    mineru_set = bool(os.getenv("MINERU_TOKEN", "").strip())
    pptx_present = (deck_dir / f"{topic_slug}.pptx").exists()
    last_err = st.session_state.last_pipeline_error
    cards: list[tuple[str, str, str]] = []
    if not mineru_set:
        cards.append((
            "Missing MinerU token", "Export blocked",
            "Add MINERU_TOKEN to `.env`, then re-run export only.",
        ))
    if last_err:
        cards.append(("Last run error", "See message", last_err[:240]))
    if not last_err and not pptx_present and list_active_slide_files(deck_dir, ".png"):
        cards.append((
            "PDF viewer unavailable", "Download still works",
            "No iframe dependency in the main success state.",
        ))
    if not cards:
        st.markdown(
            '<div style="color:var(--muted);font-size:13px">No errors. Recovery actions appear here when something goes wrong.</div>',
            unsafe_allow_html=True,
        )
    else:
        for small, big, body in cards:
            st.markdown(
                f"""
<div class="sd-metric" style="margin-bottom:10px">
  <small>{small}</small>
  <strong style="font-size:16px">{big}</strong>
  <p style="color:var(--muted);margin:8px 0 0;font-size:12px">{body}</p>
</div>
""",
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

# Run pipeline if approved sig matches but hasn't been executed yet.
if st.session_state.approved_sig != sig:
    st.info("Edit settings above, then click **Confirm & generate** to start the pipeline.")
elif sig != st.session_state.last_pipeline_sig:
    # Background-thread runner with autorefresh polling. The progress bus is
    # the source of truth for the timeline; the worker thread updates it,
    # the main Streamlit script reads it once per autorefresh tick.
    import threading
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    try:
        from streamlit_autorefresh import st_autorefresh
    except Exception:  # pragma: no cover - optional dep
        st_autorefresh = None

    bus_state_key = f"pipeline_bus::{sig}"
    thread_state_key = f"pipeline_thread::{sig}"
    error_state_key = f"pipeline_error::{sig}"

    bus: ProgressBus | None = st.session_state.get(bus_state_key)
    worker: threading.Thread | None = st.session_state.get(thread_state_key)

    # Recover cleanly if a prior run with the same signature left stale state
    # (for example, failed/finished worker thread but same confirmed params).
    stale_or_missing_worker = (
        worker is None or (isinstance(worker, threading.Thread) and not worker.is_alive())
    )
    terminal_bus = (
        bus is None
        or bus.snapshot().overall_state in {"done", "error"}
    )
    if stale_or_missing_worker and terminal_bus:
        st.session_state.pop(bus_state_key, None)
        st.session_state.pop(thread_state_key, None)
        st.session_state.pop(error_state_key, None)
        bus = None
        worker = None

    if bus is None:
        bus = ProgressBus()
        st.session_state[bus_state_key] = bus

        # Capture variables needed inside the worker; nothing on `st.session_state`
        # should be touched from the worker thread.
        worker_args = dict(
            source_text=combined_source,
            topic_hint=topic_hint,
            analysis=analysis,
            confirmed_params=confirmed_params,
            ref_files_meta=refs_meta,
            planning_base_url=planning_base_url,
            planning_api_key=planning_api_key,
            planning_model=planning_model,
            planning_max_tokens=planning_max_tokens,
            image_base_url=image_base_url,
            image_api_key=image_api_key,
            image_model=image_model,
            image_size=confirmed_params.get("image_size") or image_size_env,
            preset_names=preset_names,
            export_pdf=export_pdf,
            progress=bus,
        )

        def _run_pipeline_thread() -> None:
            try:
                run_pipeline(**worker_args)
            except Exception as exc:  # noqa: BLE001 - surface to UI
                bus.mark_error(str(exc))

        worker = threading.Thread(target=_run_pipeline_thread, daemon=True,
                                   name=f"skilldeck-pipeline-{topic_slug}")
        # Attach Streamlit's ScriptRunContext so st.write/st.warning calls
        # inside the pipeline don't emit ScriptRunContext warnings.
        add_script_run_ctx(worker)
        worker.start()
        st.session_state[thread_state_key] = worker

    snap = bus.snapshot()
    is_alive = worker.is_alive() if worker is not None else False
    overall = snap.overall_state

    # Render live timeline.
    _render_pipeline_timeline(snap)

    # Drive reruns while the worker is still going.
    if is_alive and overall == "running":
        if st_autorefresh is not None:
            st_autorefresh(interval=1000, key=f"pipeline_autorefresh::{sig}")
        else:
            time.sleep(1.0)
            st.rerun()
    else:
        # Terminal: clean up so the next sig change starts fresh.
        last_err = st.session_state.get(error_state_key, "") or snap.error or ""
        if last_err:
            st.session_state.last_pipeline_error = last_err
            st.error(last_err)
            # leave the bus around so the user sees the failed timeline
            st.stop()
        else:
            st.session_state.last_pipeline_sig = sig
            st.session_state.last_pipeline_error = ""
            st.session_state._done_until = max(st.session_state._done_until, 2)
            st.session_state._active_step = 3
            # Drop the bus / thread refs for the completed run.
            st.session_state.pop(bus_state_key, None)
            st.session_state.pop(thread_state_key, None)
            st.session_state.pop(error_state_key, None)
            st.rerun()
else:
    st.session_state._done_until = max(st.session_state._done_until, 2)
    st.session_state._active_step = 3

# ============================== Step 4: Review ==============================
st.markdown('<div id="review"></div><hr/>', unsafe_allow_html=True)

# Switch to a previewed historical deck if the sidebar selected one.
preview_slug = st.session_state.get("_preview_deck_slug")
if preview_slug:
    out_slug = preview_slug
    output_deck_dir = DECKS_DIR / preview_slug
    st.info(
        f"Showing files from **{preview_slug}** (sidebar deck library). "
        f"Current session topic is **{topic_slug}**."
    )
else:
    out_slug = topic_slug
    output_deck_dir = deck_dir

pptx_path = output_deck_dir / f"{out_slug}.pptx"
pdf_path = output_deck_dir / f"{out_slug}.pdf"
images = list_active_slide_files(output_deck_dir, ".png")
charts = list_active_slide_files(output_deck_dir, ".svg")
slide_count_actual = len(images) + len(charts)

col_rev_l, col_rev_r = st.columns([1.15, 0.85], gap="medium")

with col_rev_l:
    review_badge = f"{slide_count_actual} slide{'s' if slide_count_actual != 1 else ''}"
    review_kind = "good" if slide_count_actual else ""
    _panel_head(
        "Review Output",
        "Slide gallery",
        "Preview image slides and structured chart slides in one ordered deck view.",
        badge=review_badge,
        badge_kind=review_kind,
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)

    if not (images or charts):
        st.markdown(
            '<div style="color:var(--muted);font-size:13px">'
            "Slides will appear here once generation completes."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        all_slides: list[tuple[Path, str]] = (
            [(p, "PNG") for p in images] + [(p, "SVG") for p in charts]
        )
        all_slides.sort(key=lambda x: x[0].name)
        # Render thumbs in a 3-column grid.
        for chunk_start in range(0, len(all_slides), 3):
            cols = st.columns(3)
            for i, col in enumerate(cols):
                idx = chunk_start + i
                if idx >= len(all_slides):
                    break
                p, kind = all_slides[idx]
                with col:
                    try:
                        st.image(str(p), width="stretch")
                    except Exception:
                        if kind == "SVG":
                            st.markdown(p.read_text(encoding="utf-8"), unsafe_allow_html=True)
                    label = p.stem.replace("-slide-", " · ")
                    st.markdown(
                        f'<div class="sd-thumb" style="border:none;margin-top:-6px">'
                        f'<div class="cap"><strong>{label}</strong>'
                        f'<span class="sd-badge">{kind}</span></div></div>',
                        unsafe_allow_html=True,
                    )

    # Download cards — labels live in HTML, buttons sit underneath.
    st.markdown(
        """
<div class="sd-dl-grid">
  <div class="sd-dl-card">
    <strong>Editable PowerPoint</strong>
    <p>Native text, shapes, chart regions, layout elements where possible.</p>
  </div>
  <div class="sd-dl-card">
    <strong>PDF export</strong>
    <p>Available when export tooling completes successfully.</p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    dl_a, dl_b = st.columns(2)
    with dl_a:
        if pptx_path.exists():
            st.download_button(
                "Download PPTX",
                data=pptx_path.read_bytes(),
                file_name=pptx_path.name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                width="stretch",
                type="primary",
                key=f"dl_pptx_{out_slug}",
            )
        else:
            st.button("PPTX not ready", disabled=True, width="stretch", key=f"dl_pptx_disabled_{out_slug}")
    with dl_b:
        if pdf_path.exists():
            st.download_button(
                "Download PDF",
                data=pdf_path.read_bytes(),
                file_name=pdf_path.name,
                mime="application/pdf",
                width="stretch",
                key=f"dl_pdf_{out_slug}",
            )
        else:
            st.button("PDF not ready", disabled=True, width="stretch", key=f"dl_pdf_disabled_{out_slug}")

    st.markdown("</div>", unsafe_allow_html=True)

with col_rev_r:
    _panel_head(
        "Export recovery",
        "Retry without regenerating",
        "For failed PPTX/PDF assembly after slides already exist.",
    )
    st.markdown('<div class="sd-panel-body">', unsafe_allow_html=True)
    if images or charts:
        if not pptx_path.exists():
            st.markdown(
                """
<div class="sd-recovery" style="margin-top:0">
  <h4>PPTX export pending <span class="sd-badge warn">needs env</span></h4>
  <p>Slide images, SVG charts, the outline, and prompts are intact. If MINERU_TOKEN is set, retry the export only.</p>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
<div class="sd-recovery" style="margin-top:0;border-color:oklch(85% 0.05 145);background:oklch(98% 0.02 145)">
  <h4>Export complete <span class="sd-badge good">ready</span></h4>
  <p>You can re-run export to refresh the PPTX/PDF without regenerating images.</p>
</div>
""",
                unsafe_allow_html=True,
            )
        if st.button(
            "Re-run export only (editable PPTX + PDF)",
            help="Runs `python -m editable_pptx` and PDF merge only.",
            key=f"retry_export_{out_slug}",
            width="stretch",
        ):
            with st.status("Re-running export…", expanded=True) as export_status:
                export_status.write("Starting editable PPTX and PDF merge…")
                retry_log, retry_err = merge_deck(deck_dir=output_deck_dir, export_pdf=export_pdf)
                export_status.code(retry_log or "(no log)", language="text")
            if retry_err:
                st.warning(retry_err)
            elif pptx_path.exists():
                st.success("Export finished — editable PPTX updated.")
            st.rerun()
    else:
        st.markdown(
            '<div style="color:var(--muted);font-size:13px">'
            "Generate a deck first; export recovery actions appear once slide assets exist."
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div style="margin-top:14px;border:1px solid var(--border);border-radius:8px;'
        'padding:12px;background:oklch(99% 0.002 240);color:var(--muted);font-size:12px">'
        "Keeps expensive image and chart generation work intact when a late export step fails."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Inline PPTX / PDF viewers (kept below the gallery to match mockup hierarchy).
if pptx_path.exists():
    with st.expander("Embedded PPTX viewer (Microsoft Office Online — usually only works for public URLs)", expanded=False):
        viewer = f"https://view.officeapps.live.com/op/embed.aspx?src={urllib.parse.quote(str(pptx_path.resolve().as_uri()))}"
        st.iframe(viewer, height=720)

if pdf_path.exists():
    with st.expander("Inline PDF preview", expanded=False):
        try:
            st.pdf(pdf_path.read_bytes(), height=720)
        except Exception as e:
            st.warning(f"Inline PDF viewer unavailable ({e}). Install with: `pip install 'streamlit[pdf]'` and restart.")
            pdf_bytes = pdf_path.read_bytes()
            if len(pdf_bytes) <= 2_000_000:
                b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
                st.markdown(
                    f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="720" type="application/pdf"></iframe>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("PDF is large; use **Download PDF** above for a reliable view.")

# Final state: if review has any output, mark step 4 done.
if pptx_path.exists() or pdf_path.exists() or images or charts:
    st.session_state._done_until = max(st.session_state._done_until, 3)
