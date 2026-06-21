"""Tests for core/exporters.py (E3–E5) and Storage export/import (E1–E2).

Covers:
  E3 — export_csv
  E4 — export_markdown_library
  E5 — export_video_json
  E1 — Storage.export_json
  E2 — Storage.import_json (merge + overwrite)
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys

import pytest

# Ensure project root is on sys.path when running from the tests/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.exporters import export_csv, export_markdown_library, export_video_json
from core.storage import Storage
from models.video import WatchStatus
from tests.helpers import make_video, make_collection


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_video():
    v = make_video(
        video_id="vid001",
        title="Learn Python",
        channel="Corey Schafer",
        duration="12:34",
        status=WatchStatus.WATCHING,
        tags=["python", "tutorial"],
    )
    v.manual_notes = "Great intro\nVery clear"
    v.summary_paragraph = "A solid Python overview."
    v.watch_progress_sec = 300
    return v


@pytest.fixture()
def sample_collection():
    return make_collection(name="Python Series", video_ids=["vid001", "vid002"])


@pytest.fixture()
def two_videos():
    return [
        make_video(video_id="vid001", title="Alpha", status=WatchStatus.WATCHING, tags=["a", "b"]),
        make_video(video_id="vid002", title="Beta",  status=WatchStatus.SAVED),
    ]


@pytest.fixture()
def storage(tmp_path):
    return Storage(path=str(tmp_path / "videos.json"))


# ── E3: export_csv ────────────────────────────────────────────────────────────

class TestExportCsv:
    def test_header_contains_all_16_columns(self, two_videos):
        text = export_csv(two_videos)
        reader = csv.DictReader(io.StringIO(text))
        expected = {
            "video_id", "title", "channel", "url", "status", "progress_pct",
            "watch_progress_sec", "duration_sec", "duration", "tags",
            "published_at", "created_at", "updated_at", "manual_notes",
            "summary_paragraph", "thumbnail_url",
        }
        assert expected == set(reader.fieldnames)

    def test_row_count_matches_input(self, two_videos):
        text = export_csv(two_videos)
        rows = list(csv.DictReader(io.StringIO(text)))
        assert len(rows) == 2

    def test_tags_joined_with_pipe(self, sample_video):
        text = export_csv([sample_video])
        row = next(csv.DictReader(io.StringIO(text)))
        assert row["tags"] == "python | tutorial"

    def test_status_is_string_value(self, sample_video):
        text = export_csv([sample_video])
        row = next(csv.DictReader(io.StringIO(text)))
        assert row["status"] == "watching"

    def test_progress_pct_is_two_decimal_float(self, sample_video):
        text = export_csv([sample_video])
        row = next(csv.DictReader(io.StringIO(text)))
        pct = row["progress_pct"]
        assert "." in pct
        float(pct)  # must not raise

    def test_empty_list_returns_header_only(self):
        text = export_csv([])
        lines = [l for l in text.splitlines() if l.strip()]
        assert len(lines) == 1  # only the header row

    def test_newlines_in_notes_removed(self, sample_video):
        """Manual notes with newlines must not break CSV cell boundaries."""
        text = export_csv([sample_video])
        row = next(csv.DictReader(io.StringIO(text)))
        assert "\n" not in row["manual_notes"]

    def test_no_tags_produces_empty_string(self):
        v = make_video(tags=[])
        text = export_csv([v])
        row = next(csv.DictReader(io.StringIO(text)))
        assert row["tags"] == ""


# ── E4: export_markdown_library ───────────────────────────────────────────────

class TestExportMarkdownLibrary:
    def test_starts_with_h1(self, two_videos):
        md = export_markdown_library(two_videos)
        assert md.startswith("# YouTube Learning Library")

    def test_contains_video_title(self, two_videos):
        md = export_markdown_library(two_videos)
        assert "Alpha" in md
        assert "Beta" in md

    def test_watching_section_present(self, two_videos):
        md = export_markdown_library(two_videos)
        assert "Watching" in md

    def test_collections_section_present(self, two_videos, sample_collection):
        md = export_markdown_library(two_videos, collections=[sample_collection])
        assert "## Collections" in md
        assert "Python Series" in md

    def test_no_collections_skips_section(self, two_videos):
        md = export_markdown_library(two_videos, collections=None)
        assert "## Collections" not in md

    def test_manual_notes_included(self, sample_video):
        md = export_markdown_library([sample_video])
        assert "Great intro" in md

    def test_summary_paragraph_included(self, sample_video):
        md = export_markdown_library([sample_video])
        assert "A solid Python overview." in md

    def test_empty_library_still_valid(self):
        md = export_markdown_library([])
        assert "# YouTube Learning Library" in md

    def test_summary_truncated_at_300_chars(self):
        v = make_video()
        v.summary_paragraph = "x" * 400
        md = export_markdown_library([v])
        assert "\u2026" in md  # ellipsis appended when > 300 chars


# ── E5: export_video_json ─────────────────────────────────────────────────────

class TestExportVideoJson:
    def test_valid_json(self, sample_video):
        text = export_video_json(sample_video)
        payload = json.loads(text)  # must not raise
        assert isinstance(payload, dict)

    def test_schema_version_is_1(self, sample_video):
        payload = json.loads(export_video_json(sample_video))
        assert payload["schema_version"] == 1

    def test_exported_at_present(self, sample_video):
        payload = json.loads(export_video_json(sample_video))
        assert "exported_at" in payload

    def test_video_dict_roundtrip(self, sample_video):
        payload = json.loads(export_video_json(sample_video))
        from models.video import Video
        restored = Video.from_dict(payload["video"])
        assert restored.video_id == sample_video.video_id
        assert restored.title    == sample_video.title

    def test_tags_preserved(self, sample_video):
        payload = json.loads(export_video_json(sample_video))
        assert payload["video"]["tags"] == ["python", "tutorial"]

    def test_output_is_pretty_printed(self, sample_video):
        text = export_video_json(sample_video)
        assert "\n" in text  # indent=2 adds newlines


# ── E1: Storage.export_json ───────────────────────────────────────────────────

class TestStorageExportJson:
    def test_schema_version_is_1(self, storage, sample_video):
        storage.save_video(sample_video)
        snap = storage.export_json()
        assert snap["schema_version"] == 1

    def test_exported_at_present(self, storage):
        snap = storage.export_json()
        assert "exported_at" in snap

    def test_videos_key_present(self, storage, sample_video):
        storage.save_video(sample_video)
        snap = storage.export_json()
        assert sample_video.video_id in snap["videos"]

    def test_collections_key_present(self, storage):
        snap = storage.export_json()
        assert "collections" in snap

    def test_empty_library_exports_empty_dicts(self, storage):
        snap = storage.export_json()
        assert snap["videos"] == {}
        assert snap["collections"] == {}


# ── E2: Storage.import_json ───────────────────────────────────────────────────

class TestStorageImportJson:
    def _make_payload(self, *videos):
        """Build a minimal import payload from Video objects."""
        return {
            "schema_version": 1,
            "videos":        {v.video_id: v.to_dict() for v in videos},
            "collections":   {},
        }

    def test_merge_adds_new_videos(self, storage):
        v1 = make_video(video_id="v1", title="Existing")
        storage.save_video(v1)
        v2 = make_video(video_id="v2", title="Incoming")
        payload = self._make_payload(v2)
        added_v, added_c = storage.import_json(payload, merge=True)
        assert added_v == 1
        assert storage.get_video("v2") is not None

    def test_merge_skips_existing_ids(self, storage):
        v1 = make_video(video_id="v1", title="Original")
        storage.save_video(v1)
        v1_dup = make_video(video_id="v1", title="Should Not Overwrite")
        payload = self._make_payload(v1_dup)
        added_v, _ = storage.import_json(payload, merge=True)
        assert added_v == 0
        # fix: assert the title we actually saved, not a copy-paste from a different fixture
        assert storage.get_video("v1").title == "Original"

    def test_merge_returns_correct_counts(self, storage):
        existing = make_video(video_id="v1")
        storage.save_video(existing)
        new1 = make_video(video_id="v2")
        new2 = make_video(video_id="v3")
        payload = self._make_payload(existing, new1, new2)
        added_v, added_c = storage.import_json(payload, merge=True)
        assert added_v == 2  # v2 + v3; v1 skipped
        assert added_c == 0

    def test_overwrite_replaces_entire_library(self, storage):
        old = make_video(video_id="old", title="Old Video")
        storage.save_video(old)
        new = make_video(video_id="new", title="New Video")
        payload = self._make_payload(new)
        storage.import_json(payload, merge=False)
        assert storage.get_video("old") is None
        assert storage.get_video("new") is not None

    def test_overwrite_returns_total_payload_count(self, storage):
        v1 = make_video(video_id="v1")
        v2 = make_video(video_id="v2")
        payload = self._make_payload(v1, v2)
        added_v, _ = storage.import_json(payload, merge=False)
        assert added_v == 2

    def test_empty_payload_does_not_crash(self, storage):
        added_v, added_c = storage.import_json({"videos": {}, "collections": {}}, merge=True)
        assert added_v == 0
        assert added_c == 0
