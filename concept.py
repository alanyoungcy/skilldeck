"""Stage 4 of the creative-director pipeline.

Takes a slide's outline block, the architype (layout role), the locked deck
style preset, and a small library of few-shot examples; returns a structured
visual concept (subject, composition, metaphor, mood, foreground/background,
text overlay zone). The concept is the editable surface the user sees to
steer the deck without touching style.

The concept artifact is later templated into the actual image-generation
prompt by `streamlit_app.write_prompt_files`.

Design notes:
  * One LLM call per slide. Sequential per the user's choice.
  * Schema validation rejects malformed responses; the caller decides whether
    to fall back to a default concept or surface the failure.
  * Caching is via the concept JSON file itself: `outline_hash` stamped at
    write time lets `is_concept_stale` detect outline edits, and an
    `edited_by_user` flag (set when the on-disk file's content hash drifts
    from the recorded `original_hash`) lets user edits override regeneration.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONCEPT_VERSION = 1

# The concept block schema. These keys are required in `concept`.
REQUIRED_CONCEPT_KEYS = frozenset({
    "subject",
    "composition",
    "metaphor",
    "mood",
    "foreground_elements",
    "background_treatment",
    "text_overlay_zone",
})

REQUIRED_OVERLAY_KEYS = frozenset({"x", "y", "w", "h"})


# ----------------------------- data shape ---------------------------------


@dataclass
class ConceptResult:
    """Return value of `generate_visual_concept`."""

    concept: dict[str, Any]   # the validated `concept` block
    raw: str                  # the raw LLM response, for debugging


class ConceptError(Exception):
    """Raised when the LLM response can't be parsed into a valid concept."""


# ----------------------------- hashing ------------------------------------


def hash_outline_block(outline_block: str) -> str:
    """Stable hash of a slide's outline text. Drives concept invalidation."""
    return hashlib.sha256(outline_block.encode("utf-8")).hexdigest()


def hash_concept_payload(payload: dict[str, Any]) -> str:
    """Hash the concept block (only) so we can detect manual user edits.

    We hash the canonical JSON form of the `concept` field — bookkeeping
    fields like `outline_hash` and `original_hash` are deliberately excluded.
    """
    body = json.dumps(payload.get("concept") or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ----------------------------- file IO ------------------------------------


def read_concept_file(path: Path) -> dict[str, Any] | None:
    """Read a concept JSON file. Returns None on missing or malformed file."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Concept file unreadable %s: %s", path, e)
        return None


def write_concept_file(
    path: Path,
    *,
    slide_id: str,
    slide_number: int,
    role: str,
    architype: str,
    style_preset: str,
    headline: str,
    subhead: str,
    body: list[str] | None = None,
    concept: dict[str, Any],
    outline_hash: str,
) -> None:
    """Write a concept JSON, stamping outline_hash + original_hash.

    `original_hash` records what the concept hashed to immediately after
    Stage 4 wrote it. `is_concept_stale` later compares the current
    file's concept hash against this value to detect manual user edits.
    """
    payload = {
        "version": CONCEPT_VERSION,
        "slide_id": slide_id,
        "slide_number": slide_number,
        "role": role,
        "architype": architype,
        "style_preset": style_preset,
        "concept": concept,
        "headline": headline,
        "subhead": subhead,
        "body": list(body or []),
        "negative_prompts_extra": [],
        "ref_image_ids": [],
        "outline_hash": outline_hash,
        "original_hash": "",  # filled in below after we know payload's content hash
    }
    payload["original_hash"] = hash_concept_payload(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def is_concept_stale(path: Path, current_outline_hash: str) -> bool:
    """Decide whether to regenerate Stage 4 for a slide.

    Returns True (stale → regenerate) when:
      * file doesn't exist
      * file lacks an outline_hash
      * file's outline_hash doesn't match current outline content AND the
        file hasn't been edited by the user

    Returns False (fresh → reuse) when:
      * file's outline_hash matches the current outline, OR
      * file's concept hash drifted from `original_hash` (user-edited),
        in which case the user's edits are authoritative
    """
    if not path.is_file():
        return True
    payload = read_concept_file(path)
    if payload is None:
        return True
    if not payload.get("outline_hash"):
        return True
    user_edited = (
        payload.get("original_hash")
        and hash_concept_payload(payload) != payload["original_hash"]
    )
    if user_edited:
        return False  # user edits stick
    return payload["outline_hash"] != current_outline_hash


# ----------------------------- LLM call -----------------------------------


_PROMPT_TEMPLATE = """You are a creative director for a slide deck. For the slide \
beat below, output a structured JSON concept that a downstream image model \
will render. Return ONLY a single JSON object that matches the schema; no \
prose, no code fences.

Schema (required, all fields):
{{
  "subject": "what is literally rendered (concrete nouns + adjectives)",
  "composition": "where on the canvas, which third/diagonal/quadrant; \
explicitly mention which area is reserved for headline text",
  "metaphor": "one sentence: what the visual stands in for, conceptually",
  "mood": "emotional register (not visual style)",
  "foreground_elements": ["2-4 concrete visual objects"],
  "background_treatment": "one short clause about color/texture/gradient",
  "text_overlay_zone": {{"x": 0..1, "y": 0..1, "w": 0..1, "h": 0..1}}
}}

Hard constraints:
- The image model will render the slide's text (headline, subhead, body) \
inside the bitmap. Your composition decides where that text sits and how it \
relates to the visual. text_overlay_zone is the rectangle the image model \
should arrange so the slide's text reads cleanly inside it.
- The image model is locked to the deck's style preset. Do NOT describe \
visual style (palette, line weight, rendering medium); that's already \
handled. Mood and metaphor are yours; render style is not.
- text_overlay_zone uses normalized [0,1] coords with origin top-left. \
Reserve enough room for the headline + subhead the slide needs.
- foreground_elements must each be visually concrete (a thing the renderer \
can draw), not conceptual.
- The output must be valid JSON. No trailing commas, no comments, no markdown.

Beat role: {role}
Layout architype: {architype} — {architype_description}

Style preset: {style_preset}
Style anchor (the locked rendering description; do NOT repeat in your \
output): {style_anchor}

Slide content:
{slide_block}

Few-shot examples (study the LEVEL OF SPECIFICITY, not the surface details):
{examples}

Now produce the concept JSON for the slide above. Output JSON only."""


def build_prompt(
    *,
    slide_block: str,
    role: str,
    architype: str,
    architype_description: str,
    style_preset: str,
    style_anchor: str,
    examples_text: str,
) -> str:
    return _PROMPT_TEMPLATE.format(
        slide_block=slide_block.strip(),
        role=role or "content",
        architype=architype or "hero_with_bullets",
        architype_description=architype_description or "one focal visual + supporting bullets",
        style_preset=style_preset or "(unspecified)",
        style_anchor=style_anchor or "(unspecified)",
        examples=examples_text.strip(),
    )


# ----------------------------- validation ---------------------------------


def _strip_fences(text: str) -> str:
    """Strip a single ```json … ``` or ``` … ``` fence if present."""
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```\s*$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def parse_concept(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM's JSON response.

    Raises ConceptError on any schema violation.
    """
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConceptError(f"response is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ConceptError(f"response must be a JSON object, got {type(data).__name__}")

    # Tolerate the model wrapping the schema in {"concept": {...}}.
    if "concept" in data and isinstance(data["concept"], dict) and \
       not REQUIRED_CONCEPT_KEYS.issubset(data.keys()):
        data = data["concept"]

    missing = REQUIRED_CONCEPT_KEYS - set(data.keys())
    if missing:
        raise ConceptError(f"concept missing required keys: {sorted(missing)}")

    overlay = data.get("text_overlay_zone")
    if not isinstance(overlay, dict):
        raise ConceptError("text_overlay_zone must be an object")
    overlay_missing = REQUIRED_OVERLAY_KEYS - set(overlay.keys())
    if overlay_missing:
        raise ConceptError(f"text_overlay_zone missing keys: {sorted(overlay_missing)}")
    for k in REQUIRED_OVERLAY_KEYS:
        try:
            v = float(overlay[k])
        except (TypeError, ValueError) as e:
            raise ConceptError(f"text_overlay_zone.{k} must be numeric: {e}") from e
        if not (0.0 <= v <= 1.0):
            raise ConceptError(f"text_overlay_zone.{k}={v} not in [0,1]")
        overlay[k] = v

    fg = data.get("foreground_elements")
    if not isinstance(fg, list) or not fg:
        raise ConceptError("foreground_elements must be a non-empty list")
    data["foreground_elements"] = [str(x) for x in fg if str(x).strip()]

    for k in ("subject", "composition", "metaphor", "mood", "background_treatment"):
        v = data.get(k)
        if not isinstance(v, str) or not v.strip():
            raise ConceptError(f"{k} must be a non-empty string")
        data[k] = v.strip()

    return data


# ----------------------------- entry point --------------------------------


def generate_visual_concept(
    *,
    slide_block: str,
    role: str,
    architype: str,
    architype_description: str,
    style_preset: str,
    style_anchor: str,
    examples_text: str,
    chat_call,
    planning_model: str,
) -> ConceptResult:
    """Run Stage 4 for a single slide.

    `chat_call(messages, model, max_tokens) -> str` is supplied by the caller
    so this module stays decoupled from the Streamlit-side
    `chat_completion_openai_compatible` wrapper.
    """
    prompt = build_prompt(
        slide_block=slide_block,
        role=role,
        architype=architype,
        architype_description=architype_description,
        style_preset=style_preset,
        style_anchor=style_anchor,
        examples_text=examples_text,
    )
    messages = [{"role": "user", "content": prompt}]
    raw = chat_call(messages=messages, model=planning_model, max_tokens=2048)
    concept = parse_concept(raw)
    return ConceptResult(concept=concept, raw=raw)


# ----------------------------- style anchor -------------------------------
#
# Generated once per (style_spec, planning_model) pair. Cached on disk so the
# second run on the same preset is free.


_ANCHOR_PROMPT = """You are writing the locked rendering description that an \
image model will receive for every slide in a deck. The description must be \
ONE sentence under 30 words, in the style of a stock-image-prompt anchor:

  - state the rendering medium (illustration / sketch / vector / photo / etc.)
  - state the dominant palette
  - state the line/treatment quality (thin engineering line / bold brush / \
loose ink / flat geometric / etc.)
  - end with the negative cap: "no watermarks, no logos."

Do NOT describe individual slides. Do NOT include any per-slide content. \
Output one sentence; no quotes, no markdown.

Style spec:
{style_spec}"""


def build_anchor_prompt(style_spec: str) -> str:
    return _ANCHOR_PROMPT.format(style_spec=style_spec.strip())


def style_anchor_cache_key(style_spec: str, planning_model: str) -> str:
    h = hashlib.sha256(style_spec.encode("utf-8")).hexdigest()
    return f"{h}|{planning_model}"


def load_anchor_cache(deck_dir: Path) -> dict[str, str]:
    cache = deck_dir / ".style-anchor-cache.json"
    if not cache.is_file():
        return {}
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_anchor_cache(deck_dir: Path, cache: dict[str, str]) -> None:
    path = deck_dir / ".style-anchor-cache.json"
    try:
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to write anchor cache %s: %s", path, e)


def generate_style_anchor(
    *,
    style_spec: str,
    deck_dir: Path,
    planning_model: str,
    chat_call,
) -> str:
    """Return a one-sentence style anchor, hitting the on-disk cache when possible."""
    key = style_anchor_cache_key(style_spec, planning_model)
    cache = load_anchor_cache(deck_dir)
    cached = cache.get(key)
    if cached:
        return cached
    prompt = build_anchor_prompt(style_spec)
    messages = [{"role": "user", "content": prompt}]
    raw = chat_call(messages=messages, model=planning_model, max_tokens=200)
    anchor = raw.strip().strip("`\"' \n")
    # Normalise to a single line.
    anchor = " ".join(anchor.split())
    if not anchor:
        raise RuntimeError("style anchor LLM returned empty content")
    cache[key] = anchor
    save_anchor_cache(deck_dir, cache)
    return anchor


__all__ = [
    "CONCEPT_VERSION",
    "ConceptError",
    "ConceptResult",
    "build_anchor_prompt",
    "build_prompt",
    "generate_style_anchor",
    "generate_visual_concept",
    "hash_concept_payload",
    "hash_outline_block",
    "is_concept_stale",
    "load_anchor_cache",
    "parse_concept",
    "read_concept_file",
    "render_concept_prompt",
    "save_anchor_cache",
    "style_anchor_cache_key",
    "write_concept_file",
]


# ----------------------------- prompt rendering ---------------------------


def render_concept_prompt(*, concept_payload: dict[str, Any], style_anchor: str) -> str:
    """Template a concept JSON payload into a compact image-generation prompt.

    Targets ~120 words for the body so modern image models keep attention
    sharp. The output starts with a small YAML-style frontmatter block (so
    users can read slide identity at a glance) followed by the templated
    prompt body.

    The image model receives the slide's headline + subhead + body bullets
    explicitly so they're rendered inside the bitmap; downstream MinerU /
    `editable_pptx` then converts those bitmap text regions into native
    PowerPoint text frames.
    """
    concept = concept_payload.get("concept") or {}
    headline = (concept_payload.get("headline") or "").strip()
    subhead = (concept_payload.get("subhead") or "").strip()
    body_lines = concept_payload.get("body") or []
    if isinstance(body_lines, str):
        body_lines = [b.strip() for b in body_lines.splitlines() if b.strip()]
    overlay = concept.get("text_overlay_zone") or {}
    fg = concept.get("foreground_elements") or []
    fg_str = ", ".join(str(x) for x in fg if str(x).strip())
    extra_neg = concept_payload.get("negative_prompts_extra") or []
    extra_neg_str = ", ".join(str(x) for x in extra_neg if str(x).strip())

    overlay_clause = ""
    try:
        x = float(overlay.get("x", 0))
        y = float(overlay.get("y", 0))
        w = float(overlay.get("w", 0))
        h = float(overlay.get("h", 0))
        if w > 0 and h > 0:
            overlay_clause = (
                f" Place the slide's headline and supporting text inside "
                f"the area at ({x:.2f}, {y:.2f}) sized ({w:.2f}, {h:.2f})."
            )
    except (TypeError, ValueError):
        pass

    parts: list[str] = [
        style_anchor.strip(),
        "",
        f"Subject: {(concept.get('subject') or '').strip()}",
        f"Composition: {(concept.get('composition') or '').strip()}.{overlay_clause}",
        f"Mood: {(concept.get('mood') or '').strip()}.",
    ]
    if fg_str:
        parts.append(f"Foreground: {fg_str}.")
    bg = (concept.get("background_treatment") or "").strip()
    if bg:
        parts.append(f"Background: {bg}.")

    # Tell the image model exactly which words to render. The downstream
    # editable_pptx pipeline relies on the bitmap actually containing this
    # text so MinerU can convert it back into native text frames.
    text_lines: list[str] = []
    if headline:
        text_lines.append(f"  Headline (largest): {headline}")
    if subhead:
        text_lines.append(f"  Subhead (smaller, below headline): {subhead}")
    for i, b in enumerate(body_lines, start=1):
        text_lines.append(f"  Body {i}: {str(b).strip()}")
    if text_lines:
        parts.append(
            "Text to render inside the image (verbatim, spelled exactly as written):\n"
            + "\n".join(text_lines)
        )

    neg = "no watermarks, no logos, no slide numbers, no spelling errors in any rendered text"
    if extra_neg_str:
        neg = f"{neg}, {extra_neg_str}"
    parts.append(f"Negative: {neg}.")

    body = "\n".join(parts)

    header_lines = [
        "---",
        f"slide_id: {concept_payload.get('slide_id', '')}",
        f"slide_number: {concept_payload.get('slide_number', '')}",
        f"role: {concept_payload.get('role', '')}",
        f"architype: {concept_payload.get('architype', '')}",
        f"style_preset: {concept_payload.get('style_preset', '')}",
    ]
    if headline:
        header_lines.append(f"headline: {headline}")
    if subhead:
        header_lines.append(f"subhead: {subhead}")
    header_lines.append("---")
    return "\n".join(header_lines) + "\n\n" + body + "\n"
