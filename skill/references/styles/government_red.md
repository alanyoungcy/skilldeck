---
preset_id: "government_red"
kind: "layout_template"
layout_dir: "templates/layouts/government_red"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "Government briefings, policy interpretation, work summaries, project introductions, investment promotion."
keywords:
  - "Authoritative"
  - "dignified"
  - "professional"
  - "modern government style"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# government_red

Government briefings, policy interpretation, work summaries, project introductions, investment promotion.

## Template Source

- Source layout: `templates/layouts/government_red`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Authoritative, dignified, professional, modern government style

## Best For

Government briefings, policy interpretation, work summaries, project introductions, investment promotion.

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
| **Template Name** | government_red (Government Red Template)                  |
| **Use Cases**  | Government briefings, policy interpretation, work summaries, project introductions, investment promotion |
| **Design Tone** | Authoritative, dignified, professional, modern government style |
| **Theme Mode** | Light theme (white background + government red/blue accents) |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role           | Value       | Notes                              |
| -------------- | ----------- | ---------------------------------- |
| **Government Red** | `#8B0000` | Primary color, title bar, accent blocks, decoration bars |
| **Government Blue** | `#003366` | Secondary accent, chapter page backgrounds |
| **Background White** | `#FFFFFF` | Main page background            |
| **Auxiliary Light Gray** | `#F5F7FA` | Non-critical content background blocks |
| **Border Gray** | `#E4E7EB`  | Dividers, borders                  |
| **Gold Accent** | `#DAA520`  | Decorative accents, important data highlights |

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
| H1    | Cover main title   | 48px | Bold    |
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
| **Top**    | y=0, h=6px      | Dual-color gradient bar (red + blue), full width |
| **Title Bar** | y=30, h=50px | Section number block + title text + top-right logo |
| **Content Area** | y=100, h=560px | Main content area                 |
| **Footer** | y=680, h=40px   | Page number, organization name, bottom decoration line |

### Navigation Bar Design

- **Top Decoration Line**: Dual-color gradient (`#8B0000` → `#003366`), height 6px, full width
- **Bottom Decoration Line**: Government red (`#8B0000`), height 4px, y=716
- **Title Bar** (y=30):
  - Section number block: Government red square (50×50px), white number centered
  - Title text: 20px from number block, 28px font size, `#1A1A1A`
  - Top-right logo: Fixed at x=1107, dimensions 113×50px

---

## Page Roles

## VI. Page Types

### 1. Cover Page (01_cover.svg)

- Dark gradient background (primarily government blue)
- Top gold decoration line
- Main title + subtitle (centered, white)
- Organization name
- Bottom date area

### 2. Table of Contents (02_toc.svg)

- White background + left-side red vertical bar decoration
- Supports up to 5 chapters
- Numbering uses red square blocks + white numbers
- Optional data display area on the right

### 3. Chapter Page (02_chapter.svg)

- Deep blue gradient background
- Large chapter number (semi-transparent decoration)
- Chapter title + English subtitle
- Geometric decorative elements

### 4. Content Page (03_content.svg)

- White background
- Standard navigation bar (red number block)
- Flexible content area
- Supports multiple layout modes

### 5. Ending Page (04_ending.svg)

- Deep blue background
- Centered thank-you message
- Full organization name
- Contact/Address information

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
