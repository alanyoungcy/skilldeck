from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from .refs import list_style_presets, load_style_preset_text


def build_tools(skill_dir: Path):
    @tool
    def list_available_style_presets() -> list[str]:
        """List built-in style preset names, including SVG layout-backed presets."""
        return [p.name for p in list_style_presets(skill_dir)]

    @tool
    def load_style_preset(preset_name: str) -> str:
        """Load a built-in style preset markdown by name (e.g. 'blueprint' or a layout pack)."""
        return load_style_preset_text(skill_dir, preset_name)

    return [list_available_style_presets, load_style_preset]
