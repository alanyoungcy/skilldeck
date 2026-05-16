#!/usr/bin/env python3
"""Generate style preset markdown files from SVG layout template folders.

The migration is intentionally metadata-only: generated presets point back to
the SVG folders and tell the deck pipeline to use them as composition guidance.
They do not switch rendering to native template editing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

GENERATED_MARKER = "<!-- generated-by: migrate_layout_templates.py -->"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _clean_md(text: str, max_chars: int = 1800) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit("\n", 1)[0].strip()
    return cut + "\n\n..."


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\b[\s\S]*?(?=^##\s+|\Z)"
    m = re.search(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    return m.group(0).strip() if m else ""


def _extract_title(spec_text: str, layout_id: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", spec_text, flags=re.MULTILINE)
    return m.group(1).strip() if m else layout_id


def _extract_quote_summary(spec_text: str) -> str:
    m = re.search(r"^>\s*(.+?)\s*$", spec_text, flags=re.MULTILINE)
    return m.group(1).strip() if m else ""


def _load_index(layouts_dir: Path) -> dict[str, Any]:
    index_path = layouts_dir / "layouts_index.json"
    if not index_path.exists():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _quote_yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dump_frontmatter(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {_quote_yaml_scalar(str(item))}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {_quote_yaml_scalar(str(value))}")
    return "\n".join(lines) + "\n"


def _target_path(styles_dir: Path, layout_id: str, *, force: bool) -> tuple[Path, bool]:
    primary = styles_dir / f"{layout_id}.md"
    if not primary.exists():
        return primary, False
    if force or GENERATED_MARKER in primary.read_text(encoding="utf-8", errors="ignore"):
        return primary, True
    fallback = styles_dir / f"{layout_id}-template.md"
    if not fallback.exists():
        return fallback, False
    if force or GENERATED_MARKER in fallback.read_text(encoding="utf-8", errors="ignore"):
        return fallback, True
    return fallback, False


def build_style_markdown(
    *,
    skill_dir: Path,
    layout_dir: Path,
    layout_id: str,
    index_entry: dict[str, Any],
    preset_id: str,
) -> str:
    spec_path = layout_dir / "design_spec.md"
    spec_text = spec_path.read_text(encoding="utf-8")
    title = _extract_title(spec_text, layout_id)
    summary = str(index_entry.get("summary") or _extract_quote_summary(spec_text) or title)
    keywords = index_entry.get("keywords") if isinstance(index_entry.get("keywords"), list) else []
    svg_templates = sorted(p.name for p in layout_dir.glob("*.svg"))
    assets = sorted(
        p.name
        for p in layout_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and p.suffix.lower() != ".svg"
    )

    rel_layout = layout_dir.relative_to(skill_dir).as_posix()
    frontmatter = {
        "preset_id": preset_id,
        "kind": "layout_template",
        "layout_dir": rel_layout,
        "svg_templates": svg_templates,
        "assets": assets,
        "summary": summary,
        "keywords": [str(x) for x in keywords],
        "render_policy": "prompt_guidance",
    }

    overview = _extract_section(spec_text, "I. Template Overview") or _extract_section(spec_text, "Template Overview")
    colors = _extract_section(spec_text, "III. Color Scheme") or _extract_section(spec_text, "Color Scheme")
    typography = _extract_section(spec_text, "IV. Typography System") or _extract_section(spec_text, "Typography System")
    layout = (
        _extract_section(spec_text, "V. Page Structure")
        or _extract_section(spec_text, "VI. Page Structure")
        or _extract_section(spec_text, "Page Structure")
    )
    page_types = _extract_section(spec_text, "VI. Page Types") or _extract_section(spec_text, "Page Types")

    svg_lines = "\n".join(f"- `{name}`" for name in svg_templates) or "- None declared"
    asset_lines = "\n".join(f"- `{name}`" for name in assets) or "- None declared"
    keyword_text = ", ".join(str(x) for x in keywords) if keywords else "None declared"

    return (
        "---\n"
        + _dump_frontmatter(frontmatter)
        + "---\n"
        + f"{GENERATED_MARKER}\n\n"
        + f"# {preset_id}\n\n"
        + f"{summary}\n\n"
        + "## Template Source\n\n"
        + f"- Source layout: `{rel_layout}`\n"
        + "- Render policy: `prompt_guidance`\n"
        + "- Use these SVG files as composition references; do not require native SVG rendering.\n"
        + f"- Keywords: {keyword_text}\n\n"
        + "## Best For\n\n"
        + f"{summary}\n\n"
        + "## SVG Template Roster\n\n"
        + f"{svg_lines}\n\n"
        + "## Template Assets\n\n"
        + f"{asset_lines}\n\n"
        + "## Design Aesthetic\n\n"
        + f"{_clean_md(overview) if overview else _clean_md(_extract_quote_summary(spec_text) or summary)}\n\n"
        + "## Color Palette\n\n"
        + f"{_clean_md(colors) if colors else 'Use the colors defined in the source design specification.'}\n\n"
        + "## Typography\n\n"
        + f"{_clean_md(typography) if typography else 'Use the typography system defined in the source design specification.'}\n\n"
        + "## Layout Principles\n\n"
        + f"{_clean_md(layout) if layout else 'Follow the source template spacing, hierarchy, and structural page patterns.'}\n\n"
        + "## Page Roles\n\n"
        + f"{_clean_md(page_types) if page_types else 'Use cover, chapter, content, and ending SVGs as role-specific composition references.'}\n\n"
        + "## Style Rules\n\n"
        + "### Do\n\n"
        + "- Treat the markdown design spec as authoritative style guidance.\n"
        + "- Use the SVG roster to infer cover, section, content, and ending composition patterns.\n"
        + "- Keep generated image/chart slides compatible with the current skilldeck pipeline.\n\n"
        + "### Don't\n\n"
        + "- Do not edit, render, or require the SVG templates during this metadata-bridge phase.\n"
        + "- Do not override source content just to match a template placeholder.\n"
    )


def migrate(*, skill_dir: Path, force: bool = False, only: set[str] | None = None) -> list[str]:
    layouts_dir = skill_dir / "templates" / "layouts"
    styles_dir = skill_dir / "references" / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)
    index = _load_index(layouts_dir)
    messages: list[str] = []

    for layout_dir in sorted(p for p in layouts_dir.iterdir() if p.is_dir()):
        layout_id = layout_dir.name
        if only and layout_id not in only:
            continue
        spec_path = layout_dir / "design_spec.md"
        if not spec_path.exists():
            messages.append(f"SKIP {layout_id}: missing design_spec.md")
            continue
        target, can_overwrite = _target_path(styles_dir, layout_id, force=force)
        if target.exists() and not can_overwrite:
            messages.append(f"CONFLICT {layout_id}: {target.relative_to(skill_dir)} exists; not overwriting")
            continue
        preset_id = target.stem
        md = build_style_markdown(
            skill_dir=skill_dir,
            layout_dir=layout_dir,
            layout_id=layout_id,
            index_entry=index.get(layout_id, {}) if isinstance(index.get(layout_id), dict) else {},
            preset_id=preset_id,
        )
        target.write_text(md, encoding="utf-8")
        action = "UPDATE" if can_overwrite and target.exists() else "CREATE"
        messages.append(f"{action} {layout_id}: {target.relative_to(skill_dir)}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", type=Path, default=repo_root() / "skill")
    parser.add_argument("--force", action="store_true", help="Overwrite non-generated target files.")
    parser.add_argument("--only", nargs="*", help="Only migrate these layout ids.")
    args = parser.parse_args()

    messages = migrate(skill_dir=args.skill_dir.resolve(), force=args.force, only=set(args.only or []) or None)
    for msg in messages:
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
