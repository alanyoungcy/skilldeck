# consulting-deck

Enterprise consulting deck in the IBM / Accenture / Big-Four idiom — confident, structured, data-forward, prescriptive. Information is organized into repeatable patterns that build a logical argument, not just decorated.

## Design Aesthetic

Polished enterprise consulting slides where structure does the persuading. Crisp geometry, generous whitespace, modular grids, and strong typographic hierarchy carry the slide. Color is surgical — a deep corporate blue for authority, a single warm accent (coral or red) for the one number per slide that must land. Charts are flat and unembellished. Every element is on grid; every visual proves a stated finding. Decorative elements are absent — the only "ornament" is the rigor of the layout itself.

## Canvas (pixel size)

This file defines **look and information design**, not raster dimensions. **Width and height come from Skilldeck**: `.env` `IMAGE_SIZE`, or the Streamlit controls (aspect ratio + target width). Per-slide prompt files may repeat “16:9” as a compositional hint; the **authoritative** pixel frame is still that configured size (multiples of 16). After generation, slide PNGs are normalized to exactly that frame (uniform scale, centered on white) so every slide matches for PPTX export. Prefer **16:9** such as `1920×1080` (snapped to `1920×1088` if your backend requires heights divisible by 16).

## Background

- Color: Pure White (#FFFFFF) for content slides; Deep Navy (#0F2A4A) for title and section dividers
- Texture: None. Flat, matte, no gradients on body slides
- Optional: a thin (3–4 px) accent rule at the top of each content slide in IBM Blue

## Typography

### Primary Font (Headlines)

IBM Plex Sans, weight 600. Sentence case, never all-caps. Headlines are written as **findings**, not topics — 6 to 14 words that state the takeaway. Example: "87% of ML models never reach production — pipelines, not algorithms, are the bottleneck" (a finding) — not "Machine Learning Challenges" (a topic).

### Secondary Font (Body)

IBM Plex Sans, weight 400 for body, weight 500 for sub-headers and labels. Body text is dark slate (#262626). Line height 1.4–1.5. Body copy is sparse — one short paragraph OR 3–4 short bullets per zone, never both.

### Numerical Display

Plex Sans 200–300 weight, 60–96 pt for hero stats. The unit and qualifier sit small and quiet beside or below. The number is the slide.

## Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Background | Pure White | #FFFFFF | Body slide background |
| Section Background | Deep Navy | #0F2A4A | Title slides, dividers, hero panels |
| Primary Brand | IBM Blue | #0F62FE | Headers, primary chart series, callouts |
| Supporting | Steel Blue | #4589FF | Secondary chart series |
| Tint | Pale Blue | #D0E2FF | Block fills, highlight zones, table tints |
| Warm Accent | Coral Red | #DA1E28 | The one critical number / insight per slide |
| Cool Accent | Teal | #007D79 | Tertiary series, positive outcome callouts |
| Primary Text | Slate | #262626 | Body, axis labels |
| Secondary Text | Mid Gray | #6F6F6F | Subtitles, source notes |
| Divider | Light Gray | #E0E0E0 | 1 px rules, table grid lines |

## Information Architecture (How Slides Are Organized)

This is the spine of the consulting style. Every slide answers one of four questions, and the layout is dictated by which question it answers.

### The Four Slide Functions

| Function | Purpose | Layout Pattern |
|----------|---------|----------------|
| **Frame** | Establish the problem or context | Headline + 1–3 supporting stats OR a quote |
| **Diagnose** | Show what's broken or shifting | Comparison, gap analysis, before/after |
| **Prescribe** | Recommend the framework or path | Stages, pillars, layers, or matrix |
| **Prove** | Show evidence the prescription works | Outcome stats, case study, ROI block |

A consulting deck cycles through Frame → Diagnose → Prescribe → Prove. Every slide should be tagged (mentally) with one of these — slides that don't have a function get cut.

### The Pyramid Principle (How Each Slide Argues)

Each slide follows top-down logic:

1. **Headline = the conclusion**, not the topic
2. **Body = 2–4 supporting points** that prove the headline
3. **Footer = source / context**, not a summary

Example headline (correct): "Reuse, not novelty, separates AI leaders from laggards — 4 in 5 production ML projects fail without it"
Example headline (wrong): "About AI Project Success Rates"

The reader should grasp the argument from the headlines alone, even with the body content hidden. This is the "skim test" — flip through the deck reading only headlines and see if the story holds.

### The Rule of 3 (Or 4, Never More)

Information is grouped into 3s wherever possible — three pillars, three challenges, three outcomes. Four is acceptable for matrices and quadrants. Five or more triggers a regrouping into categories. Examples from Accenture's pattern:

- Three traits of mature AI: ML engineering at scale · Responsible AI · End-to-end resilient systems
- Three goals of an architecture: Reuse · Reduce manual work · Speed to market
- Three pillars of successful ML: Data quality · Right complexity · Measurability

## Table Design

Tables in consulting decks are not data dumps — they are **structured arguments**. Every column has a job.

### The Comparison Table (most common)

Used for "Option A vs Option B" or "Current state vs Future state."

```
┌──────────────────┬─────────────────────┬─────────────────────┐
│ DIMENSION        │ TODAY               │ WITH [SOLUTION]     │
├──────────────────┼─────────────────────┼─────────────────────┤
│ Time to deploy   │ 9–12 months         │ 6–8 weeks           │
│ Models reused    │ <5%                 │ 60%+                │
│ Failure rate     │ 87% never ship      │ <20% never ship     │
└──────────────────┴─────────────────────┴─────────────────────┘
```

Rules:
- Header row: pale blue tint (#D0E2FF), bold, sentence case
- Body rows: alternating white / very pale gray (#F4F4F4) for scannability
- The "winning" column gets a thin coral left-border to signal "this is the answer"
- Numerical values right-aligned; text left-aligned
- Maximum 6 rows — beyond that, split into two tables

### The Capability / Maturity Table

Used to assess where the client is and what to do next. Three to four rows by three to four maturity levels.

| Capability | Ad hoc | Defined | Optimized | Industrialized |
|------------|--------|---------|-----------|----------------|
| Data quality | Manual checks | Documented rules | Automated baselines | Continuous monitoring |
| Model reuse | None | Shared scripts | Feature store | Cross-org governance |
| Deployment | Notebook hand-off | Manual pipelines | CI/CD for models | Self-service MLOps |

Rules:
- Left column = capability (slate text, weight 500)
- Top row = maturity stages, left to right = worst to best
- Cells = short descriptors, 3–6 words max
- The client's current position is shaded pale blue; the target is shaded coral tint
- A diagonal arrow can run from current → target across the matrix

### The Matrix / 2x2

Two axes, four quadrants, plotted entities. Rules:
- Both axis labels in mid-gray, sentence case ("Business value" / "Implementation effort")
- Quadrant labels in muted gray inside each corner ("Quick wins" / "Strategic bets" / "Fill-ins" / "Avoid")
- Entities plotted as small filled circles (IBM Blue), labeled to the right
- ONE entity highlighted in coral — the recommended starting point
- Always include a one-line caption below: "Quick wins offer fastest ROI; strategic bets shape the 3-year roadmap"

## Diagram Design

Consulting diagrams turn process into picture. Five canonical types cover ~90% of needs.

### 1. Linear Process / Journey

For sequential steps (Accenture's 6-checkpoint AI roadmap is this pattern).

```
[ STAGE 1 ]──→[ STAGE 2 ]──→[ STAGE 3 ]──→[ STAGE 4 ]──→[ STAGE 5 ]
  Define       Curate         Update         Validate       Realize
  value        data           roadmap        team           value
```

Rules:
- Equal-width rectangles, axis-aligned, evenly spaced
- Arrow connectors are simple lines with arrowhead, IBM Blue, 1.5 px stroke
- Each stage has a short title (1–2 words) + a one-line descriptor below
- Number each stage (01, 02, 03…) in pale blue inside the box, top-left
- Highlight the current stage in coral if showing client position
- Outcome metrics go in a separate row below: "→ 67% faster outcomes · 102% ROI"

### 2. Layered Stack / Pillar Framework

For "X rests on Y rests on Z." Use for tech stacks, capability layers, governance frameworks.

```
┌────────────────────────────────────────────┐
│ OUTCOMES         (top — what client gets)  │  coral tint
├────────────────────────────────────────────┤
│ APPLICATIONS      (assistants, copilots)   │  pale blue
├────────────────────────────────────────────┤
│ PLATFORM          (watsonx, SageMaker)     │  pale blue
├────────────────────────────────────────────┤
│ FOUNDATION        (data, models, infra)    │  navy
└────────────────────────────────────────────┘
```

Rules:
- 3 to 5 horizontal bands, equal height
- Lower layers = darker (foundational = navy); upper layers = lighter
- Each band has a label on the left (weight 500) and 2–4 examples on the right
- The layer that's currently the focus of discussion gets a thin coral right-border
- Never more than 5 layers — collapse if needed

### 3. Hub-and-Spoke

For showing one central concept connected to many related elements (a platform with its services, a strategy with its workstreams).

Rules:
- Central node: IBM Blue filled circle or rounded rectangle, label inside in white
- Spokes: thin gray lines, 1 px
- Outer nodes: white-filled rounded rectangles with thin blue border, label inside in slate
- 4 to 8 outer nodes — beyond that, group into two concentric rings
- One outer node may be coral-bordered to indicate priority

### 4. Pyramid

For hierarchies of importance, audience, or strategy (e.g., "10% strategic / 30% tactical / 60% operational").

Rules:
- 3 to 4 horizontal slices stacked into a triangle
- Top slice = narrowest = most strategic / most important
- Each slice labeled inside (left-aligned), with quantitative breakdown to the right (e.g., "10% — 5 executives")
- Color: navy at top fading to pale blue at base, OR all pale blue with coral top slice

### 5. Architecture / Reference Diagram

For technical systems (Accenture's MLOps architecture is this pattern).

Rules:
- Rectangles in pale blue tint with thin IBM Blue border, label inside in slate
- Components grouped into labeled regions (dashed borders, mid-gray)
- Data flows: solid arrows in IBM Blue
- Control flows: dashed arrows in mid-gray
- Components from external systems: white fill, dashed border
- Always include a small legend bottom-right
- Caption below in mid-gray: "Source: [organization], [year]"

## Data Display

### Charts — Allowed and Disallowed

**Allowed:** horizontal bar, vertical bar, stacked bar (max 3 segments), donut (max 4 slices), simple line chart (max 3 series), waterfall chart, dot plot.

**Disallowed:** 3D charts, pie charts with more than 4 slices, charts with shadows or gradients, radar/spider charts (rarely justified), area charts with more than 2 series, dual-axis charts (almost always misleading).

### Chart Anatomy

Every chart has:
1. **Headline above** — the finding the chart proves, NOT the chart's title (e.g., "Production deployments tripled after pipeline automation" — not "ML deployments by year")
2. **Axis labels** — mid-gray, sentence case, units stated ("Models in production (#)")
3. **Series** — IBM Blue primary, Steel Blue secondary, Coral for the one series being argued for
4. **Data labels** — directly on or beside bars/points, slate text. No legend if labels can sit inline
5. **Source line** — bottom-left, mid-gray, 9–10 pt: "Source: [report name], [year], n=[sample size]"
6. **Annotation** — one short coral callout pointing to the key data point: "↑ 87%"

### The Hero Stat Block

A single number does the work of an entire slide. Layout:

```
        87%
        ───
        of ML models never reach production
        Source: [industry survey], [year]
```

Rules:
- Number: Plex Sans 200, 96–144 pt, coral
- Short rule under the number (40 px, slate, 2 px)
- Qualifier sentence: 16–18 pt, slate, max 12 words
- Source: 10 pt, mid-gray
- Centered on the slide OR placed in left half with supporting context on right

### The Three-Stat Row

```
┌─────────────────┬─────────────────┬─────────────────┐
│      102%       │      67%        │       3x        │
│   ────          │   ────          │   ────          │
│   ROI from AI   │   faster        │   model         │
│   engagements   │   outcomes      │   reuse rate    │
└─────────────────┴─────────────────┴─────────────────┘
```

Three equal columns, dividers in light gray, numbers in coral, qualifiers in slate. Use for outcome / proof slides.

## Information Patterns (Reusable Argumentation Structures)

These are the recurring structures consulting firms use to make arguments. Each one is a slide template with a fixed information shape.

### Pattern A: "The Problem in 3 Numbers"
Frame slide. Three statistics that establish urgency. Headline states the implication.
Example: "Most enterprise AI never lands — and the cost of failure is rising"
Body: 87% never reach production · $2.4M average sunk cost · 9 in 10 execs say AI is critical

### Pattern B: "Current State / Future State"
Diagnose slide. Two columns, divider between. Left = today's pain, right = with the recommended approach. Each row is one dimension (cost, speed, risk, quality).

### Pattern C: "The N-Step Journey"
Prescribe slide. Linear process diagram with 4–7 stages. Each stage has a name, a 1-line outcome, and a tool/method. Below the diagram, a single sentence: "End-to-end timeline: 6 months · Investment: $X · Expected ROI: Y%"

### Pattern D: "The Pillar Framework"
Prescribe slide. 3 vertical columns, each headed by one pillar (Data · Models · Operations). Under each header, 3–4 bullets describing what that pillar contains. A horizontal "foundation" bar runs underneath all three.

### Pattern E: "The Maturity Ladder"
Diagnose + Prescribe combined. A 4-stage horizontal ladder (Ad hoc → Defined → Optimized → Industrialized). For each stage, list 2–3 capabilities. Mark the client's current stage with a pale-blue background; mark the 18-month target stage with coral.

### Pattern F: "Proof in Outcomes"
Prove slide. A row of 3–4 outcome stats (with %, $, x multiplier) sourced to a named client engagement. A short caption beneath: "Results from [client type], [time period]."

### Pattern G: "Use Case Inventory"
Prove slide. A 3-column grid showing 6–9 use cases. Each cell has: icon · use case name · one-line outcome metric. Helps establish breadth: "We've solved this many times before."

## Style Rules

### Do

- Write headlines as findings, not topics
- Group information into 3s (or 4 max) — beyond that, regroup into categories
- Reserve coral for ONE element per slide — the one thing the audience must remember
- Pass the "skim test" — the headline-only version of the deck should still tell the story
- Include a source line on every chart, table, and quoted statistic
- Round numbers in callouts (87%, $4.4B, 3x); full precision lives in the source
- Align every element to the underlying grid — left edges, baselines, column boundaries all line up
- Use sentence case everywhere — titles, headers, axis labels, table cells

### Don't

- Use gradients, drop shadows, bevels, glows, or 3D effects
- Mix more than two typefaces
- Apply more than one accent color per slide
- Build slides without a finding headline
- Use tables as data dumps — every column must have a job in the argument
- Crowd a slide — if it doesn't fit calmly, split into two
- Use clipart, emoji, hand-drawn elements, or photo backgrounds behind text
- Center-align body copy or bulleted lists (left-aligned only)
- Use rainbow categorical palettes — stick to defined blues + one accent

## Slide Archetypes (Pick One Per Slide)

Build the deck from this small library; do not invent new layouts.

1. **Title slide** — Navy bg, white headline, small subtitle, thin coral rule
2. **Section divider** — Navy bg, oversized section number in pale blue, section title in white
3. **Hero stat** — One giant coral number, qualifier, source
4. **Three-stat row** — Three equal columns of stat blocks
5. **Finding + chart** — Finding headline top, chart fills body, source bottom
6. **Two-column compare** — Current state | Future state with divider
7. **Process journey** — Horizontal stages with arrows; one stage emphasized
8. **2x2 matrix** — Clean quadrants with one entity highlighted in coral
9. **Layered framework** — Stacked bands (foundation at base, outcomes at top)
10. **Hub and spoke** — Central concept with 4–8 connected elements
11. **Capability/maturity table** — Rows of capabilities × columns of maturity stages
12. **Use case inventory** — 3×3 grid of solved problems with outcome metrics
13. **Proof of outcomes** — Three to four ROI stats with named client context

## Best For

Strategy decks, AI/digital transformation roadmaps, capability assessments, vendor evaluations, board presentations, executive briefings, RFP responses, and anywhere the goal is to argue a structured recommendation backed by evidence.