---
preset_id: "medical_university"
kind: "layout_template"
layout_dir: "templates/layouts/medical_university"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "Medical academic reports, case discussions, research presentations, hospital work reports, medical education and training."
keywords:
  - "Professional"
  - "rigorous"
  - "life-affirming"
  - "tech-forward"
  - "trustworthy"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# medical_university

Medical academic reports, case discussions, research presentations, hospital work reports, medical education and training.

## Template Source

- Source layout: `templates/layouts/medical_university`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Professional, rigorous, life-affirming, tech-forward, trustworthy

## Best For

Medical academic reports, case discussions, research presentations, hospital work reports, medical education and training.

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

| Property         | Description                                                          |
| ---------------- | -------------------------------------------------------------------- |
| **Template Name**| medical_university (Hospital / Medical University Template)          |
| **Use Cases**    | Medical academic reports, case discussions, research presentations, hospital work reports, medical education and training |
| **Design Tone**  | Professional, rigorous, life-affirming, tech-forward, trustworthy   |
| **Theme Mode**   | Light theme (white background + medical blue title bar + life green accents) |
| **Target Institutions** | All types of medical institutions (hospitals, medical universities, affiliated hospitals, medical research institutes) |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role               | Value     | Notes                                    |
| ------------------ | --------- | ---------------------------------------- |
| **Primary Medical Blue** | `#0066B3` | Header background, chapter titles, main titles |
| **Deep Medical Blue** | `#004080` | Chapter page background, key emphasis   |
| **Accent Green**   | `#00A86B` | Card borders, life/health-related content, icons |
| **Emphasis Orange** | `#FF6B35` | Key highlights, critical data, left accent bars |
| **Light Blue BG**  | `#E6F3FA` | Key message background bar, card inner blocks |
| **Light Green BG** | `#E8F5EE` | Medical-related cards, health data blocks |
| **Background White** | `#FFFFFF` | Main page background                   |

### Text Colors

| Role             | Value     | Usage                      |
| ---------------- | --------- | -------------------------- |
| **White Text**   | `#FFFFFF` | Text on dark backgrounds   |
| **Primary Text** | `#333333` | Body content               |
| **Secondary Text** | `#666666` | Captions, annotations    |
| **Muted Gray**   | `#999999` | Footer, supplementary info |

### Neutral Colors

| Role           | Value     | Usage                        |
| -------------- | --------- | ---------------------------- |
| **Card Gray**  | `#F5F7FA` | Card inner background, info blocks |
| **Border Gray**| `#D0D7E0` | Card borders, divider lines  |

### Functional Colors

| Usage        | Value     | Description                    |
| ------------ | --------- | ------------------------------ |
| **Success**  | `#28A745` | Positive indicators, recovery data |
| **Warning**  | `#FFC107` | Precautions, reminders         |
| **Danger**   | `#DC3545` | Critical values, risk alerts   |

...

## Typography

## IV. Typography System

### Font Stack

**Font Stack**: `"Microsoft YaHei", "微软雅黑", Arial, sans-serif`

### Font Size Hierarchy

| Level | Usage            | Size | Weight  |
| ----- | ---------------- | ---- | ------- |
| H1    | Cover main title | 52px | Bold    |
| H2    | Page title       | 28px | Bold    |
| H3    | Chapter title    | 52px | Bold    |
| H4    | Card title       | 24px | Bold    |
| P     | Body content     | 18px | Regular |
| High  | Emphasized data  | 36px | Bold    |
| Sub   | Notes/sources    | 14px | Regular |
| XS    | Page number/copyright | 12px | Regular |

---

## Layout Principles

## V. Page Structure

### General Layout

| Area              | Position/Height  | Description                                  |
| ----------------- | ---------------- | -------------------------------------------- |
| **Header**        | y=0, h=70px      | Medical blue background + orange left vertical bar + page title |
| **Key Message Bar** | y=70, h=50px   | Core message/summary area (light blue background) |
| **Content Area**  | y=135, h=515px   | Main content area                            |
| **Footer**        | y=665, h=55px    | Data source, institution name, page number   |

### Decorative Design

- **Left Orange Vertical Bar**: Emphasis orange (`#FF6B35`), width 6px, used for header and card decoration
- **Medical Blue Border**: Primary blue (`#0066B3`), used for card borders
- **Green Accents**: Accent green (`#00A86B`), used for health/life-related elements
- **Cross/ECG Decorations**: Medical-themed geometric decorative elements

---

## Page Roles

## VI. Page Types

### 1. Cover Page (01_cover.svg)

- White background
- Medical blue top horizontal bar + orange left vertical bar decoration
- Upper-right logo/emblem placeholder area
- Centered main title + subtitle
- Decorative divider line (blue + green dots)
- Presenter information area (name, department/advisor, institution)
- Bottom gray info area (date)

### 2. Table of Contents (02_toc.svg)

- White background
- Standard header (medical blue + orange vertical bar)
- Card-style TOC layout (2 columns)
- Light blue/light green background cards + left colored vertical bar
- Optional items use dashed borders

### 3. Chapter Page (02_chapter.svg)

- Deep medical blue full-screen background (`#004080`)
- Right-side geometric decorations (medical theme)
- Left orange vertical bar decoration
- Large semi-transparent background chapter number
- Prominent white chapter title
- Light blue chapter description

### 4. Content Page (03_content.svg)

- White background
- Standard header (medical blue + orange vertical bar)
- Key message bar (light blue background + blue left vertical bar)
- Flexible content area
- Footer: data source, institution name, page number

### 5. Ending Page (04_ending.svg)

- White background
- Medical blue top horizontal bar
- Centered thank-you message
- Department/contact information
- Institution logo area

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
