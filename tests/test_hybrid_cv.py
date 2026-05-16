from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from editable_pptx.cv_detect import cv2_available, detect_candidates
from editable_pptx.hybrid import analyze_slide_hybrid


@unittest.skipUnless(cv2_available(), "opencv-python-headless is not installed")
class HybridCVTests(unittest.TestCase):
    def test_detects_multiple_card_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "cards.png"
            im = Image.new("RGB", (1000, 560), "white")
            draw = ImageDraw.Draw(im)
            for i in range(5):
                x0 = 70 + i * 180
                draw.rounded_rectangle((x0, 180, x0 + 130, 330), radius=18, fill=(235, 242, 255), outline=(60, 100, 180), width=3)
            im.save(image_path)

            candidates, bg = detect_candidates(image_path, min_area_fraction=0.002)

            card_like = [c for c in candidates if c.kind in {"rect", "roundRect"} and 10000 <= _area(c.bbox) <= 30000]
            self.assertGreaterEqual(len(card_like), 5)
            self.assertGreater(bg[0], 240)
            self.assertGreater(bg[1], 240)
            self.assertGreater(bg[2], 240)

    def test_hybrid_analyzer_keeps_cards_as_separate_shapes_without_vlm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "cards.png"
            im = Image.new("RGB", (1000, 560), "white")
            draw = ImageDraw.Draw(im)
            for i in range(5):
                x0 = 70 + i * 180
                draw.rounded_rectangle((x0, 180, x0 + 130, 330), radius=18, fill=(235, 242, 255), outline=(60, 100, 180), width=3)
            im.save(image_path)

            elements, shapes, page_bg, debug = analyze_slide_hybrid(
                str(image_path),
                mineru_dir=None,
                min_area_fraction=0.002,
                recursion_depth=1,
            )

            self.assertEqual(elements, [])
            self.assertGreaterEqual(len(shapes), 5)
            self.assertEqual(debug["engine"], "hybrid_cv")
            self.assertIsNotNone(page_bg)


def _area(bbox: list[float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


if __name__ == "__main__":
    unittest.main()
