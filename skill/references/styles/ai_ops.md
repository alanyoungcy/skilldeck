---
preset_id: "ai_ops"
kind: "layout_template"
layout_dir: "templates/layouts/ai_ops"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
  - "reference_style.svg"
assets: []
summary: "Telecom AI operations architecture, IT system overviews, digital transformation proposals, smart infrastructure reports."
keywords:
  - "Information-dense"
  - "structured"
  - "modular zoning"
  - "telecom"
  - "enterprise style"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# ai_ops

Telecom AI operations architecture, IT system overviews, digital transformation proposals, smart infrastructure reports.

## Template Source

- Source layout: `templates/layouts/ai_ops`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Information-dense, structured, modular zoning, telecom, enterprise style

## Best For

Telecom AI operations architecture, IT system overviews, digital transformation proposals, smart infrastructure reports.

## SVG Template Roster

- `01_cover.svg`
- `02_chapter.svg`
- `02_toc.svg`
- `03_content.svg`
- `04_ending.svg`
- `reference_style.svg`

## Template Assets

- None declared

## Design Aesthetic

## I. Template Overview

| Property           | Description                                                                    |
| ------------------ | ------------------------------------------------------------------------------ |
| **Template Name**  | ai_ops (Enterprise Digital Intelligence)                                       |
| **Use Cases**      | Telecom AI operations architecture, IT system overviews, digital transformation proposals, smart infrastructure reports |
| **Design Tone**    | Information-dense, structured, modular zoning, telecom/enterprise style        |
| **Theme Mode**     | Light theme (white background + red-blue dual-color accents + warm gray panels) |
| **Info Density**   | High density — a single page can accommodate 6-10 information modules, matching telecom reporting conventions |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role               | Value       | Notes                                        |
| ------------------ | ----------- | -------------------------------------------- |
| **Primary Red**    | `#C00000`   | Brand identity, title vertical bar, number badges, target bars |
| **Accent Blue**    | `#2E75B6`   | Scenario labels, category headers, bottom accent bars |
| **Light Blue**     | `#5B9BD5`   | Feature module cards, sub-item labels        |

### Functional Colors

| Role               | Value       | Usage                              |
| ------------------ | ----------- | ---------------------------------- |
| **Warm Gray BG**   | `#FDF3EB`   | Overview panel, open platform panel background |
| **Warm Orange Border** | `#F8CBAD` | Panel borders, decorative dividers |
| **Light Gray BG**  | `#F2F2F2`   | Subtitle bar, metric card background |
| **Card Gray BG**   | `#E7E6E6`   | Sub-module cards, capability base cards |
| **Card Border**    | `#D9D9D9`   | Card strokes                       |

### Text Colors

| Role               | Value       | Usage                          |
| ------------------ | ----------- | ------------------------------ |
| **Body Black**     | `#000000`   | Titles, standard body text     |
| **White Text**     | `#FFFFFF`   | Text on dark color blocks      |
| **Secondary Text** | `#666666`   | Subtitles, annotations         |
| **Light Secondary**| `#999999`   | Page numbers, source citations |
| **Data Emphasis**  | `#C00000`   | KPI values, key metrics        |

---

## Typography

## IV. Typography System

### Font Stack

**Font Stack**: `"Microsoft YaHei", "微软雅黑", "SimHei", Arial, sans-serif`

### Font Size Hierarchy

| Level    | Usage                  | Size    | Weight  |
| -------- | ---------------------- | ------- | ------- |
| H1       | Cover main title       | 36-48px | Bold    |
| H2       | Page title             | 32-36px | Bold    |
| H3       | Module title/subtitle  | 18-20px | Bold    |
| P        | Body content           | 14-16px | Regular |
| Caption  | Supplementary/footnotes | 12-14px | Regular |
| Data     | KPI values/metric emphasis | 24-36px | Bold |

> **Note**: Body font size is smaller than usual (14-16px vs standard 18-20px) to accommodate high information density per page.

---

## Layout Principles

## VI. Page Structure

### General Layout

| Area               | Position/Height  | Description                                          |
| ------------------ | ---------------- | ---------------------------------------------------- |
| **Title Area**     | y=20-80          | Red vertical bar + title text + optional subtitle overview bar |
| **Overview Bar**   | y=80-140         | Full-width `#F2F2F2` background bar carrying the page's core summary |
| **Content Area**   | y=140-670        | Main content area (densely packed multi-module layout) |
| **Footer**         | y=680-720        | Red narrow bar with page number + chapter name + source citation |

### Navigation Bar Design

- **Title Vertical Bar**: Red rectangle `#C00000`, 10×40px, positioned left of the title text
- **Title Text**: 10px from the vertical bar, 36px font size, `#C00000` or `#000000`
- **Overview Bar**: Full-width light gray rectangle (h=60px), centered 16px body text carrying the page overview/introduction

### Decorative Elements

- **Number Badges**: 30×30px red squares + white numbers (centered)
- **Blue Labels**: Fixed-width blue rectangles + white text (e.g., "Fault Boundary Identification")
- **Dashed Zone Frames**: `stroke="#C00000"` or `stroke="#E7E6E6"`, `stroke-dasharray="5 5"`
- **Warm Gray Panels**: `fill="#FDF3EB"` + `stroke="#F8CBAD"` + `stroke-width="2"`
- **Light Blue Feature Cards**: `fill="#5B9BD5"` rectangles + white text

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
