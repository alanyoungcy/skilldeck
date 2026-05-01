# LangChain + Streamlit: NotebookLM Style Agent

This is a small Streamlit app that implements a 3-step workflow for keeping **consistent style** when generating slide decks with NotebookLM:

- Step 1: Pick a reference image (or choose a built-in style preset from `baoyu-slide-deck`)
- Step 2: Use an LLM to extract style rules + produce NotebookLM-ready prompt snippets
- Step 3: Generate NotebookLM instructions that explicitly include **“consistent style throughout”**, plus guidance for fine-tuning inconsistent pages

## Install (use your current conda env)

From repo root:

```bash
python -m pip install -r requirements.txt
```

You also need an API key for your chosen provider:

- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`

## Run

```bash
streamlit run streamlit_app.py
```

## .env (two endpoints)

Create/edit `.env` in repo root:

- Planning (LLM chat): `PLANNING_BASE_URL`, `PLANNING_API_KEY`, `PLANNING_MODEL`
- Image generation: `IMAGE_BASE_URL`, `IMAGE_API_KEY`, `IMAGE_MODEL`

## Notes

- This app **reuses the style presets + framework docs** under `baoyu-skills/skills/baoyu-slide-deck/references/`.
- You can optionally create `app_config.yaml` (see `app_config.example.yaml`) to set defaults.

