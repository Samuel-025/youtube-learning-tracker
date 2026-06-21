"""Pure helper functions extracted from streamlit_app.py.

These contain zero Streamlit calls and can be imported freely in tests,
CLI scripts, and other non-Streamlit contexts.

Public API
----------
_apply_progress(video, new_sec)          -> str | None
_week_watched_hours(videos)              -> float
_current_week_bounds()                   -> tuple[datetime, datetime]
_linkify_timestamps(text, video_id)      -> str
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.video import Video


# ---------------------------------------------------------------------------
# Progress / status transitions
# ---------------------------------------------------------------------------

def _apply_progress(video: "Video", new_sec: int) -> str | None:  # noqa: F821
    """Update watch_progress_sec and auto-transition watch status.

    Rules
    -----
    - new_sec >= duration  → always set COMPLETED (any prior status)
    - new_sec > 0          → SAVED → WATCHING  (start watching)
    - new_sec > 0          → COMPLETED → WATCHING (scrub back, B5)
    - new_sec == 0         → COMPLETED/WATCHING → SAVED (reset)
    - dropped / rewatch    → never silently overwritten on partial progress;
                             only overwritten when reaching 100%.

    Returns a celebratory message string when status flips to COMPLETED,
    otherwise None.
    """
    # Import here to avoid circular issues when this module is imported
    # before the models package is fully initialised.
    from models.video import WatchStatus

    video.watch_progress_sec = new_sec
    celebration: str | None = None

    if new_sec >= video.duration_sec:
        if video.status != WatchStatus.COMPLETED:
            video.status = WatchStatus.COMPLETED
            celebration   = "🎉 Marked as **Completed**!"
    elif new_sec > 0:
        if video.status == WatchStatus.SAVED:
            video.status = WatchStatus.WATCHING
        elif video.status == WatchStatus.COMPLETED:
            video.status = WatchStatus.WATCHING
    else:
        if video.status in (WatchStatus.COMPLETED, WatchStatus.WATCHING):
            video.status = WatchStatus.SAVED

    return celebration


# ---------------------------------------------------------------------------
# Weekly watch-goal helpers
# ---------------------------------------------------------------------------

def _current_week_bounds() -> tuple[datetime, datetime]:
    """Return (monday_00:00, sunday_23:59:59) for the current ISO week in UTC."""
    now        = datetime.now(timezone.utc)
    monday     = now - timedelta(days=now.weekday())
    week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end   = week_start + timedelta(days=7) - timedelta(seconds=1)
    return week_start, week_end


def _week_watched_hours(videos: list) -> float:
    """Sum watch_progress_sec for videos updated this ISO week, in hours."""
    week_start, week_end = _current_week_bounds()
    total_sec = 0
    for v in videos:
        if not v.updated_at:
            continue
        try:
            updated = datetime.fromisoformat(v.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if week_start <= updated <= week_end:
                total_sec += v.watch_progress_sec
        except (ValueError, AttributeError):
            continue
    return total_sec / 3600


# ---------------------------------------------------------------------------
# Timestamp linkifier
# ---------------------------------------------------------------------------

_TS_RE = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")

_HTML_ESC: dict[str, str] = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#x27;",
}


def _linkify_timestamps(text: str, video_id: str) -> str:
    """Replace HH:MM:SS / MM:SS patterns with YouTube deep-link HTML anchors.

    The input *text* is HTML-escaped before substitution so that malicious
    transcript content (e.g. <script> tags) cannot pass through as raw HTML
    (fixes B10 / XSS).

    The output is HTML suitable for st.markdown(..., unsafe_allow_html=True).
    """
    # HTML-escape the whole text first (fixes B10)
    safe = re.sub(
        r'[&<>"\']',
        lambda m: _HTML_ESC.get(m.group(0), m.group(0)),
        text,
    )

    def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
        h, m, s = match.group(1), match.group(2), match.group(3)
        total   = (int(h) if h else 0) * 3600 + int(m) * 60 + int(s)
        label   = match.group(0)
        if "youtube.com/watch" in video_id:
            url = f"{video_id}&t={total}s"
        else:
            url = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#1a6b8a;text-decoration:none;font-weight:500;">'
            f'{label}</a>'
        )

    return _TS_RE.sub(_replace, safe)


def _extract_timestamps(text: str) -> list[tuple[str, int]]:
    """Return [(label, total_seconds), ...] for every timestamp in *text*."""
    results: list[tuple[str, int]] = []
    for m in _TS_RE.finditer(text):
        h    = int(m.group(1)) if m.group(1) else 0
        mins = int(m.group(2))
        secs = int(m.group(3))
        results.append((m.group(0), h * 3600 + mins * 60 + secs))
    return results
