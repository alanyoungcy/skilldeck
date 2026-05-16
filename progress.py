"""Thread-safe progress bus for the skilldeck pipeline.

The pipeline runs in a daemon thread; the Streamlit UI thread polls
`ProgressBus.snapshot()` once per autorefresh tick to render the timeline.
The bus tracks both ordered stage state ("Source saved", "Outline generated",
…) and a per-stage event log so the UI can show the latest message.

Design notes:
  * `Stage` is an Enum with a fixed order — the UI iterates it to render the
    timeline rows even before the pipeline starts, so users see the queued
    states immediately.
  * `emit_stage(stage, state, ...)` is the only public mutator beyond
    `emit_event` and `mark_done`/`mark_error`. Everything else derives.
  * Snapshots are deep-copied so the UI never mutates internal state.
"""
from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Stage(str, Enum):
    """Ordered pipeline stages shown in the UI timeline."""
    SOURCE = "source"          # source-*.md, analysis.md, confirmation.yaml
    OUTLINE = "outline"        # outline.md
    PROMPTS = "prompts"        # prompts/NN-slide-*.md and *.chart.json
    CONCEPTS = "concepts"      # creative-director visual concepts (P5)
    CHARTS = "charts"          # CHART_SPEC -> SVG render
    IMAGES = "images"          # image API per slide
    PPTX = "pptx"              # editable PPTX assembly (deck_assembler)
    PDF = "pdf"                # optional PDF export

    @property
    def display(self) -> str:
        return {
            Stage.SOURCE: "Source and analysis saved",
            Stage.OUTLINE: "Outline generated and validated",
            Stage.PROMPTS: "Per-slide prompts created",
            Stage.CONCEPTS: "Visual concepts generated",
            Stage.CHARTS: "Chart slides rendered",
            Stage.IMAGES: "Image slides generated",
            Stage.PPTX: "Editable PPTX assembled",
            Stage.PDF: "PDF exported",
        }[self]


# Visible stage state in the UI timeline.
StageState = str  # "queued" | "running" | "done" | "error" | "skipped"


@dataclass
class StageInfo:
    state: StageState = "queued"
    label: str = ""
    detail: str = ""
    progress: float | None = None       # 0.0..1.0 within stage
    items_done: int = 0
    items_total: int = 0
    started_at: float | None = None
    ended_at: float | None = None
    error: str | None = None

    @property
    def runtime(self) -> str:
        if self.started_at is None:
            return ""
        end = self.ended_at if self.ended_at is not None else time.time()
        secs = end - self.started_at
        if secs < 1:
            return "<1s"
        if secs < 60:
            return f"{secs:.0f}s"
        m, s = divmod(int(secs), 60)
        return f"{m}m{s:02d}s"


@dataclass
class ProgressEvent:
    """A timestamped log line. Stages can emit many events while running."""
    ts: float
    stage: Stage | None
    text: str
    level: str = "info"   # "info" | "warn" | "error"


@dataclass
class Snapshot:
    """Read-only view used by the UI."""
    stages: dict[Stage, StageInfo]
    events: list[ProgressEvent]
    overall_state: str           # "idle" | "running" | "done" | "error"
    started_at: float | None
    ended_at: float | None
    error: str | None = None


class ProgressBus:
    """Thread-safe pipeline state.

    Producer (pipeline thread) calls `start_stage`, `update_stage`, `end_stage`,
    `emit_event`, `mark_done`, `mark_error`. Consumer (UI thread) calls
    `snapshot()` to read everything atomically.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stages: dict[Stage, StageInfo] = {s: StageInfo() for s in Stage}
        self._events: list[ProgressEvent] = []
        self._max_events = 200
        self._overall_state: str = "idle"
        self._started_at: float | None = None
        self._ended_at: float | None = None
        self._error: str | None = None

    # ------------ producer side ------------

    def start_pipeline(self) -> None:
        with self._lock:
            self._overall_state = "running"
            self._started_at = time.time()
            self._ended_at = None
            self._error = None

    def start_stage(self, stage: Stage, label: str = "", detail: str = "",
                    items_total: int = 0) -> None:
        with self._lock:
            info = self._stages[stage]
            info.state = "running"
            info.label = label or stage.display
            info.detail = detail
            info.items_total = items_total
            info.items_done = 0
            info.progress = 0.0 if items_total else None
            info.started_at = time.time()
            info.ended_at = None
            info.error = None
            self._append_event_locked(stage, label or stage.display)

    def update_stage(self, stage: Stage, *, items_done: int | None = None,
                     items_total: int | None = None, detail: str | None = None) -> None:
        with self._lock:
            info = self._stages[stage]
            if items_total is not None:
                info.items_total = items_total
            if items_done is not None:
                info.items_done = items_done
            if info.items_total:
                info.progress = min(1.0, info.items_done / info.items_total)
            if detail is not None:
                info.detail = detail

    def end_stage(self, stage: Stage, detail: str | None = None) -> None:
        with self._lock:
            info = self._stages[stage]
            info.state = "done"
            info.ended_at = time.time()
            if detail is not None:
                info.detail = detail
            if info.items_total:
                info.items_done = info.items_total
                info.progress = 1.0
            self._append_event_locked(stage, f"{info.label or stage.display} — done")

    def skip_stage(self, stage: Stage, reason: str = "") -> None:
        with self._lock:
            info = self._stages[stage]
            info.state = "skipped"
            info.detail = reason
            info.ended_at = time.time()
            self._append_event_locked(stage, f"{info.label or stage.display} — skipped: {reason}".rstrip(": "))

    def fail_stage(self, stage: Stage, error: str) -> None:
        with self._lock:
            info = self._stages[stage]
            info.state = "error"
            info.error = error
            info.ended_at = time.time()
            self._append_event_locked(stage, error, level="error")

    def emit_event(self, text: str, *, stage: Stage | None = None, level: str = "info") -> None:
        with self._lock:
            self._append_event_locked(stage, text, level=level)

    def mark_done(self) -> None:
        with self._lock:
            self._overall_state = "done"
            self._ended_at = time.time()

    def mark_error(self, error: str) -> None:
        with self._lock:
            self._overall_state = "error"
            self._error = error
            self._ended_at = time.time()
            self._append_event_locked(None, error, level="error")

    # ------------ consumer side ------------

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                stages=copy.deepcopy(self._stages),
                events=list(self._events),
                overall_state=self._overall_state,
                started_at=self._started_at,
                ended_at=self._ended_at,
                error=self._error,
            )

    def is_running(self) -> bool:
        with self._lock:
            return self._overall_state == "running"

    # ------------ internal ------------

    def _append_event_locked(self, stage: Stage | None, text: str, level: str = "info") -> None:
        self._events.append(ProgressEvent(time.time(), stage, text, level=level))
        if len(self._events) > self._max_events:
            del self._events[: len(self._events) - self._max_events]


__all__ = [
    "ProgressBus",
    "ProgressEvent",
    "Snapshot",
    "Stage",
    "StageInfo",
]
