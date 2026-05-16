---
preset_id: "academic_defense"
kind: "layout_template"
layout_dir: "templates/layouts/academic_defense"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "Thesis defense, academic presentations, research progress reports, grant applications."
keywords:
  - "Professional"
  - "rigorous"
  - "research-oriented"
  - "clear hierarchy"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# academic_defense

Thesis defense, academic presentations, research progress reports, grant applications.

## Template Source

- Source layout: `templates/layouts/academic_defense`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Professional, rigorous, research-oriented, clear hierarchy

## Best For

Thesis defense, academic presentations, research progress reports, grant applications.

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
| **Template Name** | academic_defense                                    |
| **Use Cases**  | Thesis defense, academic presentations, research progress reports, grant applications |
| **Design Tone** | Professional, rigorous, research-oriented, clear hierarchy |
| **Theme Mode** | Light theme (white background + dark blue title bar)   |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role           | Value       | Notes                            |
| -------------- | ----------- | -------------------------------- |
| **Primary Dark Blue** | `#003366` | Header background, section titles, main headings |
| **Accent Blue** | `#0066CC` | Card borders, icons, secondary decorations |
| **Accent Red** | `#CC0000`  | Key highlights, keyword emphasis, left decorative bar |
| **Light Blue-Gray** | `#E8F4FC` | Key message bar background, card inner sections |
| **Background White** | `#FFFFFF` | Page main background           |

### Text Colors

| Role           | Value       | Usage                  |
| -------------- | ----------- | ---------------------- |
| **White Text** | `#FFFFFF`   | Text on dark backgrounds |
| **Primary Text** | `#333333` | Body content           |
| **Secondary Text** | `#666666` | Descriptions, annotations |
| **Muted Gray** | `#999999`  | Footer, auxiliary info |

### Neutral Colors

| Role           | Value       | Usage                  |
| -------------- | ----------- | ---------------------- |
| **Card Gray**  | `#F5F7FA`   | Card inner background, info blocks |
| **Border Gray** | `#D0D7E0`  | Card borders, dividers |

### Functional Colors

| Usage      | Value       | Description    |
| ---------- | ----------- | -------------- |
| **Success** | `#28A745`  | Positive indicators |
| **Warning** | `#FFA500`  | Alerts         |
| **Info**   | `#17A2B8`   | Information tips |

---

## Typography

## IV. Typography System

### Font Stack

**Font Stack**: `"Microsoft YaHei", "微软雅黑", Arial, sans-serif`

### Font Size Hierarchy

| Level | Usage            | Size | Weight  |
| ----- | ---------------- | ---- | ------- |
| H1    | Cover main title | 56px | Bold    |
| H2    | Page title       | 28px | Bold    |
| H3    | Section title    | 56px | Bold    |
| H4    | Card title       | 24px | Bold    |
| P     | Body content     | 18px | Regular |
| High  | Highlighted data | 36px | Bold    |
| Sub   | Notes/sources    | 14px | Regular |
| XS    | Page number/copyright | 12px | Regular |

---

## Layout Principles

## V. Page Structure

### General Layout

| Area           | Position/Height | Description                            |
| -------------- | --------------- | -------------------------------------- |
| **Header**     | y=0, h=70px     | Dark blue background + red left bar + page title |
| **Key Message Bar** | y=70, h=50px | Core message/summary area (light blue-gray background) |
| **Content Area** | y=135, h=515px | Main content area                    |
| **Footer**     | y=665, h=55px   | Data source, section name, page number |

### Decorative Elements

- **Left Red Bar**: Red (`#CC0000`), width 6px, used for header and card decoration
- **Blue Border**: Accent blue (`#0066CC`), used for card borders
- **Decorative Divider**: Blue (`#0066CC`), paired with decorative dots

---

## Page Roles

## VI. Page Types

### 1. Cover Page (01_cover.svg)

- White background
- Dark blue top bar + red left vertical bar decoration
- Top-right Logo placeholder area
- Centered main title + subtitle
- Decorative divider line (blue + dots)
- Presenter info area (name, advisor, institution)
- Bottom gray info area (date)

### 2. Table of Contents Page (02_toc.svg)

- White background
- Standard header (dark blue + red vertical bar)
- Card-style TOC item layout (2 columns)
- Light blue-gray background cards + left colored vertical bar
- Optional items use dashed borders

### 3. Chapter Page (02_chapter.svg)

- Dark blue full-screen background (`#003366`)
- Right-side geometric decorations
- Left red vertical bar decoration
- Large semi-transparent background number
- Prominent white chapter title
- Light blue-gray chapter description
- Red decorative horizontal line

### 4. Content Page (03_content.svg)

- White background
- Standard header (dark blue + red vertical bar)
- Key message bar (light blue-gray background + blue left vertical bar)
- Flexible content area
- Footer: data source, section name, page number

### 5. Ending Page (04_ending.svg)

- White background
- Dark blue top bar
- Centered thank-you message
- Tagline
- Decorative divider line
- Contact info card (gray background)
- Bottom gray area (copyright, page number)

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
