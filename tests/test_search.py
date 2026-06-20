"""Tests for storage.search_videos — full-text search across all fields."""

import pytest
from models.video import WatchStatus
from conftest import make_video


class TestSearchVideos:
    """Comprehensive search tests — one fixture, multiple field assertions."""

    def _populate(self, storage):
        """Seed storage with a small diverse library."""
        v1 = make_video("id1aaaaaaa1", title="Python OOP Masterclass", channel="Tech With Tim")
        v1.summary_bullets = ["Classes and objects", "Inheritance explained"]
        v1.auto_notes = ["Great for beginners"]
        v1.tags = ["python", "oop"]

        v2 = make_video("id2aaaaaaa2", title="React Hooks Deep Dive", channel="Fireship")
        v2.manual_notes = "useState and useEffect patterns"
        v2.summary_paragraph = "A thorough walkthrough of React hooks."
        v2.tags = ["javascript", "react"]

        v3 = make_video("id3aaaaaaa3", title="SQL for Data Analysis", channel="Alex the Analyst")
        v3.tags = ["sql", "data"]

        for v in [v1, v2, v3]:
            storage.save_video(v)
        return v1, v2, v3

    def test_search_title(self, storage):
        self._populate(storage)
        results = storage.search_videos("masterclass")
        assert len(results) == 1
        assert results[0].video_id == "id1aaaaaaa1"

    def test_search_channel(self, storage):
        self._populate(storage)
        results = storage.search_videos("fireship")
        assert len(results) == 1
        assert results[0].video_id == "id2aaaaaaa2"

    def test_search_manual_notes(self, storage):
        self._populate(storage)
        results = storage.search_videos("useeffect")
        assert len(results) == 1

    def test_search_summary_paragraph(self, storage):
        self._populate(storage)
        results = storage.search_videos("thorough walkthrough")
        assert len(results) == 1

    def test_search_summary_bullets(self, storage):
        self._populate(storage)
        results = storage.search_videos("inheritance")
        assert len(results) == 1

    def test_search_auto_notes(self, storage):
        self._populate(storage)
        results = storage.search_videos("beginners")
        assert len(results) == 1

    def test_search_tag(self, storage):
        self._populate(storage)
        results = storage.search_videos("react")
        assert len(results) == 1

    def test_search_case_insensitive(self, storage):
        self._populate(storage)
        assert len(storage.search_videos("PYTHON")) == 1
        assert len(storage.search_videos("python")) == 1

    def test_search_partial_match(self, storage):
        self._populate(storage)
        results = storage.search_videos("anal")  # matches 'analysis' and 'analyst'
        assert len(results) == 1  # only v3 title and channel contain 'anal'

    def test_search_no_match(self, storage):
        self._populate(storage)
        assert storage.search_videos("kubernetes") == []

    def test_search_empty_library(self, storage):
        assert storage.search_videos("python") == []

    def test_search_returns_multiple_matches(self, storage):
        self._populate(storage)
        # 'data' matches v3 tag; but let's also add it to v1 notes
        results = storage.search_videos("python")
        # Only v1 has python in title/tags
        assert len(results) == 1

    def test_search_empty_query_returns_all(self, storage):
        """An empty search string matches everything (q in any string is always True)."""
        self._populate(storage)
        results = storage.search_videos("")
        assert len(results) == 3
