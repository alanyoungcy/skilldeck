from __future__ import annotations

from pathlib import Path

from langchain_core.runnables import Runnable

from .models import NotebookLMInstructions, StyleExtraction
from .prompts import step2_agent_prompt, step2_prompt, step3_agent_prompt, step3_prompt
from .tools import build_tools


def _as_bullets(lines: list[str]) -> str:
    return "\n".join(f"- {x}" for x in lines)


def _extract_json_object(text: str) -> str:
    """
    Best-effort extraction of the first top-level JSON object in `text`.
    This protects agent-mode parsing if a model adds preface text or code fences.
    """
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        return t
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return t
    return t[start : end + 1]


def run_step2_extract_style(
    *,
    llm,
    skill_dir: Path,
    preset_name: str | None,
    preset_markdown_override: str | None,
    image_description: str | None,
    use_agent: bool,
    max_iterations: int,
) -> StyleExtraction:
    preset_markdown = ""
    if preset_markdown_override:
        preset_markdown = preset_markdown_override.strip()
    elif preset_name:
        from .refs import load_style_preset_text

        preset_markdown = load_style_preset_text(skill_dir, preset_name).strip()

    image_description = (image_description or "").strip()

    if not use_agent:
        chain: Runnable = step2_prompt() | llm.with_structured_output(StyleExtraction)
        return chain.invoke(
            {
                "preset_markdown": preset_markdown,
                "image_description": image_description,
            }
        )

    from langchain.agents import AgentExecutor, create_tool_calling_agent

    tools = build_tools(skill_dir)
    agent_prompt = step2_agent_prompt()
    agent = create_tool_calling_agent(llm, tools, agent_prompt)
    executor = AgentExecutor(agent=agent, tools=tools, max_iterations=max_iterations)

    raw = executor.invoke(
        {
            "preset_markdown": preset_markdown,
            "image_description": image_description,
        }
    )["output"]

    return StyleExtraction.model_validate_json(_extract_json_object(raw))


def run_step3_generate_instructions(
    *,
    llm,
    style: StyleExtraction,
    deck_context: str | None,
    use_agent: bool,
    max_iterations: int,
) -> NotebookLMInstructions:
    deck_context = (deck_context or "").strip()
    snippets = "\n".join(f"- {s}" for s in style.notebooklm_prompt_snippets)

    if not use_agent:
        chain: Runnable = step3_prompt() | llm.with_structured_output(NotebookLMInstructions)
        return chain.invoke(
            {
                "style_rules": _as_bullets(style.style_rules),
                "style_summary": style.style_summary,
                "snippets": snippets,
                "deck_context": deck_context,
            }
        )

    from langchain.agents import AgentExecutor, create_tool_calling_agent

    tools = []
    agent_prompt = step3_agent_prompt()
    agent = create_tool_calling_agent(llm, tools, agent_prompt)
    executor = AgentExecutor(agent=agent, tools=tools, max_iterations=max_iterations)

    raw = executor.invoke(
        {
            "style_rules": _as_bullets(style.style_rules),
            "style_summary": style.style_summary,
            "snippets": snippets,
            "deck_context": deck_context,
        }
    )["output"]

    return NotebookLMInstructions.model_validate_json(_extract_json_object(raw))

