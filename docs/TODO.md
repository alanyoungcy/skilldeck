# skilldeck — TODO

Status as of 2026-05-16. Source of truth for "what's left." Ordered roughly
by priority. Items in **Plan** describe non-trivial work that should be
designed before code; items in **Task** are small enough to ship directly.
Items in **Decision needed** are blocked on a user choice.

Mirrored as runtime tasks where useful — see `TaskList` for the live view.

---

## Open items

### P6 — Per-stage review gates *(highest priority)*

**What.** Three optional pauses in the pipeline so the user can inspect
artifacts before committing to slow downstream work:

- **Outline gate** — review `outline.md` after the planning LLM writes it.
- **Concepts gate** — review every `prompts/NN-slide-*.concept.json` after
  Stage 4 generates them.
- **Prompts gate** — review every `prompts/NN-slide-*.md` after the
  templated image prompt is built.

All gates default OFF so the existing fast path is preserved. Toggled via
three checkboxes in the Configure column.

**Why now.** Each gate corresponds to a structurally different artifact:

| Gate | Reviews | Why pause here |
|---|---|---|
| Outline | slide list, headlines, body bullets, layouts, chart specs | Model sometimes mis-counts slides, picks wrong layouts, paraphrases poorly. Cheap to fix here, expensive to fix downstream. |
| Concepts | visual subject, composition, metaphor, mood per slide | Where creative direction lives. A generic concept produces a generic image no matter how well downstream runs. Editing here is ~free; regenerating after image gen costs an API call per slide. |
| Prompts | the templated image-generation prompt | Final sanity check before the slowest stage. Most users leave it; power users tweak negatives or composition wording. |

**Mechanism.** Pipeline runs in a daemon thread already (Phase 2). At each
gate, the worker calls `bus.request_gate(stage)`, which sets the stage to
`awaiting_review` and blocks on a `threading.Event`. The autorefreshing UI
notices the state, shows a card with the artifact + three buttons:
"Continue", "Regenerate this stage", "I edited on disk — click when
ready". Each button calls `bus.release_gate(stage, action)` to unblock the
worker.

**Open decisions before code:**

1. **Inline edit or external edit?** Should the UI show editable
   `st.text_area`s with a "save & continue" button, or just render the
   artifact and require external editing? Default: render-only +
   external editing (simpler; user-edit detection is already wired via
   content-aware writes).
2. **Per-slide pagination for the concepts/prompts gate?** Show all N at
   once (long scroll) or paginate? Default: all-at-once; N is typically
   5–14.
3. **What does "Regenerate" mean?**
   - Outline: re-run planning LLM with same source.
   - Concepts: re-run Stage 4 for ALL slides (default) or only flagged
     slides (cheaper, more UI).
   - Prompts: re-template from concepts (deterministic, no LLM call).

**Tasks** (`#24`–`#29` in `TaskList`):

- [ ] **P6.1** — Three review checkboxes in the Configure column,
      replacing the hardcoded `False`s. Persist into `confirmed_params`.
- [ ] **P6.2** — `ProgressBus.request_gate(stage)`,
      `release_gate(stage, action)`, `awaiting_review` `StageState`. Add
      `state_class` mapping (yellow dot) in `_render_pipeline_timeline`.
- [ ] **P6.3** — Wire gate calls into `run_pipeline` after `Stage.OUTLINE`,
      `Stage.CONCEPTS`, and `Stage.PROMPTS`, gated by the corresponding
      `confirmed_params` flag. *Blocked by P6.2.*
- [ ] **P6.4** — UI gate card: render artifact, three buttons.
      *Blocked by P6.2.* Naturally subsumes the
      "expose `concept.json` for editing" follow-up since the concepts
      gate IS the editing surface.
- [ ] **P6.5** — Regenerate handlers per stage. For concepts, blow away
      existing `prompts/*.concept.json` so the staleness check forces
      regen. *Blocked by P6.3 + P6.4.*
- [ ] **P6.6** — Tests covering: gate triggers when flag set, doesn't
      trigger when flag unset, "Continue" releases without re-running,
      "Regenerate" loops the stage and re-arms the gate, user disk-edit
      between gate-open and continue is preserved. *Blocked by P6.5.*

---

### P5-fix-B — Forward text overlay from `concept.json` into PPTX

**What.** P5 Fix A unblocked the empty-text bug by re-allowing text in
the rendered image (image model renders headlines/bullets verbatim,
MinerU detects them, `editable_pptx` paints native text frames as
before). Fix B is the proper end-state from the original P5 design:
image stays textless, but the PPTX assembler reads the matching
`concept.json` and paints the headline / subhead / body bullets as
native text frames at the `text_overlay_zone` coords directly. Perfect
alignment with no MinerU OCR variance, guaranteed text-matches-`outline.md`.

**Why opt-in.** The current Fix A flow works and is conservative. Fix B
is strictly better when concept.json is reliable — but turning it on
requires telling the image model "no text in image" again, and any
regression in that constraint would put us back in the empty-text bug.
So: env-gated, validated in real runs first.

**Touch points:**

- `editable_pptx/assemble.py` `add_slide_from_image` — when
  `<deck>/prompts/<stem>.concept.json` exists, read it and emit text
  frames for headline / subhead / body anchored to `text_overlay_zone`.
- New env `EDITABLE_PPTX_OVERLAY_FROM_CONCEPT=1` (opt-in).
- When env set: ignore MinerU's text detections (bitmap shouldn't have
  any) AND restore "no text in image" in the anchor + per-slide
  negative; when env unset: keep the Fix A behavior.
- Test: with env set, slide PPTX text frames match `outline.md` exactly
  regardless of what MinerU detected.

---

### P7 — SVG chart + image-model background/sidebar

**What.** Chart slides today are SVG-template-only (data accurate, fully
editable per-bar, no API tokens). User asked for the image model to also
participate. Decision (locked): keep the SVG template as the data layer
and add a Stage-4-generated visual context behind/beside the chart.
Image model produces hero illustration / atmospheric backdrop matching
the deck style; `svg_to_pptx` layers the chart on top.

**Plan deliverable.** Write `docs/illustrated-chart-design.md` covering:

1. Where the chart sits inside the backdrop. Stage 4 returns both
   `text_overlay_zone` and a new `chart_zone` rect. The image prompt
   tells the model to leave `chart_zone` visually quiet enough that the
   SVG chart reads cleanly on top.
2. PPTX composition order: backdrop PNG as picture layer at z=0, then
   native SVG-derived shapes at z=1+.
3. Whether the backdrop is full-bleed (chart sits inside) or sized to
   the unused side region (chart and backdrop are side-by-side).
4. Whether chart legend / title sits in the SVG layer (deterministic,
   editable) or the bitmap (looks better, less editable). Probably SVG.
5. Schema additions to `<CHART_SPEC>` so the planner can opt slides
   into the illustrated form (or whether it's automatic when a chart
   slide also has Stage 4 output).
6. Cost: each illustrated chart adds one image-model call. Decide
   default opt-in vs opt-out.

**Tasks** (`#32` in `TaskList`):

- [ ] **P7.1** — Write the design doc. *Blocked by P5-fix-B landing,
      since the overlay mechanism it ships is the same composition
      mechanism this needs.*
- [ ] **P7.2** — Implement: extend Stage 4 schema for `chart_zone`,
      add chart-aware backdrop generation, layered PPTX composition,
      env-gated default.
- [ ] **P7.3** — Tests: chart accuracy preserved (per-bar values match
      the spec), backdrop generates only when enabled, layered
      composition order correct in the output PPTX.

---

### P-clean — Remove old prompt-template fallback

`write_prompt_files` still produces the legacy `<STYLE_INSTRUCTIONS>` +
`// VISUAL` prose dump as a fallback when no concept.json exists. After
P5 is validated in real runs, drop the fallback so the codepath is
single-purpose. Low priority; cleanup, not user-visible.

---

### P-future — Consistency critique pass (Stage 6 from creative-director design)

After all images render, render thumbnail grid, send to VLM with style
preset, get back `{slide_index, axis, severity, issue, suggested_fix}`.
Act on `severity >= 3` by regenerating with tighter style constraints
or with reference images. Behind `EDITABLE_PPTX_CRITIQUE=1` env, opt-in.

Defer until P6 lands and we see whether Stage 4 quality alone is enough
or critique is needed for the last 20%. Cheap to add later.

---

### P-future — Live progress for the editable_pptx subprocess

The deck assembler runs in a subprocess (`python -m deck_assembler`),
so the progress bus only sees "PPTX stage start" and "PPTX stage end" —
no per-slide MinerU / VLM / decompose / cache ticks during assembly.
Two options:

- Replace the subprocess with a direct in-process call. Large refactor,
  ties Streamlit's import order to opencv etc.
- Have the subprocess emit progress lines on stdout and the parent
  parse them.

Defer. The current "PPTX assembly running…" bar is fine for most decks.

---

### P-future — Documentation refresh

`README.md` describes the original pipeline. Should mention:

- The `Stage.CONCEPTS` step (creative director).
- Concept files as the user-editable surface.
- The `EDITABLE_PPTX_DECOMPOSE_*` env-var family from Phase 2.
- The analysis cache from Phase 3 (`EDITABLE_PPTX_ANALYSIS_CACHE`,
  `EDITABLE_PPTX_ANALYSIS_WORKERS`).
- The PDF caching from Phase 1 (`SKILLDECK_EXPORT_PDF`).
- Live progress + autorefresh from Phase 2.

Low priority; users follow the Streamlit UI, not the README, for run
mechanics.

---

### P-future — Integration tests for `run_pipeline`

All current 106 tests are unit-level: helpers, parsers, schema
validators, IO roundtrips, single-function happy paths and edge cases.
There's no end-to-end test that exercises `run_pipeline` against a fake
LLM and asserts the timeline transitions correctly across all stages.

Worth adding once P6 lands since gates make the timeline more
interesting to assert on. Use the `chat_call` injection pattern that
`generate_visual_concept` and `generate_style_anchor` already follow —
the rest of the LLM call sites would need to be refactored to accept
an injected callable too before this is testable.

---

## Done — for reference

- **Phase 0**: Streamlit `use_container_width` → `width` deprecation.
- **Phase 1**: Duplicate `write_prompt_files` removed. Globs tightened
  to `[0-9][0-9]-slide-*` excluding backups everywhere. Content-aware
  writes (skip-if-unchanged, backup-on-change). Image-API call cached
  by prompt hash. `EDITABLE_PPTX_LAYOUT_ENGINE=hybrid_cv` honored in
  `deck_assembler` (no longer requires `MINERU_TOKEN` in hybrid mode).
  Optional PDF (`SKILLDECK_EXPORT_PDF` env + checkbox) + PPTX-hash
  cache for skipping unchanged conversions. Helpers extracted to
  `skilldeck_utils.py`.
- **Phase 2**: VLM diagram decomposition (`editable_pptx/decompose.py`)
  — second VLM pass on every image / figure / diagram region above
  `EDITABLE_PPTX_DECOMPOSE_MIN_AREA_FRACTION` (default 0.05). Returns
  sub-shapes + interior text + `removed_indices`; bitmaps replaced
  with editable shapes. Live progress: new `progress.py` with
  thread-safe `ProgressBus` + ordered `Stage` enum + capped event log
  + atomic snapshots. Pipeline runs in a daemon thread with
  `add_script_run_ctx`; UI uses `streamlit-autorefresh` (or `st.rerun`
  fallback) at ~1 Hz; live timeline + 12-line event log expander.
- **Phase 3**: Per-slide analysis cache
  (`editable_pptx/analysis_cache.py`) — caches VLM styles + page
  background + `detect_shapes` output + decomposition output per
  slide. Key = sha256(image bytes) + style model + decompose flag +
  min-area + layout engine. Stored at
  `<deck>/analysis-cache/<slide-stem>.vlm.json`. Per-slide analysis
  parallelized via `ThreadPoolExecutor` (default 4 workers, override
  `EDITABLE_PPTX_ANALYSIS_WORKERS`); python-pptx assembly stays serial
  with order preserved.
- **Phase 4**: Dropped per user decision — `scene.json` + unified merge
  weren't needed once Phase 1–3 fixed the user-visible pain.
- **Phase 5**: Creative-director Stage 4. New `concept.py`,
  `Stage.CONCEPTS` in progress bus between PROMPTS and CHARTS,
  sequential per-slide visual concepts, LLM-generated style anchor
  with on-disk cache, image-prompt rewrite to template the concept,
  bidirectional sync (outline-edit invalidates, user-edit sticks).
  Five high-quality few-shot examples covering five beat roles across
  five style presets in `skill/references/concept-examples.md`.
- **Phase 5 Fix A**: P5 originally told the image model "no text in
  image" without building the forward overlay path, leaving slides
  textless. Fix A re-enabled text rendering: image model now receives
  the slide's headline / subhead / body verbatim and renders them
  inside the bitmap; MinerU + `editable_pptx` reconstruct them as
  native text frames downstream as before. Concept JSON now carries
  a `body` field; `_slide_body_bullets` parses the outline `Body:`
  list. Pre-P5 behavior restored *plus* the Stage 4 quality lift.

---

## Test count

- **106** tests passing as of P5 Fix A.
- Coverage spans: helpers (Phase 1), progress bus (Phase 2), diagram
  decomposition (Phase 2), analysis cache (Phase 3), concept module
  + schema validation + sync + prompt rendering (Phase 5).
- No integration tests against a live LLM. By design, all LLM calls
  in `concept.py` are injected via a `chat_call` callable so tests
  can stub them. The other LLM call sites (outline retry, image API)
  would need similar refactor to be testable end-to-end.
