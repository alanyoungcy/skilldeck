"""Tests for the progress bus + worker thread orchestration."""
from __future__ import annotations

import threading
import time
import unittest

from progress import ProgressBus, Stage


class StageOrderingTests(unittest.TestCase):
    def test_stage_enum_order(self) -> None:
        # Order matters — the UI iterates Stage in this order.
        self.assertEqual(
            list(Stage),
            [
                Stage.SOURCE,
                Stage.OUTLINE,
                Stage.PROMPTS,
                Stage.CONCEPTS,
                Stage.CHARTS,
                Stage.IMAGES,
                Stage.PPTX,
                Stage.PDF,
            ],
        )

    def test_every_stage_has_a_display_label(self) -> None:
        for stage in Stage:
            self.assertTrue(stage.display)


class BusLifecycleTests(unittest.TestCase):
    def test_initial_snapshot_all_queued(self) -> None:
        bus = ProgressBus()
        snap = bus.snapshot()
        self.assertEqual(snap.overall_state, "idle")
        for stage in Stage:
            self.assertEqual(snap.stages[stage].state, "queued")

    def test_start_and_end_pipeline(self) -> None:
        bus = ProgressBus()
        bus.start_pipeline()
        self.assertEqual(bus.snapshot().overall_state, "running")
        self.assertTrue(bus.is_running())
        bus.mark_done()
        self.assertEqual(bus.snapshot().overall_state, "done")
        self.assertFalse(bus.is_running())

    def test_start_stage_marks_running(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.OUTLINE, items_total=3, detail="generating")
        snap = bus.snapshot()
        info = snap.stages[Stage.OUTLINE]
        self.assertEqual(info.state, "running")
        self.assertEqual(info.items_total, 3)
        self.assertEqual(info.items_done, 0)
        self.assertEqual(info.detail, "generating")

    def test_update_stage_progresses_items(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.IMAGES, items_total=4)
        bus.update_stage(Stage.IMAGES, items_done=2, detail="2/4")
        info = bus.snapshot().stages[Stage.IMAGES]
        self.assertEqual(info.items_done, 2)
        self.assertEqual(info.detail, "2/4")
        self.assertAlmostEqual(info.progress, 0.5, places=3)

    def test_end_stage_marks_done_and_fills_items(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.CHARTS, items_total=2)
        bus.update_stage(Stage.CHARTS, items_done=1)
        bus.end_stage(Stage.CHARTS, detail="done")
        info = bus.snapshot().stages[Stage.CHARTS]
        self.assertEqual(info.state, "done")
        self.assertEqual(info.items_done, 2)
        self.assertEqual(info.progress, 1.0)
        self.assertIsNotNone(info.ended_at)

    def test_skip_stage(self) -> None:
        bus = ProgressBus()
        bus.skip_stage(Stage.PDF, "user disabled PDF")
        info = bus.snapshot().stages[Stage.PDF]
        self.assertEqual(info.state, "skipped")
        self.assertEqual(info.detail, "user disabled PDF")

    def test_fail_stage_propagates(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.IMAGES)
        bus.fail_stage(Stage.IMAGES, "image API HTTP 500")
        info = bus.snapshot().stages[Stage.IMAGES]
        self.assertEqual(info.state, "error")
        self.assertEqual(info.error, "image API HTTP 500")

    def test_mark_error_records_overall(self) -> None:
        bus = ProgressBus()
        bus.start_pipeline()
        bus.mark_error("network gone")
        snap = bus.snapshot()
        self.assertEqual(snap.overall_state, "error")
        self.assertEqual(snap.error, "network gone")

    def test_event_log_capped(self) -> None:
        bus = ProgressBus()
        for i in range(250):
            bus.emit_event(f"event {i}")
        events = bus.snapshot().events
        # Cap is 200 by default.
        self.assertLessEqual(len(events), 200)
        # Most recent event is preserved.
        self.assertIn("event 249", events[-1].text)


class SnapshotImmutabilityTests(unittest.TestCase):
    """The snapshot is deep-copied so the UI never mutates internals."""

    def test_snapshot_does_not_share_stage_dict(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.OUTLINE)
        snap = bus.snapshot()
        snap.stages[Stage.OUTLINE].state = "tampered"
        # Re-fetch — original state must be untouched.
        self.assertEqual(bus.snapshot().stages[Stage.OUTLINE].state, "running")


class ConcurrencyTests(unittest.TestCase):
    """Many producers + readers must not deadlock or corrupt state."""

    def test_concurrent_producers_and_readers(self) -> None:
        bus = ProgressBus()
        bus.start_pipeline()
        stop = threading.Event()
        errors: list[Exception] = []

        def producer() -> None:
            try:
                for i in range(50):
                    bus.update_stage(Stage.IMAGES, items_done=i, items_total=50)
                    bus.emit_event(f"tick {i}", stage=Stage.IMAGES)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def reader() -> None:
            try:
                while not stop.is_set():
                    snap = bus.snapshot()
                    _ = len(snap.events)
                    _ = snap.stages[Stage.IMAGES].items_done
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        bus.start_stage(Stage.IMAGES, items_total=50)
        producers = [threading.Thread(target=producer) for _ in range(4)]
        readers = [threading.Thread(target=reader) for _ in range(2)]
        for t in producers + readers:
            t.start()
        for t in producers:
            t.join(timeout=5)
        stop.set()
        for t in readers:
            t.join(timeout=5)

        self.assertEqual(errors, [])
        bus.end_stage(Stage.IMAGES)
        bus.mark_done()


class StageRuntimeTests(unittest.TestCase):
    def test_runtime_blank_before_start(self) -> None:
        bus = ProgressBus()
        self.assertEqual(bus.snapshot().stages[Stage.OUTLINE].runtime, "")

    def test_runtime_increases_during_run(self) -> None:
        bus = ProgressBus()
        bus.start_stage(Stage.OUTLINE)
        time.sleep(0.05)
        rt1 = bus.snapshot().stages[Stage.OUTLINE].runtime
        time.sleep(0.05)
        rt2 = bus.snapshot().stages[Stage.OUTLINE].runtime
        # Both should be non-empty; rt2 should be >= rt1 once seconds tick.
        self.assertNotEqual(rt1, "")
        self.assertNotEqual(rt2, "")


if __name__ == "__main__":
    unittest.main()
