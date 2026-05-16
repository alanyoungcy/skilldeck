# Editable PPTX export (Path B in this repo)

Slide images (`NN-slide-*.png`) are turned into a **native, editable** `.pptx`: vector text boxes and figures on top of a background where rasterized text has been masked (**edge**-sampled fill by default, or solid white) so you do not see double text.

## Command

From the **skilldeck** repository root:

```bash
python -m editable_pptx slide-deck/<topic-slug> [-o out.pptx]
```

## Environment variables

### MinerU (layout)

| Variable | Required | Purpose |
|----------|----------|---------|
| `MINERU_TOKEN` | **Yes** | MinerU v4 API bearer token |
| `MINERU_API_BASE` | No | Default `https://mineru.net` |
| `MINERU_MODEL_VERSION` | No | `vlm` or `pipeline` |
| `MINERU_POLL_TIMEOUT` | No | Poll seconds (default `600`) |

### Background and layout

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITABLE_PPTX_BG_MODE` | `edge` | `edge` (average color outside bbox), `whiteout` (solid mask), `none` (raw; double-text risk) |
| `EDITABLE_PPTX_TEXT_PAD` | `1.005` | Text box size vs MinerU bbox |
| `EDITABLE_PPTX_BG_FLATTEN` | `0` | When `1`, drop the full-page bitmap and paint a flat fill from the VLM-inferred page background color. Combine with shape detection for a fully reconstructed look. |
| `EDITABLE_PPTX_LAYOUT_SNAP` | `1` | Snap element bboxes to a pixel grid then cluster shared edges/centers so columns line up. |
| `EDITABLE_PPTX_SNAP_GRID_PX` | `8` | Pixel grid size for the snap step. |
| `EDITABLE_PPTX_SNAP_CLUSTER_PX` | `10` | Edge/center clustering tolerance (pixels). |

### Native shape reconstruction (VLM)

When the VLM is configured (see below), the export asks it to enumerate
decorative shapes — rounded cards, pills, dividers, arrows — that aren't
text/images/tables. Each is emitted as a native PowerPoint preset shape
(`MSO_SHAPE.ROUNDED_RECTANGLE`, `OVAL`, `CHEVRON`, `RIGHT_ARROW`, …) with
fill, stroke, and corner radius set from the VLM output. Shapes the VLM
can't classify confidently fall back to the bitmap path.

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITABLE_PPTX_SHAPE_DETECT` | `1` | Enable VLM-driven shape enumeration. Disable to skip the extra VLM call. |

When a deck folder contains `prompts/NN-slide-*.spec.json` (written by
`streamlit_app` from the `<DESIGN_SPEC>` block in the outline), the export
passes `layout` and `shape_hints` from that file to the VLM as hints — this
makes shape recovery much more reliable for slides that were planned with a
specific archetype.

### Cross-check (LibreOffice + VLM)

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITABLE_PPTX_CROSSCHECK` | `0` | When `1`, render the produced PPTX back to PNGs via LibreOffice and ask the VLM to score each slide vs the source. Writes `crosscheck_report.json` next to the deck. |
| `EDITABLE_PPTX_SOFFICE` | autodetect | Path to the `soffice` binary (default tries `/Applications/LibreOffice.app/Contents/MacOS/soffice` then `$PATH`). |

The crosscheck is a quality gate — it does not auto-retry; it just logs
slides whose similarity score is below `0.6` so you know which to inspect.

### Fonts

| Variable | Purpose |
|----------|---------|
| `EDITABLE_PPTX_FONT_NAME` | Body font (must be installed in PowerPoint) |
| `EDITABLE_PPTX_TITLE_FONT_NAME` | Title font; falls back to body |

If the deck `style` is `sketch-notes` (from `confirmation.yaml` or `outline.md`) and these are unset, defaults try **Patrick Hand** (install it or set the env vars).

When the VLM is enabled, it also returns a per-block `font_family_hint`
(`sans-serif | serif | mono | display | handwritten | script`) and a
`weight`; these select an installed family from `editable_pptx/fonts.py`
(latin + CJK pair) and drive bold rendering. Sizes are **shrunk to fit**
the bbox using `PIL.ImageFont` against the chosen family — this fixes the
CJK/Latin overflow the legacy heuristic produced.

### OpenAI-compatible VLM (style extraction, analyze.md step C)

Uses **`/v1/chat/completions`** with a **vision** model: full slide + per-crop calls for color; merges **bold / italic / underline / alignment / RGB** into text runs.

| Variable | Purpose |
|----------|---------|
| `EDITABLE_PPTX_BASE_URL` | API root; normalized to `.../v1/chat/completions` |
| `EDITABLE_PPTX_API_KEY` | Bearer token |
| `EDITABLE_PPTX_STYLE_MODEL` | Multimodal model id |

If `EDITABLE_PPTX_BASE_URL` or `EDITABLE_PPTX_API_KEY` is empty, **planning** fallbacks apply: `PLANNING_BASE_URL` and `PLANNING_API_KEY`. The **style model** must still be set with `EDITABLE_PPTX_STYLE_MODEL` (do not reuse a non-vision planning model id unless your gateway maps it to a VLM).

When VLM vars are unset, export skips API calls and uses heuristics only.

### Other

Planning and image generation for Streamlit use `PLANNING_*` and `IMAGE_*`; see `.env.example`.

## Limitations

- Layout is **MinerU-only** for typed regions (no hybrid OCR); decorative shapes are recovered by a separate VLM call.
- True **inpainting** (generative clean background) is not implemented; use `edge`, `whiteout`, or the new `EDITABLE_PPTX_BG_FLATTEN=1` flat-fill mode (best when shape detection is reliable).
- **Font family** in PPTX is selected from a hint table (`editable_pptx/fonts.py`); the image model's exact font is only approximated. Override with `EDITABLE_PPTX_FONT_NAME` / `EDITABLE_PPTX_TITLE_FONT_NAME`.
- All slides should share the **same pixel dimensions** for best alignment.
- Shape detection accuracy depends on the VLM. For complex illustrations the bitmap fallback kicks in automatically.

## Legacy flat PPTX

`scripts/merge-to-pptx.ts` is deprecated (flat raster only).
