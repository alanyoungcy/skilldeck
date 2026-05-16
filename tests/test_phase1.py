"""Phase 1 tests: glob filtering, content-aware writes, hybrid CV gate, PDF export gating."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from skilldeck_utils import (
    backup_if_exists,
    is_active_slide_file,
    list_active_slide_files,
    pdf_cache_is_fresh,
    resolve_pdf_export_flag,
    write_bytes_if_changed,
    write_pdf_cache,
    write_text_if_changed,
)


class GlobFilteringTests(unittest.TestCase):
    def test_active_files_exclude_backups(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01-slide-cover.md").write_text("a", encoding="utf-8")
            (root / "02-slide-content.md").write_text("b", encoding="utf-8")
            (root / "01-slide-cover-backup-20260101-120000.md").write_text("old", encoding="utf-8")
            (root / "02-slide-content-backup-20260101-120000.md").write_text("old", encoding="utf-8")
            (root / "outline.md").write_text("not a slide", encoding="utf-8")

            active = list_active_slide_files(root, ".md")

            self.assertEqual(
                [p.name for p in active],
                ["01-slide-cover.md", "02-slide-content.md"],
            )

    def test_chart_json_filtering(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01-slide-bar.chart.json").write_text("{}", encoding="utf-8")
            (root / "01-slide-bar-backup-20260101-120000.chart.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                [p.name for p in list_active_slide_files(root, ".chart.json")],
                ["01-slide-bar.chart.json"],
            )

    def test_png_svg_filtering(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01-slide-cover.png").write_bytes(b"png")
            (root / "01-slide-cover-backup-20260101-120000.png").write_bytes(b"old")
            (root / "02-slide-chart.svg").write_text("<svg/>", encoding="utf-8")
            (root / "02-slide-chart-backup-20260101-120000.svg").write_text("<svg/>", encoding="utf-8")
            self.assertEqual(
                [p.name for p in list_active_slide_files(root, ".png")],
                ["01-slide-cover.png"],
            )
            self.assertEqual(
                [p.name for p in list_active_slide_files(root, ".svg")],
                ["02-slide-chart.svg"],
            )

    def test_is_active_slide_file(self) -> None:
        self.assertTrue(is_active_slide_file(Path("01-slide-cover.png")))
        self.assertFalse(is_active_slide_file(Path("01-slide-cover-backup-20260101-120000.png")))


class ContentAwareWriteTests(unittest.TestCase):
    def test_text_write_creates_file(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "outline.md"
            self.assertTrue(write_text_if_changed(p, "hello"))
            self.assertEqual(p.read_text(encoding="utf-8"), "hello")

    def test_text_write_skips_when_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "outline.md"
            p.write_text("hello", encoding="utf-8")
            mtime_before = p.stat().st_mtime_ns
            self.assertFalse(write_text_if_changed(p, "hello"))
            self.assertEqual(p.stat().st_mtime_ns, mtime_before)
            backups = list(p.parent.glob("outline-backup-*.md"))
            self.assertEqual(backups, [])

    def test_text_write_backs_up_on_change(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "outline.md"
            p.write_text("v1", encoding="utf-8")
            self.assertTrue(write_text_if_changed(p, "v2"))
            self.assertEqual(p.read_text(encoding="utf-8"), "v2")
            backups = list(p.parent.glob("outline-backup-*.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "v1")

    def test_bytes_write_skips_when_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "img.png"
            p.write_bytes(b"\x00\x01\x02")
            mtime_before = p.stat().st_mtime_ns
            self.assertFalse(write_bytes_if_changed(p, b"\x00\x01\x02"))
            self.assertEqual(p.stat().st_mtime_ns, mtime_before)

    def test_bytes_write_backs_up_on_change(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "img.png"
            p.write_bytes(b"old")
            self.assertTrue(write_bytes_if_changed(p, b"new"))
            self.assertEqual(p.read_bytes(), b"new")
            backups = list(p.parent.glob("img-backup-*.png"))
            self.assertEqual(len(backups), 1)


class BackupHelperTests(unittest.TestCase):
    def test_backup_renames_existing(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "outline.md"
            p.write_text("hello", encoding="utf-8")
            backup_if_exists(p)
            self.assertFalse(p.exists())
            backups = list(p.parent.glob("outline-backup-*.md"))
            self.assertEqual(len(backups), 1)

    def test_backup_noop_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "missing.md"
            backup_if_exists(p)  # must not raise
            self.assertFalse(p.exists())


class PDFExportFlagTests(unittest.TestCase):
    def test_explicit_true_wins(self) -> None:
        with mock.patch.dict(os.environ, {"SKILLDECK_EXPORT_PDF": "0"}):
            self.assertTrue(resolve_pdf_export_flag(True))

    def test_explicit_false_wins(self) -> None:
        with mock.patch.dict(os.environ, {"SKILLDECK_EXPORT_PDF": "1"}):
            self.assertFalse(resolve_pdf_export_flag(False))

    def test_env_disabled_when_no_explicit(self) -> None:
        for v in ("0", "false", "no", "off"):
            with mock.patch.dict(os.environ, {"SKILLDECK_EXPORT_PDF": v}):
                self.assertFalse(resolve_pdf_export_flag(None))

    def test_env_enabled_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "SKILLDECK_EXPORT_PDF"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(resolve_pdf_export_flag(None))


class PDFCacheTests(unittest.TestCase):
    def test_cache_fresh_after_write(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            slug = "demo"
            (deck / f"{slug}.pptx").write_bytes(b"pptx-content")
            (deck / f"{slug}.pdf").write_bytes(b"pdf-content")
            write_pdf_cache(deck, slug)
            self.assertTrue(pdf_cache_is_fresh(deck, slug))

    def test_cache_stale_when_pptx_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            slug = "demo"
            (deck / f"{slug}.pptx").write_bytes(b"v1")
            (deck / f"{slug}.pdf").write_bytes(b"pdf")
            write_pdf_cache(deck, slug)
            (deck / f"{slug}.pptx").write_bytes(b"v2")
            self.assertFalse(pdf_cache_is_fresh(deck, slug))

    def test_cache_stale_when_pdf_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            slug = "demo"
            (deck / f"{slug}.pptx").write_bytes(b"pptx")
            (deck / f"{slug}.pdf").write_bytes(b"pdf")
            write_pdf_cache(deck, slug)
            (deck / f"{slug}.pdf").unlink()
            self.assertFalse(pdf_cache_is_fresh(deck, slug))

    def test_cache_stale_when_no_cache_file(self) -> None:
        with TemporaryDirectory() as tmp:
            deck = Path(tmp)
            slug = "demo"
            (deck / f"{slug}.pptx").write_bytes(b"pptx")
            (deck / f"{slug}.pdf").write_bytes(b"pdf")
            self.assertFalse(pdf_cache_is_fresh(deck, slug))


class HybridCVAssemblerTests(unittest.TestCase):
    """deck_assembler/_build_image_deck must skip the MinerU-token check when
    EDITABLE_PPTX_LAYOUT_ENGINE=hybrid_cv is active."""

    def test_hybrid_cv_does_not_require_mineru_token(self) -> None:
        from deck_assembler.merge import _build_image_deck

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            slide = tmp_path / "01-slide-cover.png"
            from PIL import Image as _Image
            _Image.new("RGB", (32, 18), (255, 255, 255)).save(slide, "PNG")

            env_patch = {
                "MINERU_TOKEN": "",
                "EDITABLE_PPTX_LAYOUT_ENGINE": "hybrid_cv",
                "EDITABLE_PPTX_HYBRID_MINERU_FALLBACK": "0",
            }
            captured: dict[str, object] = {}

            def fake_export(image_paths, mineru_dirs, out_pptx, *, bg_mode, deck_dir):
                captured["image_paths"] = list(image_paths)
                captured["mineru_dirs"] = list(mineru_dirs)
                Path(out_pptx).write_bytes(b"fake-pptx")

            with mock.patch.dict(os.environ, env_patch, clear=False), \
                 mock.patch("editable_pptx.assemble.export_editable_deck", side_effect=fake_export), \
                 mock.patch("editable_pptx.mineru.parse_slide_image") as parse_mock:
                _build_image_deck([slide], tmp_path / "out.pptx", tmp_path)
                parse_mock.assert_not_called()

            self.assertEqual(captured["mineru_dirs"], [None])

    def test_no_engine_set_still_requires_mineru(self) -> None:
        from deck_assembler.merge import _build_image_deck

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            slide = tmp_path / "01-slide-cover.png"
            from PIL import Image as _Image
            _Image.new("RGB", (32, 18), (255, 255, 255)).save(slide, "PNG")

            env_patch = {
                "MINERU_TOKEN": "",
                "EDITABLE_PPTX_LAYOUT_ENGINE": "mineru",
            }
            with mock.patch.dict(os.environ, env_patch, clear=False):
                with self.assertRaises(RuntimeError) as ctx:
                    _build_image_deck([slide], tmp_path / "out.pptx", tmp_path)
                self.assertIn("MINERU_TOKEN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
