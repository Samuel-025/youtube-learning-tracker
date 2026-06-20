"""Tests for the Storage class."""

import threading
import pytest
from models.video import WatchStatus
from helpers import make_video, make_collection


# ---------------------------------------------------------------------------
# CRUD — Videos
# ---------------------------------------------------------------------------

class TestVideoCRUD:
    def test_save_and_get(self, storage):
        v = make_video()
        storage.save_video(v)
        result = storage.get_video(v.video_id)
        assert result is not None
        assert result.title == v.title

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_video("does_not_exist") is None

    def test_get_all_empty(self, storage):
        assert storage.get_all_videos() == []

    def test_get_all_multiple(self, storage):
        storage.save_video(make_video("vid1aaaaaaa"))
        storage.save_video(make_video("vid2aaaaaaa"))
        assert len(storage.get_all_videos()) == 2

    def test_save_overwrites_existing(self, storage):
        v = make_video()
        storage.save_video(v)
        v.title = "Updated Title"
        storage.save_video(v)
        result = storage.get_video(v.video_id)
        assert result.title == "Updated Title"
        assert len(storage.get_all_videos()) == 1

    def test_delete_existing(self, storage):
        v = make_video()
        storage.save_video(v)
        assert storage.delete_video(v.video_id) is True
        assert storage.get_video(v.video_id) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_video("ghost_id") is False

    def test_update_video_changes_updated_at(self, storage):
        import time
        v = make_video()
        storage.save_video(v)
        old_ts = v.updated_at
        time.sleep(0.01)
        v.title = "New Title"
        storage.update_video(v)
        result = storage.get_video(v.video_id)
        assert result.updated_at >= old_ts

    def test_clear_all_videos(self, storage):
        storage.save_video(make_video("vid1aaaaaaa"))
        storage.save_video(make_video("vid2aaaaaaa"))
        storage.clear_all_videos()
        assert storage.get_all_videos() == []


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_no_partial_write_on_concurrent_saves(self, storage):
        """Concurrent saves must not corrupt the JSON file."""
        errors = []

        def save(i):
            try:
                storage.save_video(make_video(f"vid{i:08d}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=save, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent writes: {errors}"
        assert len(storage.get_all_videos()) == 20


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

class TestFilterAndSearch:
    def test_filter_by_status(self, storage):
        storage.save_video(make_video("vid1aaaaaaa", status=WatchStatus.SAVED))
        storage.save_video(make_video("vid2aaaaaaa", status=WatchStatus.COMPLETED))
        storage.save_video(make_video("vid3aaaaaaa", status=WatchStatus.COMPLETED))
        completed = storage.filter_by_status(WatchStatus.COMPLETED)
        assert len(completed) == 2
        assert all(v.status == WatchStatus.COMPLETED for v in completed)

    def test_filter_by_status_empty(self, storage):
        assert storage.filter_by_status(WatchStatus.WATCHING) == []

    def test_count_by_status(self, storage):
        storage.save_video(make_video("vid1aaaaaaa", status=WatchStatus.SAVED))
        storage.save_video(make_video("vid2aaaaaaa", status=WatchStatus.WATCHING))
        storage.save_video(make_video("vid3aaaaaaa", status=WatchStatus.WATCHING))
        counts = storage.count_by_status()
        assert counts["saved"] == 1
        assert counts["watching"] == 2
        assert counts["completed"] == 0

    def test_search_by_title(self, storage):
        storage.save_video(make_video(title="Python Tutorial for Beginners"))
        storage.save_video(make_video("vid2aaaaaaa", title="Learn JavaScript"))
        results = storage.search_videos("python")
        assert len(results) == 1
        assert results[0].title == "Python Tutorial for Beginners"

    def test_search_by_channel(self, storage):
        v = make_video(channel="Corey Schafer")
        storage.save_video(v)
        results = storage.search_videos("corey")
        assert len(results) == 1

    def test_search_by_manual_notes(self, storage):
        v = make_video()
        v.manual_notes = "important decorator pattern"
        storage.save_video(v)
        results = storage.search_videos("decorator")
        assert len(results) == 1

    def test_search_by_tag(self, storage):
        v = make_video(tags=["machine-learning", "numpy"])
        storage.save_video(v)
        results = storage.search_videos("machine-learning")
        assert len(results) == 1

    def test_search_by_summary_bullets(self, storage):
        v = make_video()
        v.summary_bullets = ["Closures capture enclosing scope", "Use functools.wraps"]
        storage.save_video(v)
        results = storage.search_videos("closures")
        assert len(results) == 1

    def test_search_by_auto_notes(self, storage):
        v = make_video()
        v.auto_notes = ["Mentioned asyncio event loop"]
        storage.save_video(v)
        results = storage.search_videos("asyncio")
        assert len(results) == 1

    def test_search_case_insensitive(self, storage):
        storage.save_video(make_video(title="Django REST Framework Deep Dive"))
        assert len(storage.search_videos("django")) == 1
        assert len(storage.search_videos("DJANGO")) == 1
        assert len(storage.search_videos("Django")) == 1

    def test_search_no_results(self, storage):
        storage.save_video(make_video(title="Python Basics"))
        assert storage.search_videos("rust") == []


# ---------------------------------------------------------------------------
# delete_video removes video from collections (B8 fix)
# ---------------------------------------------------------------------------

class TestDeleteVideoCleansCollections:
    def test_delete_removes_from_collection(self, storage):
        v = make_video()
        storage.save_video(v)
        coll = make_collection(video_ids=[v.video_id])
        storage.save_collection(coll)

        storage.delete_video(v.video_id)

        reloaded = storage.get_collection(coll.id)
        assert v.video_id not in reloaded.video_ids

    def test_clear_all_wipes_collection_video_ids(self, storage):
        v = make_video()
        storage.save_video(v)
        coll = make_collection(video_ids=[v.video_id])
        storage.save_collection(coll)

        storage.clear_all_videos()

        reloaded = storage.get_collection(coll.id)
        assert reloaded.video_ids == []
