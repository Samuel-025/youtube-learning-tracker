"""Due-date helpers for F2 — Watch Reminders (v0.11.0).

Public API
----------
due_status(video) -> str | None
    'overdue'  — due_date is in the past
    'today'    — due_date is today
    'soon'     — due in 1–2 days
    'upcoming' — due in 3–7 days
    None       — no due_date set, or due > 7 days away

due_badge(video) -> tuple[str, str] | None
    Returns (emoji, label) for display, or None if no badge needed.
    e.g.  ('🔴', 'Overdue')  |  ('🟡', 'Today')  |  ('🟢', 'This week')

days_until(video) -> int | None
    Signed integer days from today to due_date.
    Negative = overdue.  None = no due_date set.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.video import Video


def days_until(video: "Video") -> int | None:
    """Return signed days from today to video.due_date, or None if unset."""
    # getattr guard: tolerates Video instances loaded before F2 was added
    due_date = getattr(video, "due_date", None)
    if not due_date:
        return None
    try:
        due = date.fromisoformat(due_date)  # expects YYYY-MM-DD
    except ValueError:
        return None
    return (due - date.today()).days


def due_status(video: "Video") -> str | None:
    """Classify how urgent the due date is.

    Returns one of 'overdue', 'today', 'soon', 'upcoming', or None.
    """
    d = days_until(video)
    if d is None:
        return None
    if d < 0:
        return "overdue"
    if d == 0:
        return "today"
    if d <= 2:
        return "soon"
    if d <= 7:
        return "upcoming"
    return None  # more than 7 days away — no badge


_BADGE: dict[str, tuple[str, str]] = {
    "overdue":  ("🔴", "Overdue"),
    "today":    ("🟡", "Due today"),
    "soon":     ("🟡", "Due soon"),
    "upcoming": ("🟢", "This week"),
}


def due_badge(video: "Video") -> tuple[str, str] | None:
    """Return (emoji, label) for the due-date badge, or None if no badge needed."""
    status = due_status(video)
    return _BADGE.get(status) if status else None
