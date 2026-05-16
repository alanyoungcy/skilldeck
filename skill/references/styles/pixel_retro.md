---
preset_id: "pixel_retro"
kind: "layout_template"
layout_dir: "templates/layouts/pixel_retro"
svg_templates:
  - "01_cover.svg"
  - "02_chapter.svg"
  - "02_toc.svg"
  - "03_content.svg"
  - "04_ending.svg"
assets: []
summary: "Tech talks, programming tutorials, game introductions, geek-style showcases."
keywords:
  - "Retro gaming"
  - "neon cyberpunk"
  - "geek tech"
  - "8-bit style"
render_policy: "prompt_guidance"
---
<!-- generated-by: migrate_layout_templates.py -->

# pixel_retro

Tech talks, programming tutorials, game introductions, geek-style showcases.

## Template Source

- Source layout: `templates/layouts/pixel_retro`
- Render policy: `prompt_guidance`
- Use these SVG files as composition references; do not require native SVG rendering.
- Keywords: Retro gaming, neon cyberpunk, geek tech, 8-bit style

## Best For

Tech talks, programming tutorials, game introductions, geek-style showcases.

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

| Property       | Description                                                |
| -------------- | ---------------------------------------------------------- |
| **Template Name** | pixel_retro (Pixel Retro Template)                      |
| **Use Cases**  | Tech talks, programming tutorials, game introductions, geek-style showcases |
| **Design Tone** | Retro gaming, neon cyberpunk, geek tech, 8-bit style      |
| **Theme Mode** | Dark theme (deep space black background + neon accents)    |

---

## Color Palette

## III. Color Scheme

### Background Colors

| Role           | Value       | Notes                            |
| -------------- | ----------- | -------------------------------- |
| **Deep Space Black** | `#0D1117` | Main background color          |
| **Starry Night Blue** | `#161B22` | Card/block background         |
| **Dark Border** | `#30363D`  | Borders/dividers                 |

### Accent Colors (Neon Series)

| Role           | Value       | Usage                            |
| -------------- | ----------- | -------------------------------- |
| **Neon Green** | `#39FF14`   | Primary accent, success, save points, Git |
| **Cyber Pink** | `#FF2E97`   | Secondary accent, warnings, contrast, GitHub |
| **Electric Blue** | `#00D4FF` | Tertiary accent, links, info, flows |
| **Gold Yellow** | `#FFD700`  | Quaternary accent, history, timelines, highlights |

### Auxiliary Colors

| Role           | Value       | Usage                            |
| -------------- | ----------- | -------------------------------- |
| **Dark Green** | `#238636`   | Muted version of success state   |
| **Dark Pink**  | `#8B2252`   | Muted pink                       |
| **Dark Blue**  | `#1F6FEB`   | Muted blue                       |

### Text Colors

| Role           | Value       | Usage                  |
| -------------- | ----------- | ---------------------- |
| **Moonlight White** | `#E6EDF3` | Primary text         |
| **Mist Gray**  | `#8B949E`   | Secondary descriptive text |
| **Pure White** | `#FFFFFF`   | Emphasized titles      |

---

## Typography

## IV. Typography System

### Font Stack

**Title Font**: `"Consolas", "Monaco", "Courier New", monospace` - Pixel/code aesthetic

**Body Font**: `-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif`

**Code Font**: `"Cascadia Code", "Fira Code", "Consolas", monospace`

### Font Size Hierarchy

| Level | Usage              | Size | Weight  |
| ----- | ------------------ | ---- | ------- |
| H1    | Cover main title   | 52px | Bold    |
| H2    | Page heading       | 36px | Bold    |
| H3    | Section title/Subtitle | 22px | 600  |
| P     | Body content       | 18px | Regular |
| High  | Highlighted data   | 48px | Bold    |
| Sub   | Supplementary text | 14px | Regular |
| Code  | Code text          | 16px | Regular |

---

## Layout Principles

## V. Page Structure

### General Layout

| Area       | Position/Height | Description                            |
| ---------- | --------------- | -------------------------------------- |
| **Top**    | y=0, h=4-6px    | Neon green decoration line (dual-line effect) |
| **Title Area** | y=50, h=70px | Page title + English subtitle         |
| **Content Area** | y=130, h=510px | Main content area                  |
| **Footer** | y=680, h=40px   | Page number, decoration line, progress indicator |

### Decorative Elements

- **Top Decoration Line**: Neon green dual lines (main line 4px + auxiliary line 2px)
- **Bottom Decoration Line**: Neon green dual lines (auxiliary line 4px + main line 4px)
- **Pixel Blocks**: Corner decorations with decreasing opacity (100% → 60% → 30%)
- **Scanline Grid**: Optional low-opacity background grid lines

---

## Page Roles

## VI. Page Types

### 1. Cover Page (01_cover.svg)

- Deep space black background
- Top/bottom neon decoration lines
- Pixel-style console graphic (optional)
- Main title (neon green glow effect)
- Subtitle (moonlight white)
- Function button group (horizontal layout)
- Bottom prompt text (e.g., "PRESS START")

### 2. Table of Contents (02_toc.svg)

- Deep space black background
- Standard top decoration
- Chapter list (with importance labels)
  - Red: Essential / Must-learn
  - Yellow: Recommended
  - Green: Optional
- Pixel-style list design

### 3. Chapter Page (02_chapter.svg)

- Deep space black background
- Full-screen neon effect
- Large chapter number (glow effect)
- Chapter title + English subtitle
- Pixel-style decorative frame

### 4. Content Page (03_content.svg)

- Deep space black background
- Standard top decoration
- Page title (neon green + glow)
- English subtitle (mist gray)
- **Fully open content area** (y=140 to y=670, width 1160px)
- Bottom page number

> **Design Principle**: The content page template only provides the page frame (title area + footer). The content area is freely designed by the Executor based on actual content. Available layouts include but are not limited to: cards, progress bars, tables, timelines, comparison charts, etc.

### 5. Ending Page (04_ending.svg)

- Deep space black background
- Neon glow main title
- Summary card group
- "GAME SAVED" visual effect
- Progress button group

---

## Style Rules

### Do

- Treat the markdown design spec as authoritative style guidance.
- Use the SVG roster to infer cover, section, content, and ending composition patterns.
- Keep generated image/chart slides compatible with the current skilldeck pipeline.

### Don't

- Do not edit, render, or require the SVG templates during this metadata-bridge phase.
- Do not override source content just to match a template placeholder.
