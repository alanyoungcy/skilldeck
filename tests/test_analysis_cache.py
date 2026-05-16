"""Tests for editable_pptx.analysis_cache."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from editable_pptx import analysis_cache


def _make_image(path: Path, color=(255, 255, 255), size=(640, 360)) -> None:
    Image.new("RGB", size, color).save(path, "PNG")


class CacheKeyTests(unittest.TestCase):
    def test_key_changes_when_image_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = tmp_path / "a.png"
            b = tmp_path / "b.png"
            _make_image(a, (255, 255, 255))
            _make_image(b, (0, 0, 0))
            ka = analysis_cache.cache_key(
                image_path=str(a), vlm_model="m1", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            kb = analysis_cache.cache_key(
                image_path=str(b), vlm_model="m1", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            self.assertNotEqual(ka, kb)

    def test_key_changes_when_decompose_flag_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = tmp_path / "a.png"
            _make_image(a)
            k_on = analysis_cache.cache_key(
                image_path=str(a), vlm_model="m1", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            k_off = analysis_cache.cache_key(
                image_path=str(a), vlm_model="m1", decompose_enabled=False,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            self.assertNotEqual(k_on, k_off)

    def test_key_changes_when_vlm_model_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = tmp_path / "a.png"
            _make_image(a)
            k1 = analysis_cache.cache_key(
                image_path=str(a), vlm_model="gpt-4o", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            k2 = analysis_cache.cache_key(
                image_path=str(a), vlm_model="claude-opus-4-7", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            self.assertNotEqual(k1, k2)

    def test_key_stable_for_same_inputs(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            a = tmp_path / "a.png"
            _make_image(a)
            k1 = analysis_cache.cache_key(
                image_path=str(a), vlm_model="m1", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            k2 = analysis_cache.cache_key(
                image_path=str(a), vlm_model="m1", decompose_enabled=True,
                decompose_min_area_fraction=0.05, layout_engine="mineru",
            )
            self.assertEqual(k1, k2)


class CacheRoundtripTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            stem = "01-slide-cover"
            path = analysis_cache.cache_path(deck, stem)
            assert path is not None
            key = "test-key"
            analysis_cache.save(
                path, key,
                page_bg=(250, 248, 245),
                styles=[{"i": 0, "bold": False, "align": "left"}],
                shapes=[{"kind": "rect", "bbox": [10, 20, 30, 40]}],
                decompose_extra_shapes=[{"kind": "roundRect", "bbox": [50, 60, 70, 80]}],
                decompose_extra_texts=[{"bbox": [50, 60, 70, 80], "type": "text", "content": "Plan"}],
                decompose_removed_indices=[3],
            )
            loaded = analysis_cache.load(path, key)
            assert loaded is not None
            self.assertEqual(loaded["page_bg"], [250, 248, 245])
            self.assertEqual(len(loaded["styles"]), 1)
            self.assertEqual(loaded["shapes"][0]["kind"], "rect")
            self.assertEqual(loaded["decompose"]["removed_indices"], [3])
            self.assertEqual(loaded["decompose"]["extra_texts"][0]["content"], "Plan")

    def test_load_returns_none_on_key_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            path = analysis_cache.cache_path(deck, "01-slide-cover")
            assert path is not None
            analysis_cache.save(
                path, "key-A",
                page_bg=None, styles=[], shapes=[],
                decompose_extra_shapes=[], decompose_extra_texts=[],
                decompose_removed_indices=[],
            )
            self.assertIsNone(analysis_cache.load(path, "key-B"))

    def test_load_returns_none_on_missing_file(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            self.assertIsNone(analysis_cache.load(path, "anything"))

    def test_load_returns_none_on_corrupt_json(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrupt.json"
            path.write_text("{ this is not json", encoding="utf-8")
            self.assertIsNone(analysis_cache.load(path, "anything"))

    def test_load_returns_none_on_old_version(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.json"
            path.write_text(
                json.dumps({"version": 0, "key": "x"}), encoding="utf-8",
            )
            self.assertIsNone(analysis_cache.load(path, "x"))

    def test_cache_path_returns_none_when_no_deck_dir(self) -> None:
        self.assertIsNone(analysis_cache.cache_path(None, "01-slide-cover"))

    def test_cache_save_creates_cache_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            path = analysis_cache.cache_path(deck, "01-slide-cover")
            assert path is not None
            self.assertFalse(path.parent.exists())
            analysis_cache.save(
                path, "k",
                page_bg=None, styles=[], shapes=[],
                decompose_extra_shapes=[], decompose_extra_texts=[],
                decompose_removed_indices=[],
            )
            self.assertTrue(path.parent.is_dir())
            self.assertTrue(path.is_file())


class StyleSeparationTests(unittest.TestCase):
    """compute_openai_element_styles must NOT mutate elements;
    apply_styles_to_elements is the only mutator."""

    def test_apply_styles_attaches_style_dict(self) -> None:
        from editable_pptx.openai_style import apply_styles_to_elements

        elements = [
            {"bbox": [0, 0, 100, 30], "type": "title", "content": "Hello", "image_path": None},
            {"bbox": [0, 40, 100, 80], "type": "text", "content": "Body", "image_path": None},
            {"bbox": [10, 10, 80, 80], "type": "image", "content": None, "image_path": "/tmp/x.png"},
        ]
        styles = [
            {"bold": True, "italic": False, "align": "center"},
            {"bold": False, "italic": True, "align": "left"},
        ]
        apply_styles_to_elements(elements, styles)
        # First two text elements get styles; the image element does not.
        self.assertEqual(elements[0]["style"], styles[0])
        self.assertEqual(elements[1]["style"], styles[1])
        self.assertNotIn("style", elements[2])


if __name__ == "__main__":
    unittest.main()
