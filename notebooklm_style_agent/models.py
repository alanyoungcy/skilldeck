from __future__ import annotations

from pydantic import BaseModel, Field


class StyleExtraction(BaseModel):
    """Output of Step 2 (style extraction)."""

    style_summary: str = Field(
        description="Short paragraph describing the style in plain language."
    )
    style_rules: list[str] = Field(
        description="Bullet rules that enforce consistent style across slides/pages."
    )
    color_palette: list[str] = Field(
        default_factory=list,
        description="Optional palette as hex codes or named colors (if known).",
    )
    typography_rules: list[str] = Field(
        default_factory=list, description="Optional typography rules."
    )
    layout_rules: list[str] = Field(
        default_factory=list, description="Optional layout/composition rules."
    )
    do_list: list[str] = Field(default_factory=list, description="Do list.")
    dont_list: list[str] = Field(default_factory=list, description="Don't list.")
    notebooklm_prompt_snippets: list[str] = Field(
        description="Short reusable prompt snippets to paste into NotebookLM."
    )


class NotebookLMInstructions(BaseModel):
    """Output of Step 3 (NotebookLM instructions)."""

    generation_instructions: str = Field(
        description="A single block of instructions to paste into NotebookLM."
    )
    fine_tune_checklist: list[str] = Field(
        description="Checklist for only fixing pages that break style consistency."
    )

