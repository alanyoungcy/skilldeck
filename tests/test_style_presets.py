from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from notebooklm_style_agent.refs import list_style_presets, load_style_preset_text


REPO_DIR = Path(__file__).resolve().parents[1]
MIGRATION_SCRIPT = REPO_DIR / "skill" / "scripts" / "migrate_layout_templates.py"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("migrate_layout_templates", MIGRATION_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StylePresetTests(unittest.TestCase):
    def test_plain_markdown_presets_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            styles = skill_dir / "references" / "styles"
            styles.mkdir(parents=True)
            (styles / "blueprint.md").write_text("# blueprint\n\nGrid style.", encoding="utf-8")

            presets = list_style_presets(skill_dir)

            self.assertEqual([p.name for p in presets], ["blueprint"])
            self.assertEqual(presets[0].kind, "markdown")
            self.assertEqual(load_style_preset_text(skill_dir, "blueprint"), "# blueprint\n\nGrid style.")

    def test_layout_backed_preset_loads_svg_metadata_and_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            styles = skill_dir / "references" / "styles"
            layout_dir = skill_dir / "templates" / "layouts" / "anthropic"
            styles.mkdir(parents=True)
            layout_dir.mkdir(parents=True)
            (layout_dir / "01_cover.svg").write_text("<svg />", encoding="utf-8")
            (styles / "anthropic.md").write_text(
                """---
preset_id: "anthropic"
kind: "layout_template"
layout_dir: "templates/layouts/anthropic"
svg_templates:
  - "01_cover.svg"
  - "03_content.svg"
assets: []
summary: "AI talks."
keywords:
  - "technical"
render_policy: "prompt_guidance"
---
# anthropic

Use the Anthropic template style.
""",
                encoding="utf-8",
            )

            preset = list_style_presets(skill_dir)[0]
            loaded = load_style_preset_text(skill_dir, "anthropic")

            self.assertTrue(preset.is_layout_template)
            self.assertEqual(preset.label, "anthropic · SVG layout pack")
            self.assertEqual(preset.layout_dir, layout_dir)
            self.assertEqual(preset.svg_templates, ("01_cover.svg", "03_content.svg"))
            self.assertIn("## SVG Layout Guidance", loaded)
            self.assertIn("`01_cover.svg`: cover page reference", loaded)
            self.assertIn("`03_content.svg`: content page reference (missing; use markdown guidance only)", loaded)

    def test_migration_creates_specs_for_english_and_chinese_templates(self) -> None:
        module = load_migration_module()
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            layouts = skill_dir / "templates" / "layouts"
            styles = skill_dir / "references" / "styles"
            for layout_id in ("anthropic", "招商银行"):
                d = layouts / layout_id
                d.mkdir(parents=True)
                (d / "design_spec.md").write_text(
                    f"""# {layout_id} Template

> Summary for {layout_id}.

## I. Template Overview

| Property | Description |
| --- | --- |
| **Use Cases** | Demo |
| **Design Tone** | Structured |

## III. Color Scheme

- Primary: #123456

## IV. Typography System

- Font Stack: Arial

## V. Page Structure

- Content area is flexible.

## VI. Page Types

- Cover Page (`01_cover.svg`)
- Content Page (`03_content.svg`)
""",
                    encoding="utf-8",
                )
                (d / "01_cover.svg").write_text("<svg />", encoding="utf-8")
                (d / "03_content.svg").write_text("<svg />", encoding="utf-8")
            layouts.mkdir(parents=True, exist_ok=True)
            (layouts / "layouts_index.json").write_text(
                '{"anthropic": {"summary": "AI talks.", "keywords": ["modern"]}, '
                '"招商银行": {"summary": "Banking.", "keywords": ["finance"]}}',
                encoding="utf-8",
            )
            styles.mkdir(parents=True)
            (styles / "anthropic.md").write_text("# existing\n", encoding="utf-8")

            messages = module.migrate(skill_dir=skill_dir, only={"anthropic", "招商银行"})

            self.assertIn("CREATE anthropic: references/styles/anthropic-template.md", messages)
            self.assertIn("CREATE 招商银行: references/styles/招商银行.md", messages)
            anthropic = (styles / "anthropic-template.md").read_text(encoding="utf-8")
            cmb = (styles / "招商银行.md").read_text(encoding="utf-8")
            self.assertIn('preset_id: "anthropic-template"', anthropic)
            self.assertIn("Use these SVG files as composition references", anthropic)
            self.assertIn('preset_id: "招商银行"', cmb)
            self.assertIn("03_content.svg", cmb)


if __name__ == "__main__":
    unittest.main()
