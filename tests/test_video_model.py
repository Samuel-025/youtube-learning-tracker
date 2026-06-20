"""Tests for the Video data model."""

import dataclasses
import pytest
from models.video import Video, WatchStatus, _parse_duration_sec
from helpers import make_video


# ---------------------------------------------------------------------------
# _parse_duration_sec
# ---------------------------------------------------------------------------

class TestParseDurationSec:
    def test_mm_ss(self):
        assert _parse_duration_sec("10:34") == 634

    def test_hh_mm_ss(self):
        assert _parse_duration_sec("1:23:45") == 5025

    def test_iso8601(self):
        assert _parse_duration_sec("PT1H23M45S") == 5025

    def test_iso8601_minutes_only(self):
        assert _parse_duration_sec("PT5M") == 300

    def test_iso8601_seconds_only(self):
        assert _parse_duration_sec("PT45S") == 45

    def test_bare_seconds(self):
        assert _parse_duration_sec("45") == 45

    def test_empty_string(self):
        assert _parse_duration_sec("") == 0

    def test_unparseable(self):
        assert _parse_duration_sec("not-a-duration") == 0


# ---------------------------------------------------------------------------
# Video defaults & __post_init__
# ---------------------------------------------------------------------------

class TestVideoDefaults:
    def test_default_status(self):
        v = make_video()
        assert v.status == WatchStatus.SAVED

    def test_duration_sec_auto_populated(self):
        v = make_video(duration="5:00")
        assert v.duration_sec == 300

    def test_duration_sec_iso8601(self):
        v = make_video(duration="PT1H")
        assert v.duration_sec == 3600

    def test_local_path_empty_string_normalised_to_none(self):
        v = make_video()
        v.local_path = ""
        v.__post_init__()
        assert v.local_path is None

    def test_tags_coerced_to_str(self):
        """Tags must always be strings even if raw JSON has ints."""
        v = make_video()
        v.tags = [1, 2, 3]  # type: ignore
        v.__post_init__()
        assert v.tags == ["1", "2", "3"]


# ---------------------------------------------------------------------------
# progress_pct property
# ---------------------------------------------------------------------------

class TestProgressPct:
    def test_zero_when_no_duration(self):
        v = make_video(duration="")
        v.duration_sec = 0
        assert v.progress_pct == 0.0

    def test_fifty_percent(self):
        v = make_video(duration="10:00")  # 600s
        v.watch_progress_sec = 300
        assert v.progress_pct == pytest.approx(50.0)

    def test_caps_at_100(self):
        v = make_video(duration="10:00")
        v.watch_progress_sec = 9999
        assert v.progress_pct == 100.0


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_basic_round_trip(self):
        v = make_video(status=WatchStatus.WATCHING)
        v2 = Video.from_dict(v.to_dict())
        assert v2.video_id == v.video_id
        assert v2.status == WatchStatus.WATCHING

    def test_all_statuses_survive_round_trip(self):
        for status in WatchStatus:
            v = make_video(status=status)
            v2 = Video.from_dict(v.to_dict())
            assert v2.status == status

    def test_manual_notes_preserved(self):
        v = make_video()
        v.manual_notes = "My important note"
        v2 = Video.from_dict(v.to_dict())
        assert v2.manual_notes == "My important note"

    def test_tags_preserved(self):
        v = make_video(tags=["python", "beginner"])
        v2 = Video.from_dict(v.to_dict())
        assert v2.tags == ["python", "beginner"]

    def test_unknown_keys_dropped_silently(self):
        d = make_video().to_dict()
        d["future_field_xyz"] = "some value"
        v2 = Video.from_dict(d)
        assert not hasattr(v2, "future_field_xyz")

    def test_missing_keys_fall_back_to_defaults(self):
        d = make_video().to_dict()
        del d["manual_notes"]
        del d["tags"]
        v2 = Video.from_dict(d)
        assert v2.manual_notes == ""
        assert v2.tags == []

    def test_invalid_status_falls_back_to_saved(self):
        d = make_video().to_dict()
        d["status"] = "nonexistent_status"
        v2 = Video.from_dict(d)
        assert v2.status == WatchStatus.SAVED

    def test_from_dict_known_set_is_dynamic(self):
        """B11: from_dict derives 'known' from live dataclass, not hardcoded set."""
        field_names = {f.name for f in dataclasses.fields(Video)}
        v = make_video()
        v2 = Video.from_dict(v.to_dict())
        for name in field_names:
            assert getattr(v2, name) == getattr(v, name), f"Field '{name}' lost in round-trip"

    def test_duration_sec_recalculated_when_zero(self):
        """B4: from_dict recalculates duration_sec when stored value is 0."""
        d = make_video(duration="5:00").to_dict()
        d["duration_sec"] = 0
        v2 = Video.from_dict(d)
        assert v2.duration_sec == 300
