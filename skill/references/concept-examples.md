# Concept examples (Stage 4 few-shots)

These examples teach the creative-director LLM the *level of specificity*
that separates a description from a concept. They are spliced into the
Stage 4 prompt verbatim. Five examples covering different beat roles,
architypes, and presets so the model doesn't lock onto one aesthetic.

The schema (parallel to `concept` in `prompts/NN-slide-{slug}.concept.json`):

```
{
  "subject": "...",                  // the literal thing rendered
  "composition": "...",              // canvas split + framing
  "metaphor": "...",                 // what the subject stands in for
  "mood": "...",                     // emotional register
  "foreground_elements": ["..."],    // near, in focus
  "background_treatment": "...",     // far, secondary
  "text_overlay_zone": {"x": 0..1, "y": 0..1, "w": 0..1, "h": 0..1}
}
```

`text_overlay_zone` describes the rectangle inside which the image model
should render the slide's actual headline, subhead, and body bullets. The
downstream pipeline detects those rendered words and converts them back
into native PowerPoint text frames, so you decide *where* the text sits
and how the visual frames it; the words themselves come from `outline.md`
and are passed to the image model verbatim.

---

## Example 1 — claim, metaphor_split, blueprint

**Slide block:**

```
Headline: Resilience is plural
Subhead: Strength lives in the chain, not the link
Body:
- One link can fail; the chain holds
- Distributed risk beats concentrated certainty
- Systems outlast their parts
```

**Architype:** `metaphor_split` — visual metaphor on one side, text reserved on the other.

**Style preset:** `blueprint` (grid texture, cool engineering blues, technical line work).

**Concept:**

```json
{
  "subject": "a single chain laid diagonally across blueprint paper, drafted in thin engineering lines, with one link slightly enlarged and rendered in solid engineering-blue ink while the rest stay in light pencil contour",
  "composition": "asymmetric — chain occupies the left two-thirds, anchored bottom-left to upper-middle; right third is reserved blueprint paper for headline and three-bullet body",
  "metaphor": "the load-bearing link is indistinguishable from the others until tension reveals it",
  "mood": "analytical, quietly confident, structural",
  "foreground_elements": [
    "drafted chain in cool blue ink",
    "dimension lines marking link spacing",
    "small annotation labels in technical sans-serif"
  ],
  "background_treatment": "warm off-white blueprint paper with faint graph grid, subtle edge wear",
  "text_overlay_zone": {"x": 0.66, "y": 0.10, "w": 0.30, "h": 0.78}
}
```

---

## Example 2 — data_point, data_with_visual, bold-editorial

**Slide block:**

```
Headline: Usage doubled in six months
Subhead: 41k → 89k weekly active accounts, Q1–Q3 2026
Body:
- Mobile growth led, web held flat
- New self-serve onboarding shipped in March
- Source: internal product analytics
```

**Architype:** `data_with_visual` — chart on one side, illustrative concept on the other.

**Style preset:** `bold-editorial` (high contrast, vibrant accents, magazine impact).

**Concept:**

```json
{
  "subject": "an oversized stylized growth curve printed in bold editorial style, the curve rendered as a thick gestural brush stroke in vibrant coral against a deep charcoal background, the curve's apex bursting through the top edge of the canvas",
  "composition": "full-bleed left panel for the curve; right third clean charcoal for headline, subhead, and an inline chart placeholder. The curve crosses a hairline horizontal axis but dominates vertically",
  "metaphor": "growth that exceeded its own frame — the bitmap can't contain the trajectory",
  "mood": "decisive, celebratory, unhurried",
  "foreground_elements": [
    "thick coral curve, slightly textured edge",
    "hairline cream axis lines",
    "small marker dot at the curve's exit point"
  ],
  "background_treatment": "deep charcoal flat fill with subtle paper grain, no gradient",
  "text_overlay_zone": {"x": 0.62, "y": 0.12, "w": 0.32, "h": 0.74}
}
```

---

## Example 3 — hook, full_bleed_hero, sketch-notes

**Slide block:**

```
Headline: What if compounding worked against you?
Subhead: A short story about small mistakes that don't stay small
Body: (none — cover/hook slide)
```

**Architype:** `full_bleed_hero` — one dominant image, headline overlaid on a quiet zone.

**Style preset:** `sketch-notes` (loose hand-drawn ink + light watercolor on warm cream paper).

**Concept:**

```json
{
  "subject": "a hand-drawn snowball rolling down a sloped mountain path, growing visibly larger at each loose ink stroke along its trail, with three smaller snow lumps scattered at the start and one massive accumulating mass near the bottom edge",
  "composition": "centered diagonal — the snowball's trajectory enters from upper-left and arcs to lower-right, leaving the upper-right quadrant quiet for headline placement",
  "metaphor": "small things you ignore become the thing that defines the slope",
  "mood": "warm, slightly rueful, story-opening",
  "foreground_elements": [
    "loose ink-line snowball with subtle blue watercolor wash",
    "broken dotted trail showing the path",
    "three small starter lumps in pencil"
  ],
  "background_treatment": "warm cream paper with gentle blue watercolor wash on the slope, white space dominant in the headline zone",
  "text_overlay_zone": {"x": 0.55, "y": 0.08, "w": 0.40, "h": 0.40}
}
```

---

## Example 4 — comparison, two_column_compare, scientific

**Slide block:**

```
Headline: Two pathways, one outcome
Subhead: Glycolysis vs. oxidative phosphorylation, in cells under stress
Body:
- Glycolysis: fast, low ATP yield, anaerobic-tolerant
- OxPhos: slow, high ATP yield, requires oxygen
- Stressed cells favor glycolysis even when oxygen is present (Warburg effect)
```

**Architype:** `two_column_compare` — A vs B side-by-side with parallel framing.

**Style preset:** `scientific` (clean, cool blues, precise diagrammatic illustration, restrained palette).

**Concept:**

```json
{
  "subject": "two parallel cellular pathway diagrams, drawn cross-section style: left column shows a glucose molecule splitting into lactate via short arrows and a small ATP icon (×2); right column shows the same glucose entering a stylized mitochondrion with a longer arrow chain and a larger ATP icon (×~32). Both diagrams use identical line weight and labeling conventions",
  "composition": "vertical center divider, two equal columns; each column has a labeled header band at top, a stack of pathway nodes in the middle, and a numerical ATP yield at the bottom",
  "metaphor": "same input, different machinery — speed vs efficiency framed as a deliberate cellular tradeoff",
  "mood": "precise, didactic, neutral",
  "foreground_elements": [
    "two pathway diagrams in cool slate blue",
    "small ATP icons sized to convey relative yield",
    "thin labeled arrows between nodes"
  ],
  "background_treatment": "near-white background with a soft 1px center divider; light cool-gray quadrant tint to subtly distinguish the two columns",
  "text_overlay_zone": {"x": 0.05, "y": 0.04, "w": 0.90, "h": 0.10}
}
```

---

## Example 5 — payoff, hero_with_bullets, notion

**Slide block:**

```
Headline: One platform replaces five tools
Subhead: We retired the bolt-on stack in Q2 — here's what changed
Body:
- Single source of truth for accounts and contracts
- 3 fewer integrations to monitor
- Onboarding dropped from 11 days to 4
- 2026 budget: -$140k in saas spend
```

**Architype:** `hero_with_bullets` — one focal visual on the left, bullet list on the right.

**Style preset:** `notion` (clean SaaS dashboard aesthetic, neutral grays, geometric sans, dense layout tolerated).

**Concept:**

```json
{
  "subject": "a single rounded-square platform card centered-left, sitting on a faint dot-grid; five small tool-tile silhouettes arranged in a fading arc behind it, each rendered in lighter gray and slightly translucent as if dissolving into the central card",
  "composition": "left half holds the platform card and the dissolving tool tiles; right half is clean whitespace reserved for headline, subhead, and the four-bullet list with simple icons",
  "metaphor": "consolidation visualized as gravity — the smaller tools collapse into the larger one rather than the larger one absorbing them aggressively",
  "mood": "calm, definitive, slightly relieving",
  "foreground_elements": [
    "central rounded-square platform card with subtle drop shadow",
    "five smaller tool tiles in fading gray, arranged in an arc",
    "thin connector lines from each tile to the central card"
  ],
  "background_treatment": "near-white with a faint dot grid, no gradient",
  "text_overlay_zone": {"x": 0.50, "y": 0.10, "w": 0.45, "h": 0.78}
}
```

---

## What to copy from these examples (for the LLM)

- `subject` says **what is rendered**, not what it represents. Render-time visible nouns and adjectives only.
- `composition` is **specific about the canvas split**: name which third / quadrant / diagonal the elements occupy. Always reserve space for `text_overlay_zone`.
- `metaphor` is **one sentence** of conceptual interpretation. Not the slide's argument — the visual's argument.
- `mood` is **emotional register**, not visual style. Style is locked by the preset; mood varies per slide.
- `foreground_elements` is **2–4 items**, each a concrete visual object the renderer can produce.
- `background_treatment` is **one short clause** about color, texture, gradient, paper, etc.
- `text_overlay_zone` uses **normalized coordinates [0,1]** with origin top-left. Width × height must leave at least 30% of the canvas for the visual.
- **The image model renders the slide's text inside the bitmap.** The headline, subhead, and body bullets appear as actual rendered words inside `text_overlay_zone`. The downstream pipeline detects those words and reconstructs them as native, editable PowerPoint text frames; what you decide here is *where the text sits and how the visual frames it*, not whether it appears.
