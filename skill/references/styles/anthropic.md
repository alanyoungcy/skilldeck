---
preset_id: "anthropic"
kind: "layout_template"
layout_dir: "templates/layouts/anthropic"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "AI tech talks, developer conferences, technical training, product launches."
keywords:
  - "Tech-forward"
  - "professional"
  - "modern"
  - "conclusion-first"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# anthropic

AI tech talks, developer conferences, technical training, product launches.

## Template Source

- Source layout: `templates/layouts/anthropic`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Tech-forward, professional, modern, conclusion-first

## Best For

AI tech talks, developer conferences, technical training, product launches.

## SVG Template Roster

- `01_cover.svg`
- `02_chapter.svg`
- `02_toc.svg`
- `03_content.svg`
- `04_ending.svg`

## Template Assets

- None declared

## Design Aesthetic

## I. Template Overview

| Property       | Description                                            |
| -------------- | ------------------------------------------------------ |
| **Template Name** | anthropic (Anthropic Style Template)                |
| **Use Cases**  | AI tech talks, developer conferences, technical training, product launches |
| **Design Tone** | Tech-forward, professional, modern, conclusion-first |
| **Theme Mode** | Mixed theme (dark cover/chapter + light content pages) |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role             | Value       | Notes                            |
| ---------------- | ----------- | -------------------------------- |
| **Anthropic Orange** | `#D97757` | Brand identity, title emphasis, key data |
| **Deep Space Gray** | `#1A1A2E` | Cover background, body text, chart base |
| **Tech Blue**    | `#4A90D9`   | Flowcharts, links, interactive elements |
| **Mint Green**   | `#10B981`   | Recommended options, positive indicators, success states |
| **Coral Red**    | `#EF4444`   | Risks, cautions, warnings        |

### Neutral Colors

| Role           | Value       | Usage                  |
| -------------- | ----------- | ---------------------- |
| **Cloud White** | `#F8FAFC`  | Card background        |
| **Border Gray** | `#E2E8F0`  | Card borders, dividers |
| **Slate Gray** | `#64748B`   | Secondary text, chart labels |
| **Pure White** | `#FFFFFF`   | Page background        |

---

## Typography

## IV. Typography System

### Font Stack

**Font Stack**: `Arial, "Helvetica Neue", "Segoe UI", sans-serif`

### Font Size Hierarchy

| Level    | Usage            | Size   | Weight  |
| -------- | ---------------- | ------ | ------- |
| H1       | Cover main title | 56px   | Bold    |
| H2       | Page title       | 32-36px| Bold    |
| H3       | Subtitle/section | 24-28px| Semibold|
| H4       | Card title       | 20-22px| Bold    |
| P        | Body content     | 16-18px| Regular |
| Data     | Highlighted data | 40-48px| Bold    |
| Label    | Label text       | 14px   | 500     |
| Sub      | Chart labels/footnotes | 12-14px | Regular |

---

## Layout Principles

## VI. Page Structure

### General Layout

| Area           | Position/Height | Description                            |
| -------------- | --------------- | -------------------------------------- |
| **Top**        | y=0, h=6-8px    | Anthropic Orange decorative bar        |
| **Label**      | y=50-70         | Page type label (uppercase, orange)    |
| **Title Area** | y=80-140        | Page title (core takeaway)             |
| **Content Area** | y=160-620     | Main content area                      |
| **Footer**     | y=680           | Page number (centered)                 |

### Decorative Elements

- **Top Orange Bar**: Anthropic Orange (`#D97757`), height 6px
- **Left Gradient Bar**: Orange gradient (`#D97757` → `#E8956F`)
- **Card Border**: Light gray (`#E2E8F0`)
- **Card Shadow**: Soft shadow effect
- **Grid Decoration Lines**: White low-opacity grid on dark covers

---

## Page Roles

Use cover, chapter, content, and ending SVGs as role-specific composition references.

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
