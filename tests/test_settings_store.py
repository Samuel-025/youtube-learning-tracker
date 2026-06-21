"""Tests for core/settings_store.py (SettingsStore — v0.9.0).

Covers:
  - Default values on first init
  - Persist a value and reload
  - Overwrite an existing key
  - weekly_goal_hours typed property (get + set)
  - Negative goal clamped to 0
  - Corrupt JSON file falls back to defaults
  - Unknown keys are preserved on reload
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.settings_store import SettingsStore


@pytest.fixture()
def settings(tmp_path):
    """Fresh SettingsStore backed by a temp file."""
    return SettingsStore(path=tmp_path / "settings.json")


# ── defaults ──────────────────────────────────────────────────────────────────

class TestDefaults:
    def test_weekly_goal_default_is_zero(self, settings):
        assert settings.weekly_goal_hours == 0.0

    def test_get_unknown_key_returns_none(self, settings):
        assert settings.get("nonexistent_key") is None

    def test_get_unknown_key_returns_supplied_default(self, settings):
        assert settings.get("missing", 42) == 42


# ── persist & reload ──────────────────────────────────────────────────────────

class TestPersistence:
    def test_set_then_get_same_session(self, settings):
        settings.set("weekly_goal_hours", 5.0)
        assert settings.get("weekly_goal_hours") == 5.0

    def test_value_persists_across_new_instance(self, tmp_path):
        path = tmp_path / "settings.json"
        s1 = SettingsStore(path=path)
        s1.set("weekly_goal_hours", 7.5)

        s2 = SettingsStore(path=path)  # reload from same file
        assert s2.weekly_goal_hours == 7.5

    def test_overwrite_existing_key(self, settings):
        settings.set("weekly_goal_hours", 3.0)
        settings.set("weekly_goal_hours", 10.0)
        assert settings.weekly_goal_hours == 10.0

    def test_file_created_on_init(self, tmp_path):
        path = tmp_path / "subdir" / "settings.json"
        SettingsStore(path=path)
        assert path.exists()

    def test_arbitrary_key_persists(self, tmp_path):
        path = tmp_path / "settings.json"
        s1 = SettingsStore(path=path)
        s1.set("custom_flag", True)
        s2 = SettingsStore(path=path)
        assert s2.get("custom_flag") is True


# ── weekly_goal_hours property ────────────────────────────────────────────────

class TestWeeklyGoalProperty:
    def test_set_via_property(self, settings):
        settings.weekly_goal_hours = 8.0
        assert settings.weekly_goal_hours == 8.0

    def test_negative_goal_clamped_to_zero(self, settings):
        settings.weekly_goal_hours = -5.0
        assert settings.weekly_goal_hours == 0.0

    def test_zero_goal_allowed(self, settings):
        settings.weekly_goal_hours = 0
        assert settings.weekly_goal_hours == 0.0

    def test_fractional_goal_preserved(self, settings):
        settings.weekly_goal_hours = 2.5
        assert settings.weekly_goal_hours == 2.5

    def test_int_input_returns_float(self, settings):
        settings.weekly_goal_hours = 4
        assert isinstance(settings.weekly_goal_hours, float)


# ── resilience ────────────────────────────────────────────────────────────────

class TestResilience:
    def test_corrupt_json_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{ not valid json !!!")
        s = SettingsStore(path=path)
        assert s.weekly_goal_hours == 0.0  # default, no crash

    def test_missing_file_creates_with_defaults(self, tmp_path):
        path = tmp_path / "fresh.json"
        assert not path.exists()
        s = SettingsStore(path=path)
        assert path.exists()
        assert s.weekly_goal_hours == 0.0

    def test_unknown_keys_in_file_are_preserved(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps({"future_feature": "enabled", "weekly_goal_hours": 3.0}))
        s = SettingsStore(path=path)
        assert s.get("future_feature") == "enabled"
        assert s.weekly_goal_hours == 3.0
