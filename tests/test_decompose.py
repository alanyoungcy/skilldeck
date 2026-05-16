"""Tests for editable_pptx.decompose (multi-box diagram VLM pass)."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from editable_pptx import decompose


# Slide dimensions used by every test.
SLIDE_W, SLIDE_H = 1920, 1080
SLIDE_SIZE = (SLIDE_W, SLIDE_H)


def _diagram_element(bbox: list[float] | None = None) -> dict:
    """Helper: a 'figure' element covering ~40% of the slide by default."""
    return {
        "bbox": bbox if bbox is not None else [200.0, 100.0, 1500.0, 800.0],
        "type": "figure",
        "content": None,
        "image_path": "/tmp/fake-region.png",
        "metadata": {},
    }


class CoordinateProjectionTests(unittest.TestCase):
    def test_project_inside_region(self) -> None:
        # Region 100..500 (w=400), 200..600 (h=400). Norm bbox 0.1..0.4, 0.2..0.5.
        bbox = decompose._project_bbox(
            [0.1, 0.2, 0.4, 0.5],
            region_bbox=[100.0, 200.0, 500.0, 600.0],
            crop_w=400,
            crop_h=400,
        )
        assert bbox is not None
        x0, y0, x1, y1 = bbox
        self.assertAlmostEqual(x0, 140.0, places=3)
        self.assertAlmostEqual(y0, 280.0, places=3)
        self.assertAlmostEqual(x1, 260.0, places=3)
        self.assertAlmostEqual(y1, 400.0, places=3)

    def test_project_clamps_to_unit_box(self) -> None:
        bbox = decompose._project_bbox(
            [-0.1, -0.1, 1.2, 1.2],
            region_bbox=[0.0, 0.0, 100.0, 100.0],
            crop_w=100,
            crop_h=100,
        )
        assert bbox is not None
        self.assertEqual(bbox, [0.0, 0.0, 100.0, 100.0])

    def test_project_rejects_inverted_bbox(self) -> None:
        self.assertIsNone(
            decompose._project_bbox([0.5, 0.5, 0.4, 0.4], [0, 0, 100, 100], 100, 100)
        )

    def test_project_rejects_malformed(self) -> None:
        self.assertIsNone(decompose._project_bbox(None, [0, 0, 100, 100], 100, 100))
        self.assertIsNone(decompose._project_bbox([0.0, 0.0, 1.0], [0, 0, 100, 100], 100, 100))


class GuardTests(unittest.TestCase):
    def test_returns_empty_when_vlm_disabled(self) -> None:
        with mock.patch.object(decompose, "vlm_enabled", return_value=False):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [_diagram_element()], SLIDE_SIZE
            )
        self.assertEqual(shapes, [])
        self.assertEqual(texts, [])
        self.assertEqual(removed, [])

    def test_returns_empty_when_no_elements(self) -> None:
        with mock.patch.object(decompose, "vlm_enabled", return_value=True):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [], SLIDE_SIZE
            )
        self.assertEqual((shapes, texts, removed), ([], [], []))

    def test_skips_text_elements(self) -> None:
        text_el = {
            "bbox": [0.0, 0.0, 1920.0, 1080.0],  # full-slide text — must be ignored
            "type": "text",
            "content": "headline",
            "image_path": None,
            "metadata": {},
        }
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region") as call_mock:
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [text_el], SLIDE_SIZE
            )
        call_mock.assert_not_called()
        self.assertEqual((shapes, texts, removed), ([], [], []))

    def test_skips_small_regions(self) -> None:
        # 100x100 region = 10000 px. Slide is 1920x1080 = 2,073,600 px.
        # Fraction = 0.0048, below default min_area_fraction=0.05.
        small = _diagram_element([0.0, 0.0, 100.0, 100.0])
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region") as call_mock:
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [small], SLIDE_SIZE, min_area_fraction=0.05
            )
        call_mock.assert_not_called()
        self.assertEqual(removed, [])

    def test_lower_min_area_fraction_picks_up_small_region(self) -> None:
        small = _diagram_element([0.0, 0.0, 100.0, 100.0])
        fake_items = [
            {
                "kind": "shape", "shape_kind": "rect", "bbox": [0.0, 0.0, 1.0, 1.0],
                "stroke_width_px": 2, "z": "under", "text": "ok", "confidence": 0.9,
            }
        ]
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=fake_items):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [small], SLIDE_SIZE, min_area_fraction=0.001
            )
        self.assertEqual(len(shapes), 1)
        self.assertEqual(len(texts), 1)
        self.assertEqual(removed, [0])


class DecompositionTests(unittest.TestCase):
    """End-to-end: a 4-box diagram returns 4 shapes + 4 labels + 1 removed."""

    def _four_box_response(self) -> list[dict]:
        return [
            {
                "kind": "shape", "shape_kind": "roundRect",
                "bbox": [0.05, 0.10, 0.45, 0.45],
                "fill_rgb": [240, 240, 240], "stroke_rgb": [80, 80, 80],
                "stroke_width_px": 2, "corner_radius_px": 8, "z": "under",
                "text": "Plan", "confidence": 0.92,
            },
            {
                "kind": "shape", "shape_kind": "roundRect",
                "bbox": [0.55, 0.10, 0.95, 0.45],
                "fill_rgb": [240, 240, 240], "stroke_rgb": [80, 80, 80],
                "stroke_width_px": 2, "corner_radius_px": 8, "z": "under",
                "text": "Build", "confidence": 0.91,
            },
            {
                "kind": "shape", "shape_kind": "roundRect",
                "bbox": [0.05, 0.55, 0.45, 0.90],
                "fill_rgb": [240, 240, 240], "stroke_rgb": [80, 80, 80],
                "stroke_width_px": 2, "corner_radius_px": 8, "z": "under",
                "text": "Test", "confidence": 0.90,
            },
            {
                "kind": "shape", "shape_kind": "roundRect",
                "bbox": [0.55, 0.55, 0.95, 0.90],
                "fill_rgb": [240, 240, 240], "stroke_rgb": [80, 80, 80],
                "stroke_width_px": 2, "corner_radius_px": 8, "z": "under",
                "text": "Ship", "confidence": 0.93,
            },
        ]

    def test_four_box_diagram_decomposes(self) -> None:
        diagram = _diagram_element([200.0, 100.0, 1500.0, 800.0])
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(
                 decompose, "_call_vlm_for_region",
                 return_value=self._four_box_response(),
             ):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual(len(shapes), 4)
        self.assertEqual(len(texts), 4)
        self.assertEqual(removed, [0])
        # All decomposed shapes must be projected into the diagram region's bbox.
        for sh in shapes:
            x0, y0, x1, y1 = sh["bbox"]
            self.assertGreaterEqual(x0, 200.0 - 0.5)
            self.assertGreaterEqual(y0, 100.0 - 0.5)
            self.assertLessEqual(x1, 1500.0 + 0.5)
            self.assertLessEqual(y1, 800.0 + 0.5)
            self.assertEqual(sh["source"], "diagram_decompose")
        # All text elements have non-empty content.
        for tx in texts:
            self.assertTrue(tx["content"].strip())
            self.assertEqual(tx["type"], "text")
            self.assertIsNone(tx["image_path"])

    def test_standalone_text_items(self) -> None:
        """A 'kind=text' item produces a text element, no shape."""
        diagram = _diagram_element()
        items = [
            {
                "kind": "text", "bbox": [0.1, 0.1, 0.5, 0.2],
                "text": "Caption", "confidence": 0.85,
            }
        ]
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=items):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual(shapes, [])
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0]["content"], "Caption")
        self.assertEqual(removed, [0])

    def test_low_confidence_items_filtered(self) -> None:
        diagram = _diagram_element()
        items = [
            {
                "kind": "shape", "shape_kind": "rect", "bbox": [0.1, 0.1, 0.5, 0.5],
                "stroke_width_px": 1, "z": "under", "confidence": 0.10,
            },
            {
                "kind": "shape", "shape_kind": "rect", "bbox": [0.5, 0.5, 0.9, 0.9],
                "stroke_width_px": 1, "z": "under", "confidence": 0.95,
            },
        ]
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=items):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual(len(shapes), 1)
        self.assertEqual(removed, [0])

    def test_empty_vlm_result_keeps_bitmap(self) -> None:
        diagram = _diagram_element()
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=[]):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual((shapes, texts, removed), ([], [], []))

    def test_invalid_shape_kind_dropped(self) -> None:
        diagram = _diagram_element()
        items = [
            {
                "kind": "shape", "shape_kind": "weird-thing",
                "bbox": [0.1, 0.1, 0.5, 0.5], "z": "under", "confidence": 0.9,
            }
        ]
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=items):
            shapes, texts, removed = decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual((shapes, texts, removed), ([], [], []))

    def test_does_not_mutate_input_elements(self) -> None:
        diagram = _diagram_element()
        original = dict(diagram)
        items = [
            {
                "kind": "shape", "shape_kind": "rect", "bbox": [0.1, 0.1, 0.5, 0.5],
                "z": "under", "confidence": 0.9, "text": "x",
            }
        ]
        with mock.patch.object(decompose, "vlm_enabled", return_value=True), \
             mock.patch.object(decompose, "_call_vlm_for_region", return_value=items):
            decompose.decompose_image_regions(
                "/tmp/fake.png", [diagram], SLIDE_SIZE,
            )
        self.assertEqual(diagram, original)


class EnvFlagTests(unittest.TestCase):
    def test_decompose_enabled_default_on_when_vlm_enabled(self) -> None:
        from editable_pptx import env as env_mod
        with mock.patch.object(env_mod, "vlm_enabled", return_value=True), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDITABLE_PPTX_DECOMPOSE_DIAGRAMS", None)
            self.assertTrue(env_mod.diagram_decompose_enabled())

    def test_decompose_disabled_when_flag_zero(self) -> None:
        from editable_pptx import env as env_mod
        with mock.patch.object(env_mod, "vlm_enabled", return_value=True), \
             mock.patch.dict(os.environ, {"EDITABLE_PPTX_DECOMPOSE_DIAGRAMS": "0"}):
            self.assertFalse(env_mod.diagram_decompose_enabled())

    def test_decompose_disabled_when_vlm_disabled(self) -> None:
        from editable_pptx import env as env_mod
        with mock.patch.object(env_mod, "vlm_enabled", return_value=False), \
             mock.patch.dict(os.environ, {"EDITABLE_PPTX_DECOMPOSE_DIAGRAMS": "1"}):
            self.assertFalse(env_mod.diagram_decompose_enabled())

    def test_min_area_fraction_clamped(self) -> None:
        from editable_pptx import env as env_mod
        with mock.patch.dict(os.environ, {"EDITABLE_PPTX_DECOMPOSE_MIN_AREA_FRACTION": "1.5"}):
            self.assertEqual(env_mod.diagram_decompose_min_area_fraction(), 1.0)
        with mock.patch.dict(os.environ, {"EDITABLE_PPTX_DECOMPOSE_MIN_AREA_FRACTION": "-0.5"}):
            self.assertEqual(env_mod.diagram_decompose_min_area_fraction(), 0.0)
        with mock.patch.dict(os.environ, {"EDITABLE_PPTX_DECOMPOSE_MIN_AREA_FRACTION": "not-a-number"}):
            self.assertEqual(env_mod.diagram_decompose_min_area_fraction(), 0.05)


if __name__ == "__main__":
    unittest.main()
