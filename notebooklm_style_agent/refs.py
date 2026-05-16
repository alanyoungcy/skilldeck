from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised in lean Python envs
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class StylePreset:
    name: str
    path: Path
    kind: str = "markdown"
    summary: str = ""
    keywords: tuple[str, ...] = ()
    render_policy: str = ""
    layout_dir: Path | None = None
    svg_templates: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()

    @property
    def is_layout_template(self) -> bool:
        return self.kind == "layout_template"

    @property
    def label(self) -> str:
        if self.is_layout_template:
            return f"{self.name} · SVG layout pack"
        return self.name


def styles_dir(skill_dir: Path) -> Path:
    return skill_dir / "references" / "styles"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    data = _load_frontmatter(raw)
    if not isinstance(data, dict):
        return {}, text
    return data, body


def _load_frontmatter(raw: str) -> dict[str, Any]:
    if yaml is not None:
        data = yaml.safe_load(raw) or {}
        return data if isinstance(data, dict) else {}

    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(line[4:].strip().strip("'\""))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            data[key] = []
            current_key = key
        elif value == "":
            data[key] = []
            current_key = key
        else:
            data[key] = value.strip("'\"")
            current_key = key
    return data


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(x) for x in value if str(x).strip())
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if str(x).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _resolve_layout_dir(skill_dir: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    p = Path(value)
    if not p.is_absolute():
        p = skill_dir / p
    return p


def _preset_from_path(skill_dir: Path, p: Path) -> StylePreset:
    text = p.read_text(encoding="utf-8")
    meta, _body = _split_frontmatter(text)
    layout_dir = _resolve_layout_dir(skill_dir, meta.get("layout_dir"))
    return StylePreset(
        name=str(meta.get("preset_id") or p.stem),
        path=p,
        kind=str(meta.get("kind") or "markdown"),
        summary=str(meta.get("summary") or ""),
        keywords=_as_str_tuple(meta.get("keywords")),
        render_policy=str(meta.get("render_policy") or ""),
        layout_dir=layout_dir,
        svg_templates=_as_str_tuple(meta.get("svg_templates")),
        assets=_as_str_tuple(meta.get("assets")),
    )


def list_style_presets(skill_dir: Path) -> list[StylePreset]:
    sdir = styles_dir(skill_dir)
    if not sdir.exists():
        return []
    presets: list[StylePreset] = []
    for p in sorted(sdir.glob("*.md")):
        presets.append(_preset_from_path(skill_dir, p))
    return presets


def _svg_role(svg_name: str) -> str:
    stem = Path(svg_name).stem.lower()
    if "cover" in stem:
        return "cover"
    if "toc" in stem:
        return "toc"
    if "chapter" in stem:
        return "chapter"
    if "ending" in stem:
        return "ending"
    if "content" in stem:
        return "content"
    return "reference"


def _layout_guidance(preset: StylePreset) -> str:
    if not preset.is_layout_template:
        return ""
    role_lines: list[str] = []
    for svg in preset.svg_templates:
        exists = ""
        if preset.layout_dir is not None and not (preset.layout_dir / svg).exists():
            exists = " (missing; use markdown guidance only)"
        role_lines.append(f"- `{svg}`: {_svg_role(svg)} page reference{exists}")
    if not role_lines:
        role_lines.append("- No SVG roster was declared; use the markdown design spec only.")

    layout_dir = str(preset.layout_dir) if preset.layout_dir is not None else "(not declared)"
    assets = ", ".join(f"`{a}`" for a in preset.assets) if preset.assets else "none declared"
    return (
        "\n\n---\n\n"
        "## SVG Layout Guidance\n\n"
        "This preset is backed by SVG page templates. Use the templates as composition "
        "references for the image/chart prompts, but keep the current generation pipeline: "
        "do not edit or render these SVG templates directly.\n\n"
        f"- Layout directory: `{layout_dir}`\n"
        f"- Render policy: `{preset.render_policy or 'prompt_guidance'}`\n"
        f"- Assets: {assets}\n"
        "- Available page roles:\n"
        + "\n".join(role_lines)
        + "\n"
    )


def get_style_preset(skill_dir: Path, preset_name: str) -> StylePreset:
    for preset in list_style_presets(skill_dir):
        if preset.name == preset_name or preset.path.stem == preset_name:
            return preset
    raise FileNotFoundError(f"Unknown style preset: {preset_name}")


def load_style_preset_text(skill_dir: Path, preset_name: str) -> str:
    sdir = styles_dir(skill_dir)
    p = sdir / f"{preset_name}.md"
    preset = _preset_from_path(skill_dir, p) if p.exists() else get_style_preset(skill_dir, preset_name)
    text = preset.path.read_text(encoding="utf-8")
    _meta, body = _split_frontmatter(text)
    return body.strip() + _layout_guidance(preset)
