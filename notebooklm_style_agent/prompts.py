from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


STEP2_SYSTEM = """You are a design style analyst.
Your job: infer stylistic rules that can be reused to keep a slide deck visually consistent.
Be concrete and enforceable: typography, palette, layout rhythm, icon/illustration style, borders, spacing, density, tone.
If the user provides a style preset markdown, treat it as the authoritative style spec.
If an image is provided but you cannot view it, fall back to the user’s description and the preset.
Output must be consistent, reusable, and suitable for NotebookLM instructions.

IMPORTANT OUTPUT RULE:
- Return ONLY valid JSON (no markdown fences, no extra text) that matches the requested schema exactly."""


def step2_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", STEP2_SYSTEM),
            (
                "human",
                """Reference style preset (optional):
{preset_markdown}

User's reference-image description (optional):
{image_description}

Goal:
- Extract stylistic rules and translate them into NotebookLM-ready prompt snippets.
- Ensure the rules can drive "consistent style throughout" across all pages.

Return the final result using the requested structured schema.""",
            ),
        ]
    )


def step2_agent_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", STEP2_SYSTEM),
            (
                "human",
                """Reference style preset (optional):
{preset_markdown}

User's reference-image description (optional):
{image_description}

If you need built-in style presets, use tools to list/load them.

Goal:
- Extract stylistic rules and translate them into NotebookLM-ready prompt snippets.
- Ensure the rules can drive "consistent style throughout" across all pages.

Return ONLY valid JSON matching the schema.""",
            ),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


STEP3_SYSTEM = """You write concise, explicit NotebookLM generation instructions.
You must explicitly include the phrase: "consistent style throughout".
You must also provide a short fine-tuning checklist that only changes pages that break consistency (do not rewrite everything).

IMPORTANT OUTPUT RULE:
- Return ONLY valid JSON (no markdown fences, no extra text) that matches the requested schema exactly."""


def step3_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", STEP3_SYSTEM),
            (
                "human",
                """Style rules (authoritative):
{style_rules}

Style summary:
{style_summary}

NotebookLM prompt snippets:
{snippets}

User's deck topic/context (optional):
{deck_context}

Generate:
1) A single instruction block to paste into NotebookLM.
2) A fine-tuning checklist focusing only on inconsistent pages.

Return the final result using the requested structured schema.""",
            ),
        ]
    )


def step3_agent_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", STEP3_SYSTEM),
            (
                "human",
                """Style rules (authoritative):
{style_rules}

Style summary:
{style_summary}

NotebookLM prompt snippets:
{snippets}

User's deck topic/context (optional):
{deck_context}

Return ONLY valid JSON matching the schema.""",
            ),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

