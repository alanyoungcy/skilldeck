__all__ = [
    "StyleExtraction",
    "NotebookLMInstructions",
    "get_chat_model",
    "run_step2_extract_style",
    "run_step3_generate_instructions",
]


def __getattr__(name: str):
    if name in {"StyleExtraction", "NotebookLMInstructions"}:
        from .models import NotebookLMInstructions, StyleExtraction

        return {"StyleExtraction": StyleExtraction, "NotebookLMInstructions": NotebookLMInstructions}[name]
    if name in {"run_step2_extract_style", "run_step3_generate_instructions"}:
        from .runner import run_step2_extract_style, run_step3_generate_instructions

        return {
            "run_step2_extract_style": run_step2_extract_style,
            "run_step3_generate_instructions": run_step3_generate_instructions,
        }[name]
    if name == "get_chat_model":
        from .llm import get_chat_model

        return get_chat_model
    raise AttributeError(name)
