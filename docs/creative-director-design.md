# Creative-Director Pipeline — Design (P5)

Status: design draft. No code yet. The agreement is to design the artifact format
and stage interfaces *before* implementing, so we don't build twice.

## Why this exists

The current pipeline conflates "what to show" with "how to render it." The
planning LLM emits an `outline.md` that contains both content (`KEY CONTENT:`)
and a freeform prose `VISUAL:` description, and that whole bundle is pasted
into the image prompt with the style instructions. The image model gets one
shot to invent composition, subject, metaphor, mood, and rendering — under
time pressure, with no intermediate review surface.

NotebookLM's slide pipeline gets a perceptible quality lift by inserting an
explicit **Stage 4 — visual concept** between the outline and the image
generation. A second LLM, given the beat content, the architype (layout
role), and the locked style preset, decides:

- **subject** — the literal thing to render
- **composition** — where it sits, how the canvas is split
- **metaphor** — what it's standing in for, conceptually
- **mood** — the emotional register
- **foreground / background elements** — what's near, what recedes
- **text overlay zone** — where the headline goes (so the layout reserves it)

The image model only renders. It doesn't decide.

That single change — separating "creative direction" from "rendering" — is
the highest-leverage step. Stages 1, 2, 3, 6 from the longer description can
all stub on existing skilldeck behavior without losing the lift.

User decision (this session): **scope = "design first, code later"**, and
**P4 (scene.json) is dropped** because P3 already fixed the duplicate
write / glob / cache / progress pain. Whatever per-slide artifact P5 needs,
we design here — there's no separate P4 artifact.

## Stage map (skilldeck-specific)

| Stage | Status today | Plan | Module |
|---|---|---|---|
| 1. Beat planning | Implicit in `outline.md` (slide blocks ≈ beats) | Keep `outline.md` as the beat list. Add optional `**Role**:` per slide so Stage 2 can act on it. | `streamlit_app.run_pipeline` (existing) |
| 2. Architype assignment | Implicit `Layout:` line in outline | Keep. Add a deterministic role→architype default table when `Layout:` is absent. | small helper in `skill/references/layouts.md` lookup |
| 3. Global style binding | Already works (17 presets + custom dimensions) | Keep. `<STYLE_INSTRUCTIONS>` block already serves as the "constraint package." Add a single `style_anchor` sentence per preset for Stage 5 to template. | `skill/references/styles/<preset>.md` |
| **4. Visual concept** | **Missing — this is the new stage** | **New `concept.py`. One LLM call per slide, returns structured concept JSON. Concept is written to `prompts/NN-slide-{slug}.concept.json` next to the existing `.md`.** | **new module** |
| 5. Image generation | Exists in `streamlit_app.generate_images_from_prompts` | Wrap. Compose the actual image prompt by templating the concept into the style anchor. The existing `prompts/NN-slide-*.md` becomes the *rendered* prompt; the `.concept.json` becomes the *editable* upstream. | `streamlit_app.generate_images_from_prompts` (light wrap) |
| 6. Critique | Missing | Defer. Behind `EDITABLE_PPTX_CRITIQUE=1` env, opt-in. Renders thumbnail grid + style preset to VLM, returns `{slide_index, issue, severity, suggested_fix}`. Acts only above a severity threshold. | new `critique.py` |

The split also matches your existing `<DESIGN_SPEC>` JSON block (which is
opt-in today and serves the export side of the pipeline). The `concept.json`
serves the *generation* side. They are different artifacts: `<DESIGN_SPEC>`
biases shape detection during PNG → PPTX reconstruction; `concept.json`
biases image generation in the first place.

## The concept artifact

This is the only new file format. It should be small, hand-editable, and
diffable.

`prompts/NN-slide-{slug}.concept.json`:

```json
{
  "slide_id": "03-slide-resilience",
  "slide_number": 3,
  "role": "claim",
  "architype": "metaphor_split",
  "style_preset": "bold-editorial",

  "concept": {
    "subject": "a chain of paper boats on a calm river, one boat slightly larger and brighter",
    "composition": "asymmetric left, right third reserved for headline + subhead",
    "metaphor": "individual links bearing collective weight",
    "mood": "calm, deliberate, optimistic",
    "foreground_elements": ["paper boats", "subtle ripples"],
    "background_treatment": "soft gradient sky, low saturation",
    "text_overlay_zone": {"x": 0.62, "y": 0.18, "w": 0.34, "h": 0.62}
  },

  "headline": "Resilience is plural",
  "subhead": "Strength comes from the chain, not the link.",

  "negative_prompts_extra": [],
  "ref_image_ids": []
}
```

Why these fields and not others:

- **`role`** stays as a free string from the outline (claim, definition,
  evidence, hook, payoff). Constrained enum is a Stage 2 concern; keep it
  loose at the artifact level so users can edit by hand.
- **`architype`** picks the layout (we have 24 in `skill/references/layouts.md`
  plus the chart templates). Drives image aspect ratio and the
  `text_overlay_zone` default.
- **`style_preset`** is the deck-level lock. Same value across every slide
  in the deck, written in by Stage 3.
- **`concept`** is the only block Stage 4 produces. Stage 5 templates this
  into the image prompt. This is the editable surface the user sees if they
  want to steer the deck without touching style.
- **`text_overlay_zone`** is in normalized 0..1 coords. The image prompt
  tells the image model to *leave that area visually quiet*, and the
  PPTX assembler later places the actual text there. We never bake text
  into the bitmap.
- **`negative_prompts_extra`** is per-slide, additive on top of the style
  preset's deck-level negatives ("no text, no watermarks, no faces, ...").
- **`ref_image_ids`** is for character/object continuity across slides:
  point to a previously generated slide's PNG to use as a reference image
  on backends that support it (`nano-banana-pro`, etc.). Empty by default.

What's deliberately NOT in this artifact:

- No style description (color hex, font hints) — that's `<STYLE_INSTRUCTIONS>`
  and lives in `outline.md`.
- No image API parameters (model, size, seed) — those live in
  `confirmation.yaml` so they're invariant per run.
- No layout hints for `editable_pptx` shape detection — that's `<DESIGN_SPEC>`
  and serves the reverse pipeline. Different audience.

## How Stage 4 actually runs

Inputs to the LLM call (one call per slide):

1. The slide's outline block (headline, subhead, body bullets, `// VISUAL`
   prose if present).
2. The architype name + a 1-line description from `layouts.md`.
3. The style preset spec (the entire `references/styles/<preset>.md`).
4. **Three or four few-shot examples** of (slide-block + architype + preset)
   → concept JSON. The few-shots are the entire ballgame for output quality.

Output: just the `concept` block above (no headline/subhead — those come
from outline.md and are passed through). The Python wrapper merges, validates
schema, writes the file.

Why few-shots are non-negotiable: without them, "subject" defaults to noun
phrases ("a businessman shaking hands"). With them, it lands on concepts
("two hands meeting in soft side-light, one warm, one cool, suggesting
partnership across difference"). The difference is the entire quality
gap between AI-slop and designed slides.

The few-shots ship in `skill/references/concept-examples.md`. Three
hand-written examples covering: a `claim` beat, a `data_point` beat,
a `hook` beat. Style preset varies across them so the model doesn't lock
onto one aesthetic.

## Image prompt template (Stage 5)

After Stage 4 writes `concept.json`, Stage 5 templates the actual prompt:

```
{style_anchor}

Subject: {concept.subject}
Composition: {concept.composition}. Reserve the area at
({text_zone.x}, {text_zone.y}) sized ({text_zone.w}, {text_zone.h})
visually quiet for headline placement.
Mood: {concept.mood}.
Foreground: {concept.foreground_elements joined}.
Background: {concept.background_treatment}.

Negative: {style_negative}, {concept.negative_prompts_extra joined}.
```

Constraint: total prompt under 80 words. We strip the existing `// VISUAL`
prose and `<STYLE_INSTRUCTIONS>` block from the prompt body — those were the
old way of saying the same thing, and concatenating them with the concept
just dilutes attention.

`style_anchor` is a single sentence per preset that I'll add to each
`references/styles/<preset>.md`, e.g.:

- `blueprint`: "Precise technical blueprint illustration on warm off-white,
  thin engineering line work, blue tones, no photographic elements."
- `bold-editorial`: "Magazine-grade editorial illustration with high
  contrast, vibrant accent colors, generous whitespace, no text in image."
- `sketch-notes`: "Loose hand-drawn sketch on warm cream paper, ink line
  with light watercolor wash, friendly imperfect strokes."

These are the same kind of one-liners the existing presets already imply;
extracting them as a named field just makes templating mechanical.

## Stage 6 (critique) — design only, ship behind a flag

After all images render (Stage 5 done), assemble a thumbnail grid PNG
(N slides as a single image, ~2-3 cols × ⌈N/3⌉ rows, each thumbnail
512×288), and call a VLM:

```
You are auditing a slide deck for visual coherence.
Style preset: <preset>.
Style spec: <one-paragraph from preset.md>.
Slides shown: 1..N, left-to-right, top-to-bottom.

Return JSON: {"deviations":[
  {"slide_index": int, "axis": "palette|composition|treatment|off-style",
   "severity": 1..5, "issue": str, "suggested_fix": str}
]}
```

Act only on `severity >= 3`. For each flagged slide, regenerate Stage 5 with
either (a) a tightened style preset injection, or (b) the `ref_image_ids`
field populated with the slide(s) the critique pointed at as the
"good" example.

Skip on first cut. Add `EDITABLE_PPTX_CRITIQUE=1` env to opt in. Cap on
regenerations (default 1 retry per flagged slide) to bound spend.

## Where it slots into the existing code

The structural change is: a new `concept.py` runs between the existing
"prompts written" stage and the existing "images generated" stage. The
existing `Stage` enum already has `Stage.PROMPTS` and `Stage.IMAGES` — we
add `Stage.CONCEPTS` between them. The existing progress bus and timeline
just gain one row.

```
SOURCE → OUTLINE → PROMPTS → CONCEPTS → CHARTS → IMAGES → PPTX → PDF
                              ^^^^^^^^
                              new
```

Cache key for the `concept.json` artifact uses the existing
`write_text_if_changed` helper — if the outline block + architype + preset
+ few-shot version are unchanged, no LLM call. Costs go to zero on reruns.

The image-prompt cache (`.imghash` sidecar from P1) keys on the *rendered*
prompt text, so a concept change → prompt change → cache miss → fresh
image. This is exactly what we want.

## What I need from you before I code

Three open decisions:

1. **Where does Stage 4 happen — main thread or worker thread?** It's an
   LLM call per slide; on a 14-slide deck that's 14 calls. Today
   `apply_openai_element_styles` already uses a `ThreadPoolExecutor` for its
   per-text-block local-color calls. We can do the same here: parallel
   across slides, each call serial within. Or run sequentially with
   progress events between. I'd default to parallel-across-slides under
   `EDITABLE_PPTX_CONCEPT_WORKERS` (default 4, same env-var pattern as
   the analysis workers).

2. **Where does the `style_anchor` sentence live?** Two options:
   (a) Add a new `## Style Anchor` section to each
   `references/styles/<preset>.md` and parse it out;
   (b) Generate it on the fly with an LLM at run start
   ("summarize this style spec in one sentence for an image-prompt anchor").
   Option (a) is deterministic and easier to debug but requires me to
   hand-write 17 anchors. Option (b) is one extra LLM call per run but
   handles custom dimensions for free. I'd pick (a) for the first 17
   presets and (b) as a fallback for `custom-dimensions`.

3. **Should `concept.json` be the user-editable surface?** Today users edit
   `outline.md` and re-run. With Stage 4, the natural editing surface
   shifts to the concept files: changing a single slide's metaphor doesn't
   require touching `outline.md`. The Streamlit UI's "Review prompts" step
   would need to surface `.concept.json` content alongside the prompt
   `.md`. That's a UI change, not a pipeline change — defer to a follow-up
   PR.

I'll wait for answers on (1) and (2) before writing code. (3) is a UI
follow-up that doesn't block the backend work.
