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

from notebooklm_style_agent.refs import list_style_presets, load_style_preset_text

REPO_DIR = Path(__file__).resolve().parent
SKILL_DIR = REPO_DIR / "baoyu-skills" / "skills" / "baoyu-slide-deck"
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


def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


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


def backup_if_exists(path: Path) -> None:
    if not path.exists():
        return
    ts = now_ts()
    backup = path.with_name(f"{path.stem}-backup-{ts}{path.suffix}")
    shutil.move(str(path), str(backup))


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def load_extend_md() -> tuple[Preferences, Path | None]:
    candidates = [
        REPO_DIR / ".baoyu-skills" / "baoyu-slide-deck" / "EXTEND.md",
        Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "baoyu-skills"
        / "baoyu-slide-deck"
        / "EXTEND.md",
        Path.home() / ".baoyu-skills" / "baoyu-slide-deck" / "EXTEND.md",
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
    import json as _json

    m = re.search(r"<DESIGN_SPEC>([\s\S]*?)</DESIGN_SPEC>", slide_block)
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


def write_prompt_files(*, deck_dir: Path, outline_md: str) -> None:
    style_block = parse_style_instructions(outline_md)
    slides_blocks = parse_slides(outline_md)
    if not style_block or not slides_blocks:
        raise RuntimeError("Could not parse outline.md (missing <STYLE_INSTRUCTIONS> or slide blocks).")

    base_prompt = read_ref_text("base-prompt.md")
    ensure_dir(deck_dir / "prompts")

    for sb in slides_blocks:
        m = re.search(r"^\*\*Filename\*\*:\s*(.+)$", sb, re.MULTILINE)
        filename = m.group(1).strip() if m else f"{now_ts()}-slide.png"
        stem = Path(filename).with_suffix("").name
        prompt_md_path = deck_dir / "prompts" / f"{stem}.md"
        backup_if_exists(prompt_md_path)
        prompt_body = (
            base_prompt.strip()
            + "\n\n---\n\n## STYLE_INSTRUCTIONS\n\n"
            + style_block
            + "\n\n---\n\n## SLIDE CONTENT\n\n"
            + sb.strip()
            + "\n"
        )
        prompt_md_path.write_text(prompt_body, encoding="utf-8")

        spec = _extract_design_spec(sb)
        if spec is not None:
            import json as _json

            spec_path = deck_dir / "prompts" / f"{stem}.spec.json"
            spec_path.write_text(_json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")


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
        if not re.match(r"^\d{2}-slide-.+\.(png|jpg|jpeg)$", fn, flags=re.IGNORECASE):
            return False, f"Slide {i} filename must look like `NN-slide-slug.png` (got `{fn}`)."

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
        cont = f"""You are continuing an existing `outline.md` for baoyu-slide-deck.

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


def generate_images_from_prompts(
    *,
    deck_dir: Path,
    image_base_url: str,
    image_api_key: str,
    image_model: str,
    image_size: str,
) -> None:
    prompts_dir = deck_dir / "prompts"
    prompt_files = sorted(prompts_dir.glob("*.md"))
    if not prompt_files:
        raise RuntimeError("No prompt files found.")

    total = len(prompt_files)
    for idx, pf in enumerate(prompt_files, start=1):
        prompt_text = pf.read_text(encoding="utf-8")
        png_name = Path(pf.name).with_suffix(".png").name
        out_path = deck_dir / png_name
        backup_if_exists(out_path)
        try:
            png_bytes = generate_image_openai_compatible(
                base_url=image_base_url,
                api_key=image_api_key,
                model=image_model,
                prompt=prompt_text,
                size=image_size,
            )
            png_bytes = normalize_generated_image_png(png_bytes, image_size)
            out_path.write_bytes(png_bytes)
            st.write(f"Generated {idx}/{total}: `{png_name}`")
        except Exception as e:
            raise RuntimeError(f"Image generation failed for `{pf.name}` → `{png_name}`: {e}") from e


def merge_deck(*, deck_dir: Path) -> tuple[str, str]:
    """Build editable PPTX via `python -m editable_pptx`, then optional PDF via bun script."""
    bun_x = resolve_bun_x()
    logs: list[str] = []
    err = ""

    if not os.getenv("MINERU_TOKEN", "").strip():
        logs.append(
            "editable_pptx: skipped — MINERU_TOKEN not set in `.env` "
            "(add it next to PLANNING_* / IMAGE_*; see `.env.example`)."
        )
        err = (
            "Editable PPTX was skipped: set **MINERU_TOKEN** in `.env`. "
            "PDF export still runs below if `bun` is available."
        )
    else:
        py = sys.executable
        r = subprocess.run(
            [py, "-m", "editable_pptx", str(deck_dir)],
            cwd=str(REPO_DIR),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        logs.append("editable_pptx:\n" + (r.stdout or "") + (r.stderr or ""))
        if r.returncode != 0:
            err = f"editable_pptx failed (exit {r.returncode}). Check log below; PDF may still have been built."

    if not bun_x:
        logs.append("merge-to-pdf: skipped (missing `bun` and `npx`)")
        return "\n\n".join(logs), err

    merge_pdf = SKILL_DIR / "scripts" / "merge-to-pdf.ts"
    if merge_pdf.exists():
        p2 = subprocess.run(bun_x + [str(merge_pdf), str(deck_dir)], capture_output=True, text=True)
        logs.append("merge-to-pdf:\n" + (p2.stdout or "") + (p2.stderr or ""))

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
        pngs = list(d.glob("*.png"))
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
) -> None:
    topic_slug = analysis["topic_slug"]
    deck_dir = get_session_deck_dir(topic_slug)
    ensure_dir(deck_dir)

    # Persist refs + confirmation every pipeline run (mirrors skill bookkeeping)
    ensure_dir(deck_dir / "refs")
    backup_if_exists(deck_dir / "confirmation.yaml")
    (deck_dir / "confirmation.yaml").write_text(
        yaml.safe_dump({"params": confirmed_params, "refs": ref_files_meta}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    # Step 3: outline
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
    prompt = f"""Generate `outline.md` for the `baoyu-slide-deck` skill.
Follow the Outline Template exactly. Include:
- Header metadata
- <STYLE_INSTRUCTIONS> block (single source of truth)
{slide_count_line}
- Audience={confirmed_params['audience']}
- Language={confirmed_params['language']} (auto => detected={analysis['detected_language']})

If preset is chosen, use the preset spec as authoritative. If custom dimensions, use:
{confirmed_params.get('dimensions')}

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
    backup_if_exists(deck_dir / "outline.md")
    (deck_dir / "outline.md").write_text(str(md), encoding="utf-8")

    # Step 5: prompts
    outline_md = (deck_dir / "outline.md").read_text(encoding="utf-8")
    write_prompt_files(deck_dir=deck_dir, outline_md=outline_md)

    # Step 7: images
    generate_images_from_prompts(
        deck_dir=deck_dir,
        image_base_url=image_base_url,
        image_api_key=image_api_key,
        image_model=image_model,
        image_size=image_size,
    )

    # Step 8: editable PPTX (MinerU) + optional PDF
    merge_log, merge_err = merge_deck(deck_dir=deck_dir)
    if merge_err:
        st.warning(merge_err)
    elif (deck_dir / f"{deck_dir.name}.pptx").is_file():
        st.success("Exported **editable** `.pptx` (open in PowerPoint to edit text).")
    if merge_log.strip():
        st.expander("Editable PPTX + PDF export log").code(merge_log, language="text")


# --- Streamlit UI ---

st.set_page_config(page_title="baoyu-slide-deck", layout="wide")
_dotenv_path = REPO_DIR / ".env"
load_dotenv_robust(_dotenv_path)

st.title("Slide Deck Generator")
st.caption(
    "Runs the `baoyu-slide-deck` flow end-to-end: analyze → confirm → outline → prompts → images → export. "
    "**PowerPoint** is an **editable** `.pptx` (MinerU layout + live text), not a flat slide-deck image export. "
    "Set **MINERU_TOKEN** in `.env`. Only edit **source** + **confirmation**; the rest runs automatically."
)

if not SKILL_DIR.exists():
    st.error(f"Missing skill directory: {SKILL_DIR}")
    st.stop()

cfg = load_app_config()
prefs, prefs_path = load_extend_md()

presets = list_style_presets(SKILL_DIR)
preset_names = [p.name for p in presets]
if not preset_names:
    st.error("No style presets found under `baoyu-slide-deck/references/styles/*.md`.")
    st.stop()

default_preset = _get(cfg, "inputs.default_style_preset", prefs.style or preset_names[0])
if default_preset not in preset_names:
    default_preset = preset_names[0]

planning_base_url = env_default("PLANNING_BASE_URL").strip()
planning_api_key = env_default("PLANNING_API_KEY").strip()
planning_model = env_default("PLANNING_MODEL").strip()
image_base_url = env_default("IMAGE_BASE_URL").strip()
image_api_key = env_default("IMAGE_API_KEY").strip()
image_model = env_default("IMAGE_MODEL").strip()
planning_max_tokens = int(env_default("PLANNING_MAX_TOKENS", "8000") or "8000")
image_size = normalize_image_size(env_default("IMAGE_SIZE", "1920x1080"))

histories = list_deck_history()
_HISTORY_CURRENT = "__current__"

with st.sidebar:
    if prefs_path:
        st.caption(f"EXTEND.md: `{prefs_path}`")
        st.divider()
    st.subheader("Deck history")
    if histories:
        preview_options = [_HISTORY_CURRENT] + [h["slug"] for h in histories]
        preview_pick = st.selectbox(
            "Preview outputs from",
            options=preview_options,
            format_func=lambda s: "Current session (source below)"
            if s == _HISTORY_CURRENT
            else format_deck_history_row(histories, s),
            key="deck_history_pick",
        )
        st.session_state["_preview_deck_slug"] = None if preview_pick == _HISTORY_CURRENT else preview_pick
    else:
        st.caption("No decks in `slide-deck/` yet.")
        st.session_state["_preview_deck_slug"] = None

missing_planning = not (planning_base_url and planning_api_key and planning_model)
missing_image = not (image_base_url and image_api_key and image_model)
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
    if not image_model:
        missing.append("IMAGE_MODEL")

    st.error("Missing required `.env` variables: " + ", ".join(missing))
    st.caption(f"Expected file: `{_dotenv_path}` (exists: `{_dotenv_path.exists()}`)")
    if _dotenv_path.exists():
        # Show whether `.env` lines look blank without printing secrets.
        env_text = _dotenv_path.read_text(encoding="utf-8", errors="ignore")
        blank_keys: list[str] = []
        for k in missing:
            m = re.search(rf"^{re.escape(k)}\\s*=\\s*(.*)$", env_text, flags=re.MULTILINE)
            if m is not None and m.group(1).strip() == "":
                blank_keys.append(k)
        if blank_keys:
            st.warning(
                "Your `.env` file contains blank values for: " + ", ".join(blank_keys) + ". Fill them and restart Streamlit."
            )
    st.info(
        "Tip: if you export empty `PLANNING_*` / `IMAGE_*` in your shell, they can hide `.env` values. "
        "This app loads `.env` with **override=True** — restart Streamlit after saving `.env`."
    )
    st.stop()

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1) Source content")
    source_text = st.text_area("Paste your source content", height=360, key="source_text")
    topic_hint = st.text_input("Topic (optional, improves slug)", key="topic_hint")
    source_pdf = st.file_uploader(
        "Or upload a PDF (text is extracted and combined with the box above)",
        type=["pdf"],
        key="source_pdf",
    )
    pdf_extracted = ""
    if source_pdf is not None:
        try:
            pdf_extracted = extract_pdf_text(source_pdf.getvalue())
            st.caption(f"PDF: extracted **{len(pdf_extracted):,}** characters from `{source_pdf.name}`.")
        except Exception as e:
            st.error(f"Could not read this PDF: {e}")

combined_source = "\n\n".join(x for x in (source_text.strip(), pdf_extracted.strip()) if x).strip()

with col_right:
    st.subheader("2) Confirmation (required)")
    st.caption("Hard gate from `baoyu-slide-deck`: Step 3+ runs only after these choices are set (auto-saved every run).")

    if not combined_source.strip():
        st.info("Paste source content or upload a PDF on the left to start.")
        st.stop()

    words = len(re.findall(r"\w+", combined_source))
    detected_language = detect_language(combined_source)
    recommended_style = recommend_style_preset(combined_source)
    recommended_slides = recommend_slide_count(words)
    slug_base = topic_hint.strip() or (combined_source.strip().splitlines()[0][:80] if combined_source.strip() else "deck")
    topic_slug = slugify(slug_base)

    analysis = {
        "words": words,
        "detected_language": detected_language,
        "recommended_style": recommended_style,
        "recommended_slides": recommended_slides,
        "topic_slug": topic_slug,
    }

    st.markdown(
        f"- Detected language: **{detected_language}**\n"
        f"- Recommended style: **{recommended_style}**\n"
        f"- Recommended slides: **{recommended_slides}**"
    )

    style_choice = st.selectbox(
        "Style (`--style`)",
        options=preset_names + ["custom-dimensions"],
        index=(preset_names.index(recommended_style) if recommended_style in preset_names else preset_names.index(default_preset)),
        key="style_choice",
    )

    audience_options = ["beginners", "intermediate", "experts", "executives", "general"]
    audience_index = audience_options.index(prefs.audience) if prefs.audience in audience_options else 4
    audience = st.selectbox("Audience (`--audience`)", audience_options, index=audience_index, key="audience")

    lang_options = ["auto", "en", "zh", "ja"]
    lang_index = lang_options.index(prefs.language) if prefs.language in lang_options else 0
    lang = st.selectbox("Language (`--lang`)", lang_options, index=lang_index, key="lang")

    slides = st.number_input(
        "Slides (`--slides`)",
        min_value=1,
        max_value=30,
        value=max(1, min(30, int(recommended_slides))),
        step=1,
        key="slides",
    )

    dims = None
    if style_choice == "custom-dimensions":
        st.markdown("Custom dimensions (Round 2)")
        texture = st.selectbox("Texture", ["clean", "grid", "organic", "pixel", "paper"], key="dim_texture")
        mood = st.selectbox(
            "Mood",
            ["professional", "warm", "cool", "vibrant", "dark", "neutral", "macaron"],
            key="dim_mood",
        )
        typography = st.selectbox(
            "Typography",
            ["geometric", "humanist", "handwritten", "editorial", "technical"],
            key="dim_typography",
        )
        density = st.selectbox("Density", ["minimal", "balanced", "dense"], index=1, key="dim_density")
        dims = {"texture": texture, "mood": mood, "typography": typography, "density": density}

    st.markdown("Reference images (`--ref`) (optional)")
    ref_files = st.file_uploader(
        "Ref images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="ref_files",
    )
    ref_usage = st.selectbox("Ref usage mode", options=["direct", "style", "palette"], index=0, key="ref_usage")

    st.markdown("Image size (must be divisible by 16)")
    aspect = st.selectbox("Aspect ratio", options=["16:9", "4:3", "custom"], index=0, key="img_aspect")
    snap_mode = st.selectbox(
        "Divisible-by-16 rounding",
        options=["nearest", "down", "up"],
        index=0,
        key="img_snap",
        help="Your image backend requires both width and height divisible by 16.",
    )
    target_width = st.number_input("Target width (px)", min_value=256, max_value=4096, value=1920, step=16, key="img_w")
    target_height = st.number_input(
        "Target height (px) (custom only)",
        min_value=256,
        max_value=4096,
        value=1080,
        step=16,
        key="img_h",
        disabled=(aspect != "custom"),
    )
    computed_size = compute_image_size(
        aspect=aspect,
        target_width=int(target_width),
        target_height=int(target_height),
        snap_mode=snap_mode,
    )
    st.info(f"Will use image size: **{computed_size}**")

    confirm_run = st.button("Confirm & Run Step 3+", type="primary", key="confirm_run")

# Auto mode: skip human “review outline/prompts” pauses (skill allows explicit opt-out; UI automates)
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
}

deck_dir = get_session_deck_dir(topic_slug)
ensure_dir(deck_dir)
backup_if_exists(deck_dir / f"source-{topic_slug}.md")
(deck_dir / f"source-{topic_slug}.md").write_text(combined_source, encoding="utf-8")
backup_if_exists(deck_dir / "analysis.md")
(deck_dir / "analysis.md").write_text(
    yaml.safe_dump(analysis, sort_keys=False, allow_unicode=True),
    encoding="utf-8",
)

refs_meta: list[dict[str, str]] = []
if ref_files:
    ensure_dir(deck_dir / "refs")
    for i, f in enumerate(ref_files, start=1):
        ext = Path(f.name).suffix.lower() or ".png"
        dest = deck_dir / "refs" / f"{i:02d}-ref-{slugify(Path(f.name).stem)}{ext}"
        backup_if_exists(dest)
        dest.write_bytes(f.getvalue())
        refs_meta.append({"ref_id": f"{i:02d}", "filename": dest.name, "usage": ref_usage})

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
    "image_size": confirmed_params.get("image_size") or image_size,
    "planning_max_tokens": planning_max_tokens,
}
sig = stable_hash(sig_obj)

if "last_pipeline_sig" not in st.session_state:
    st.session_state.last_pipeline_sig = ""
if "approved_sig" not in st.session_state:
    st.session_state.approved_sig = ""

if confirm_run:
    st.session_state.approved_sig = sig
    # force a run even if previously done with same inputs
    st.session_state.last_pipeline_sig = ""

if st.session_state.approved_sig != sig:
    st.warning("Waiting for confirmation. Click **Confirm & Run Step 3+** to proceed.")
elif sig != st.session_state.last_pipeline_sig:
    try:
        with st.status("Running baoyu-slide-deck pipeline…", expanded=True) as status:
            status.write("Step 3: generating outline…")
            run_pipeline(
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
                image_size=confirmed_params.get("image_size") or image_size,
                preset_names=preset_names,
            )
            status.write("Done.")
        st.session_state.last_pipeline_sig = sig
    except Exception as e:
        st.error(str(e))
        st.stop()

st.divider()
st.subheader("Output")

preview_slug = st.session_state.get("_preview_deck_slug")
if preview_slug:
    st.info(f"Showing files from **{preview_slug}** (sidebar “Deck history”). Current session topic is **{topic_slug}**.")
    out_slug = preview_slug
    output_deck_dir = DECKS_DIR / preview_slug
else:
    out_slug = topic_slug
    output_deck_dir = deck_dir

pptx_path = output_deck_dir / f"{out_slug}.pptx"
pdf_path = output_deck_dir / f"{out_slug}.pdf"

slide_pngs_for_export = sorted(output_deck_dir.glob("*-slide-*.png"))
if slide_pngs_for_export:
    export_help = (
        "Runs `python -m editable_pptx` and PDF merge only — no outline, prompts, or images regenerated. "
        "Use after fixing `.env` (e.g. MINERU_TOKEN) or installing `img2pdf`."
    )
    if st.button("Re-run export only (editable PPTX + PDF)", help=export_help, key=f"retry_export_{out_slug}"):
        with st.status("Re-running export…", expanded=True) as export_status:
            export_status.write("Starting editable PPTX and PDF merge…")
            retry_log, retry_err = merge_deck(deck_dir=output_deck_dir)
            export_status.code(retry_log or "(no log)", language="text")
        if retry_err:
            st.warning(retry_err)
        elif pptx_path.exists():
            st.success("Export finished — editable PPTX updated.")
        st.rerun()

images = sorted(output_deck_dir.glob("*.png"))
if images:
    st.markdown("#### Slide previews (PNG)")
    st.image([str(p) for p in images], width=420)

if pptx_path.exists():
    st.markdown("#### PowerPoint (editable)")
    st.caption(
        "Text and layout come from MinerU + `editable_pptx`; open in PowerPoint / Keynote / LibreOffice to edit."
    )
    pptx_bytes = pptx_path.read_bytes()
    st.download_button(
        "Download editable PPTX",
        data=pptx_bytes,
        file_name=pptx_path.name,
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    viewer = f"https://view.officeapps.live.com/op/embed.aspx?src={urllib.parse.quote(str(pptx_path.resolve().as_uri()))}"
    st.caption(
        "Embedded preview uses Microsoft’s viewer and usually **does not work for local `file://` URLs**. "
        "Download the file or use the PDF preview below when available."
    )
    st.iframe(viewer, height=720)
else:
    st.warning(
        f"No PPTX at `{pptx_path}` yet. If you ran the pipeline, check **MINERU_TOKEN** in `.env` and the "
        f"**Editable PPTX + PDF export log** expander above. Output name must match folder name `{out_slug}.pptx`."
    )

if pdf_path.exists():
    st.markdown("#### PDF")
    pdf_bytes = pdf_path.read_bytes()
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
    )
    try:
        st.pdf(pdf_bytes, height=720)
    except Exception as e:
        st.warning(f"Inline PDF viewer unavailable ({e}). Install with: `pip install 'streamlit[pdf]'` and restart.")
        if len(pdf_bytes) <= 2_000_000:
            b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="720" type="application/pdf"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("PDF is large; use **Download PDF** above for a reliable view.")
