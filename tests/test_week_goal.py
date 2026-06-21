"""Tests for _week_watched_hours() — weekly goal calculation (v0.11.0).

The helper sums watch_progress_sec only for videos whose updated_at
falls within the current ISO week (Mon 00:00 → Sun 23:59:59 UTC).
"""

from __future__ import annotations

import os
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Minimal Streamlit stub ────────────────────────────────────────────────────
_st = types.ModuleType("streamlit")
for _attr in (
    "set_page_config", "title", "caption", "markdown", "info", "success",
    "warning", "error", "divider", "progress", "metric", "balloons",
    "spinner", "rerun", "button", "selectbox", "text_input", "text_area",
    "slider", "columns", "container", "image", "radio", "checkbox",
    "date_input", "file_uploader", "download_button", "expander",
    "tabs", "video", "sidebar",
):
    setattr(_st, _attr, lambda *a, **kw: None)
_st.session_state = {}
_st.cache_data = lambda f=None, **kw: (f if f else lambda g: g)
for _submod in ("sidebar",):
    setattr(_st, _submod, types.SimpleNamespace(
        **{a: (lambda *x, **k: None) for a in ("title", "radio", "markdown", "divider", "caption")}
    ))
sys.modules["streamlit"] = _st

for _mod in ("dotenv", "plotly", "plotly.graph_objects"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
sys.modules["dotenv"].load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]

import importlib.util, pathlib
_spec = importlib.util.spec_from_file_location(
    "streamlit_app",
    pathlib.Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py",
)
_app = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
try:
    _spec.loader.exec_module(_app)  # type: ignore[union-attr]
except Exception:
    pass

_week_watched_hours  = _app._week_watched_hours   # type: ignore[attr-defined]
_current_week_bounds = _app._current_week_bounds  # type: ignore[attr-defined]

from helpers import make_video


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _video_updated(seconds_ago: int = 0, progress_sec: int = 3600) -> object:
    """Return a video updated `seconds_ago` seconds before now."""
    v = make_video()
    v.watch_progress_sec = progress_sec
    ts = _now_utc() - timedelta(seconds=seconds_ago)
    v.updated_at = ts.isoformat()
    return v


# ── Basic counting tests ───────────────────────────────────────────────────────

class TestWeekWatchedHours:
    def test_empty_library_returns_zero(self):
        assert _week_watched_hours([]) == 0.0

    def test_video_updated_now_is_counted(self):
        v = _video_updated(seconds_ago=0, progress_sec=3600)  # 1 h
        result = _week_watched_hours([v])
        assert abs(result - 1.0) < 0.01

    def test_video_updated_yesterday_is_counted(self):
        """Updated yesterday but still within the same ISO week."""
        # Only valid if today is not Monday — skip on Monday to be safe
        today = _now_utc()
        if today.weekday() == 0:  # Monday — yesterday was last week
            pytest.skip("Skipped on Monday: yesterday is outside the current ISO week")
        v = _video_updated(seconds_ago=86400, progress_sec=7200)  # 2 h
        result = _week_watched_hours([v])
        assert abs(result - 2.0) < 0.01

    def test_multiple_videos_summed(self):
        v1 = _video_updated(seconds_ago=60,  progress_sec=1800)  # 0.5 h
        v2 = _video_updated(seconds_ago=120, progress_sec=1800)  # 0.5 h
        result = _week_watched_hours([v1, v2])
        assert abs(result - 1.0) < 0.01

    def test_result_is_float(self):
        v = _video_updated(progress_sec=1800)
        result = _week_watched_hours([v])
        assert isinstance(result, float)


# ── Out-of-window exclusion tests ─────────────────────────────────────────────

class TestWeekBoundaryExclusion:
    def test_video_from_last_week_not_counted(self):
        """A video updated 8+ days ago must not contribute."""
        v = _video_updated(seconds_ago=8 * 86400, progress_sec=3600)
        result = _week_watched_hours([v])
        assert result == 0.0

    def test_video_updated_next_week_not_counted(self):
        """A future updated_at (next week) must not be counted."""
        v = make_video()
        v.watch_progress_sec = 3600
        future = _now_utc() + timedelta(days=8)
        v.updated_at = future.isoformat()
        result = _week_watched_hours([v])
        assert result == 0.0

    def test_video_with_no_updated_at_skipped(self):
        v = make_video()
        v.watch_progress_sec = 3600
        v.updated_at = None
        result = _week_watched_hours([v])
        assert result == 0.0


# ── Robustness / edge cases ────────────────────────────────────────────────────

class TestWeekGoalEdgeCases:
    def test_naive_datetime_handled_without_crash(self):
        """updated_at without tzinfo should not raise; should still count."""
        v = make_video()
        v.watch_progress_sec = 3600
        # naive ISO string — no timezone info
        naive_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        v.updated_at = naive_ts
        # Should not raise — result value depends on implementation
        result = _week_watched_hours([v])
        assert isinstance(result, float)

    def test_malformed_updated_at_skipped(self):
        v = make_video()
        v.watch_progress_sec = 3600
        v.updated_at = "not-a-date"
        result = _week_watched_hours([v])
        assert result == 0.0

    def test_zero_progress_video_contributes_zero(self):
        v = _video_updated(seconds_ago=60, progress_sec=0)
        result = _week_watched_hours([v])
        assert result == 0.0

    def test_mixed_in_and_out_of_window(self):
        """Only this-week videos are summed; last-week ones are ignored."""
        in_window  = _video_updated(seconds_ago=3600,     progress_sec=3600)  # 1 h
        out_window = _video_updated(seconds_ago=8 * 86400, progress_sec=3600) # last week
        result = _week_watched_hours([in_window, out_window])
        assert abs(result - 1.0) < 0.01


# ── _current_week_bounds sanity check ─────────────────────────────────────────

class TestCurrentWeekBounds:
    def test_start_is_monday(self):
        start, _ = _current_week_bounds()
        assert start.weekday() == 0  # 0 = Monday

    def test_end_is_sunday(self):
        _, end = _current_week_bounds()
        assert end.weekday() == 6  # 6 = Sunday

    def test_start_at_midnight(self):
        start, _ = _current_week_bounds()
        assert start.hour == 0 and start.minute == 0 and start.second == 0

    def test_end_at_23_59_59(self):
        _, end = _current_week_bounds()
        assert end.hour == 23 and end.minute == 59 and end.second == 59

    def test_both_are_utc_aware(self):
        start, end = _current_week_bounds()
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_span_is_7_days(self):
        start, end = _current_week_bounds()
        diff = end - start
        assert diff.days == 6  # 6 full days + 23:59:59
