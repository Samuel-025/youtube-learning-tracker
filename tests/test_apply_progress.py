"""Tests for _apply_progress() — auto-status transition logic (v0.11.0).

The function is imported directly from core.ui_helpers (pure Python, no
Streamlit dependency) so no stub or partial-module loading is needed.

Logic under test
----------------
- Partial progress:   SAVED → WATCHING
- Full progress:      any   → COMPLETED  (returns celebration string)
- Reset to zero:      COMPLETED/WATCHING → SAVED
- Dropped/Rewatch:   never silently overwritten on partial progress
                      (only overwritten at 100%)
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ui_helpers import _apply_progress
from helpers import make_video
from models.video import WatchStatus


# ── helpers ───────────────────────────────────────────────────────────────────

def _video(status: WatchStatus, duration: int = 600, progress: int = 0):
    v = make_video()
    v.duration_sec        = duration
    v.status              = status
    v.watch_progress_sec  = progress
    return v


# ── Partial progress tests ─────────────────────────────────────────────────────

class TestPartialProgress:
    def test_saved_becomes_watching(self):
        v = _video(WatchStatus.SAVED)
        _apply_progress(v, 100)
        assert v.status == WatchStatus.WATCHING

    def test_watching_stays_watching(self):
        v = _video(WatchStatus.WATCHING, progress=100)
        _apply_progress(v, 200)
        assert v.status == WatchStatus.WATCHING

    def test_dropped_not_overwritten_on_partial(self):
        v = _video(WatchStatus.DROPPED)
        _apply_progress(v, 100)
        assert v.status == WatchStatus.DROPPED

    def test_rewatch_not_overwritten_on_partial(self):
        v = _video(WatchStatus.REWATCH)
        _apply_progress(v, 100)
        assert v.status == WatchStatus.REWATCH

    def test_watch_progress_sec_is_updated(self):
        v = _video(WatchStatus.SAVED)
        _apply_progress(v, 123)
        assert v.watch_progress_sec == 123

    def test_partial_returns_none(self):
        v = _video(WatchStatus.SAVED)
        result = _apply_progress(v, 100)
        assert result is None


# ── Full progress (100%) tests ─────────────────────────────────────────────────

class TestFullProgress:
    def test_saved_becomes_completed_at_full(self):
        v = _video(WatchStatus.SAVED, duration=600)
        _apply_progress(v, 600)
        assert v.status == WatchStatus.COMPLETED

    def test_watching_becomes_completed_at_full(self):
        v = _video(WatchStatus.WATCHING, duration=600)
        _apply_progress(v, 600)
        assert v.status == WatchStatus.COMPLETED

    def test_dropped_becomes_completed_at_full(self):
        """Even dropped videos flip to completed when full progress is set."""
        v = _video(WatchStatus.DROPPED, duration=600)
        _apply_progress(v, 600)
        assert v.status == WatchStatus.COMPLETED

    def test_rewatch_becomes_completed_at_full(self):
        v = _video(WatchStatus.REWATCH, duration=600)
        _apply_progress(v, 600)
        assert v.status == WatchStatus.COMPLETED

    def test_full_returns_celebration_string(self):
        v = _video(WatchStatus.SAVED, duration=600)
        result = _apply_progress(v, 600)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_already_completed_returns_none(self):
        """No celebration when status doesn't actually change."""
        v = _video(WatchStatus.COMPLETED, duration=600, progress=600)
        result = _apply_progress(v, 600)
        assert result is None

    def test_exceeding_duration_also_completes(self):
        """Setting progress > duration still triggers completion."""
        v = _video(WatchStatus.SAVED, duration=600)
        _apply_progress(v, 700)
        assert v.status == WatchStatus.COMPLETED


# ── Reset to zero tests ────────────────────────────────────────────────────────

class TestResetToZero:
    def test_completed_resets_to_saved(self):
        v = _video(WatchStatus.COMPLETED, duration=600, progress=600)
        _apply_progress(v, 0)
        assert v.status == WatchStatus.SAVED

    def test_watching_resets_to_saved(self):
        v = _video(WatchStatus.WATCHING, progress=200)
        _apply_progress(v, 0)
        assert v.status == WatchStatus.SAVED

    def test_saved_stays_saved_on_zero(self):
        v = _video(WatchStatus.SAVED)
        _apply_progress(v, 0)
        assert v.status == WatchStatus.SAVED

    def test_dropped_unaffected_by_zero(self):
        v = _video(WatchStatus.DROPPED, progress=100)
        _apply_progress(v, 0)
        assert v.status == WatchStatus.DROPPED

    def test_reset_returns_none(self):
        v = _video(WatchStatus.WATCHING, progress=200)
        result = _apply_progress(v, 0)
        assert result is None

    def test_watch_progress_sec_set_to_zero(self):
        v = _video(WatchStatus.WATCHING, progress=300)
        _apply_progress(v, 0)
        assert v.watch_progress_sec == 0
