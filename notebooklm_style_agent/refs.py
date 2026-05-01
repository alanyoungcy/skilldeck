from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StylePreset:
    name: str
    path: Path


def styles_dir(skill_dir: Path) -> Path:
    return skill_dir / "references" / "styles"


def list_style_presets(skill_dir: Path) -> list[StylePreset]:
    sdir = styles_dir(skill_dir)
    if not sdir.exists():
        return []
    presets: list[StylePreset] = []
    for p in sorted(sdir.glob("*.md")):
        presets.append(StylePreset(name=p.stem, path=p))
    return presets


def load_style_preset_text(skill_dir: Path, preset_name: str) -> str:
    sdir = styles_dir(skill_dir)
    p = sdir / f"{preset_name}.md"
    if not p.exists():
        raise FileNotFoundError(f"Unknown style preset: {preset_name}")
    return p.read_text(encoding="utf-8")

