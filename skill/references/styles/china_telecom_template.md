---
preset_id: "china_telecom_template"
kind: "layout_template"
layout_dir: "templates/layouts/china_telecom_template"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets:
  - "footer_ribbon.png"
  - "header_brand.png"
  - "logo.png"
  - "skyline_bg.png"
  - "slogan_red.png"
  - "top_emblem.png"
summary: "China Telecom related briefings, 政企数字化方案, 转型规划, 内部汇报."
keywords:
  - "Authoritative"
  - "structured"
  - "restrained"
  - "enterprise-government hybrid"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# china_telecom_template

China Telecom related briefings, 政企数字化方案, 转型规划, 内部汇报.

## Template Source

- Source layout: `templates/layouts/china_telecom_template`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Authoritative, structured, restrained, enterprise-government hybrid

## Best For

China Telecom related briefings, 政企数字化方案, 转型规划, 内部汇报.

## SVG Template Roster

- `01_cover.svg`
- `02_chapter.svg`
- `02_toc.svg`
- `03_content.svg`
- `04_ending.svg`

## Template Assets

- `footer_ribbon.png`
- `header_brand.png`
- `logo.png`
- `skyline_bg.png`
- `slogan_red.png`
- `top_emblem.png`

## Design Aesthetic

## I. Template Overview

| Property | Description |
| --- | --- |
| **Template Name** | `china_telecom_template` (`中国电信模板`) |
| **Use Cases** | China Telecom related briefings, 政企数字化方案, 转型规划, 内部汇报 |
| **Design Tone** | Authoritative, structured, restrained, enterprise-government hybrid |
| **Theme Mode** | Light theme (white background + telecom red title bar + silver-gray structural lane + restrained brand imagery) |

---

## Color Palette

## III. Color Scheme

### Primary Colors

| Role | Value | Notes |
| --- | --- | --- |
| **Telecom Red** | `#C00000` | Main header blocks, numbering, emphasis |
| **Light Silver Gray** | `#D9D9D9` | Structural lane, chapter ribbon backing |
| **Warm White** | `#FFFFFF` | Main background |
| **Line Gray** | `#CFCFCF` | Divider lines and subtle frames |
| **Graphite** | `#2B2F33` | Primary text |

### Secondary Colors

| Role | Value | Notes |
| --- | --- | --- |
| **Muted Gray** | `#6B7280` | Secondary text and descriptions |
| **Soft Red** | `#E55B5B` | Auxiliary emphasis |
| **Near Black** | `#111827` | Key headings |
| **Skyline Blue** | `#DCEAF8` | Decorative cityline / digital texture |

---

## Typography

## IV. Typography System

### Font Stack

`"Microsoft YaHei", "微软雅黑", "PingFang SC", "Source Han Sans SC", Arial, sans-serif`

### Font Size Hierarchy

| Level | Usage | Size | Weight |
| --- | --- | --- | --- |
| H1 | Cover title | 42px | Bold |
| H2 | Chapter / content title | 28px | Bold |
| H3 | Section label / TOC item | 20px | Bold |
| P | Body text | 16px | Regular |
| Meta | Subtitle / annotations | 13px | Regular |
| Number | TOC / chapter index | 30px | Bold |

---

## Layout Principles

## V. Page Structure

### General Layout

| Area | Position | Description |
| --- | --- | --- |
| **Logo Area** | x=72, y=36 | Fixed top-left brand logo |
| **Header Ribbon** | y=32 to 96 | Red capsule + gray lane for TOC/content pages |
| **Main Content Area** | y=132 to 618 | Main text/layout body |
| **Visual Sidebar** | x=922 to 1208 | Fixed image-only rail on cover / TOC / chapter / ending pages |
| **Footer Ribbon** | y=548 to 720 | Fixed decorative bottom image area on cover/ending |
| **Footer Meta** | y=650 to 690 | Source / page number / contact info |

### Structural Rules

- Cover and ending pages reuse the image-based footer ribbon to preserve the brand atmosphere.
- TOC and content pages use dedicated visual sidebars/cards for imagery, keeping text and images in separate safe zones.
- Chapter pages are cleaner section-divider pages and should not inherit the content-page header ribbon.
- Each page should contain at most one formal logo mark; sidebars should rely on slogan and skyline imagery instead of repeated logo lockups.
- The content page remains open-canvas by default and should not reserve a large fixed sidebar.

---

## Page Roles

## VI. Page Types

### 1. Cover Page (`01_cover.svg`)

- Top-left fixed logo
- Left-aligned title cluster with red accent rule
- Right-side visual card containing slogan and skyline imagery
- Bottom full-width ribbon background

### 2. Table of Contents (`02_toc.svg`)

- Red rounded title capsule + gray structural lane
- Top-right compact logo for page-level brand anchoring
- Left visual card with restrained brand imagery
- Right text list area for up to 4 major sections
- Dotted leaders and right-aligned descriptions

### 3. Chapter Page (`02_chapter.svg`)

- Clean section-divider page without the content-page header ribbon
- Top-right compact logo anchored away from the title area
- Large chapter number and title in the left safe zone
- Right-side visual card with fixed imagery and no duplicated large logo
- Footer ribbon used as a restrained anchor

### 4. Content Page (`03_content.svg`)

- Red section tab at top-left, gray lane at top-right
- Top-right compact logo for page-level brand anchoring
- Open-canvas content area for flexible charts, tables, and mixed layouts
- Only keep lightweight corner / footer-level brand control
- Footer source and page number

### 5. Ending Page (`04_ending.svg`)

- White background
- Left closing statement block
- Right closing visual card with restrained skyline / slogan composition
- Full-width footer ribbon

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
