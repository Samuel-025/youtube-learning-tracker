"""Tests for core/due_date.py — F2 Watch Reminders (v0.11.0)."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.due_date import days_until, due_status, due_badge
from tests.helpers import make_video


def video_due(days_from_now: int):
    """Helper: video with due_date set to today ± N days."""
    d = date.today() + timedelta(days=days_from_now)
    return make_video(due_date=d.isoformat())


# ── days_until ────────────────────────────────────────────────────────────────

class TestDaysUntil:
    def test_no_due_date_returns_none(self):
        v = make_video()
        assert days_until(v) is None

    def test_today_returns_zero(self):
        assert days_until(video_due(0)) == 0

    def test_tomorrow_returns_one(self):
        assert days_until(video_due(1)) == 1

    def test_yesterday_returns_minus_one(self):
        assert days_until(video_due(-1)) == -1

    def test_invalid_date_returns_none(self):
        v = make_video(due_date="not-a-date")
        assert days_until(v) is None


# ── due_status ────────────────────────────────────────────────────────────────

class TestDueStatus:
    def test_no_due_date_returns_none(self):
        assert due_status(make_video()) is None

    def test_overdue(self):
        assert due_status(video_due(-1)) == "overdue"

    def test_today(self):
        assert due_status(video_due(0)) == "today"

    def test_soon_1_day(self):
        assert due_status(video_due(1)) == "soon"

    def test_soon_2_days(self):
        assert due_status(video_due(2)) == "soon"

    def test_upcoming_3_days(self):
        assert due_status(video_due(3)) == "upcoming"

    def test_upcoming_7_days(self):
        assert due_status(video_due(7)) == "upcoming"

    def test_beyond_7_days_returns_none(self):
        assert due_status(video_due(8)) is None


# ── due_badge ─────────────────────────────────────────────────────────────────

class TestDueBadge:
    def test_no_due_date_returns_none(self):
        assert due_badge(make_video()) is None

    def test_overdue_is_red(self):
        emoji, label = due_badge(video_due(-5))
        assert emoji == "🔴"
        assert "Overdue" in label

    def test_today_is_yellow(self):
        emoji, _ = due_badge(video_due(0))
        assert emoji == "🟡"

    def test_soon_is_yellow(self):
        emoji, _ = due_badge(video_due(1))
        assert emoji == "🟡"

    def test_upcoming_is_green(self):
        emoji, _ = due_badge(video_due(5))
        assert emoji == "🟢"

    def test_far_future_returns_none(self):
        assert due_badge(video_due(30)) is None
