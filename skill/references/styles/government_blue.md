---
preset_id: "government_blue"
kind: "layout_template"
layout_dir: "templates/layouts/government_blue"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "Key project briefings, Five-Year Plan presentations, work summaries, investment promotion, policy interpretation."
keywords:
  - "Grand"
  - "tech-forward"
  - "modern"
  - "professional government style"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# government_blue

Key project briefings, Five-Year Plan presentations, work summaries, investment promotion, policy interpretation.

## Template Source

- Source layout: `templates/layouts/government_blue`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Grand, tech-forward, modern, professional government style

## Best For

Key project briefings, Five-Year Plan presentations, work summaries, investment promotion, policy interpretation.

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

| Property       | Description                                                  |
| -------------- | ------------------------------------------------------------ |
| **Template Name** | government_blue (Government Blue Template)                |
| **Use Cases**  | Key project briefings, Five-Year Plan presentations, work summaries, investment promotion, policy interpretation |
| **Design Tone** | Grand, tech-forward, modern, professional government style  |
| **Theme Mode** | Light theme (white background + blue gradient accents)       |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role           | Value       | Notes                              |
| -------------- | ----------- | ---------------------------------- |
| **Primary Deep Blue** | `#0050B3` | Titles, key borders, section number blocks |
| **Tech Bright Blue** | `#00B4D8` | Decorative elements, accent color, gradient highlights |
| **Ocean Blue**  | `#003366`  | Chapter page backgrounds, gradient dark end |
| **Auxiliary Light Blue** | `#E6F4FF` | Background base, subdued blocks |
| **Sky Blue**    | `#90E0EF`  | Decorative accents, secondary emphasis |

### Text Colors

| Role           | Value       | Usage                  |
| -------------- | ----------- | ---------------------- |
| **Primary Text** | `#1A1A1A` | Body text, titles      |
| **White Text** | `#FFFFFF`   | Text on dark backgrounds |
| **Secondary Text** | `#4A5568` | Dimmed sections, supplementary notes |
| **Light Auxiliary** | `#718096` | Annotations, page numbers, hints |

### Functional Colors

| Usage    | Value       | Description    |
| -------- | ----------- | -------------- |
| **Success** | `#38A169` | Completed/On target |
| **Warning** | `#E53E3E` | Attention/Alert |
| **Info**    | `#3182CE` | General information |

---

## Typography

## IV. Typography System

### Font Stack

**Font Stack**: `"Microsoft YaHei", "微软雅黑", "SimHei", "Source Han Sans SC", Arial, sans-serif`

### Font Size Hierarchy

| Level | Usage              | Size | Weight  |
| ----- | ------------------ | ---- | ------- |
| H1    | Cover main title   | 52px | Bold    |
| H2    | Page heading       | 28px | Bold    |
| H3    | Section title/Subtitle | 24px | Bold |
| P     | Body content       | 18px | Regular |
| High  | Highlighted data   | 36px | Bold    |
| Sub   | Supplementary text | 14px | Regular |

---

## Layout Principles

## V. Page Structure

### General Layout

| Area       | Position/Height | Description                            |
| ---------- | --------------- | -------------------------------------- |
| **Top**    | y=0, h=6px      | Blue gradient bar (bright blue → deep blue), full width |
| **Title Bar** | y=30, h=50px | Section number block + title text + top-right logo |
| **Content Area** | y=100, h=560px | Main content area                 |
| **Footer** | y=680, h=40px   | Page number, organization name, bottom decoration line |

### Navigation Bar Design

- **Top Decoration Line**: Blue gradient (`#00B4D8` → `#0050B3`), height 6px, full width
- **Bottom Decoration Line**: Deep blue (`#0050B3`), height 4px, y=716
- **Title Bar** (y=30):
  - Section number block: Deep blue square (50×50px), white number centered
  - Title text: 20px from number block, 28px font size, `#1A1A1A`
  - Top-right logo: Fixed at x=1107, dimensions 113×50px

---

## Page Roles

## VI. Page Types

### 1. Cover Page (01_cover.svg)

- Deep blue gradient background + tech grid texture
- Left-side bright blue accent bar
- Main title + subtitle (white)
- Presenter/Organization info
- Bottom date area
- Geometric decorative circles

### 2. Table of Contents (02_toc.svg)

- Light blue gradient background
- Left-side decorative trapezoid + gradient vertical bar
- Supports up to 5 chapters
- Circular numbering + connector line design
- Floating card effect (simulated with solid colors)

### 3. Chapter Page (02_chapter.svg)

- Deep blue gradient background
- Radial glow decoration
- Large chapter number (semi-transparent + stroke effect)
- Chapter title + English subtitle
- Bright blue accent bar

### 4. Content Page (03_content.svg)

- Light gradient background
- Gradient number block
- Dashed divider lines
- Flexible content area
- Supports multiple layout modes

### 5. Ending Page (04_ending.svg)

- Deep blue gradient background
- Wave curve decoration
- Centered thank-you message (Chinese and English)
- Bright blue divider line
- Contact information

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
