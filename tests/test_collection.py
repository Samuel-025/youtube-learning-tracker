"""Tests for the Collection model and Storage collection methods."""

import pytest
from models.collection import Collection
from helpers import make_video, make_collection


# ---------------------------------------------------------------------------
# Collection model
# ---------------------------------------------------------------------------

class TestCollectionModel:
    def test_default_id_is_full_uuid(self):
        coll = make_collection()
        parts = coll.id.split("-")
        assert len(parts) == 5, "UUID4 must have 5 hyphen-separated groups"
        assert len(coll.id) == 36

    def test_video_count_property(self):
        coll = make_collection(video_ids=["a", "b", "c"])
        assert coll.video_count == 3

    def test_to_dict_and_from_dict(self):
        coll = make_collection(name="ML Course", video_ids=["vid1", "vid2"])
        coll.emoji = "🤖"
        coll.description = "Machine learning videos"
        d = coll.to_dict()
        coll2 = Collection.from_dict(d)
        assert coll2.name == "ML Course"
        assert coll2.emoji == "🤖"
        assert coll2.description == "Machine learning videos"
        assert coll2.video_ids == ["vid1", "vid2"]

    def test_from_dict_unknown_keys_dropped(self):
        d = make_collection().to_dict()
        d["future_key"] = "future_value"
        coll2 = Collection.from_dict(d)
        assert not hasattr(coll2, "future_key")

    def test_update_timestamp_changes_updated_at(self):
        import time
        coll = make_collection()
        old = coll.updated_at
        time.sleep(0.01)
        coll.update_timestamp()
        assert coll.updated_at > old


# ---------------------------------------------------------------------------
# Storage — Collection CRUD
# ---------------------------------------------------------------------------

class TestCollectionCRUD:
    def test_save_and_get(self, storage):
        coll = make_collection(name="Algorithms")
        storage.save_collection(coll)
        result = storage.get_collection(coll.id)
        assert result is not None
        assert result.name == "Algorithms"

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_collection("ghost-id") is None

    def test_get_all_empty(self, storage):
        assert storage.get_all_collections() == []

    def test_get_all_sorted_by_created_at(self, storage):
        import time
        c1 = make_collection(name="First")
        time.sleep(0.01)
        c2 = make_collection(name="Second")
        storage.save_collection(c1)
        storage.save_collection(c2)
        colls = storage.get_all_collections()
        assert colls[0].name == "First"
        assert colls[1].name == "Second"

    def test_delete_collection(self, storage):
        coll = make_collection()
        storage.save_collection(coll)
        assert storage.delete_collection(coll.id) is True
        assert storage.get_collection(coll.id) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_collection("ghost-id") is False


# ---------------------------------------------------------------------------
# add / remove video from collection
# ---------------------------------------------------------------------------

class TestCollectionMembership:
    def test_add_video_to_collection(self, storage):
        coll = make_collection()
        storage.save_collection(coll)
        v = make_video()
        storage.save_video(v)
        storage.add_video_to_collection(coll.id, v.video_id)
        reloaded = storage.get_collection(coll.id)
        assert v.video_id in reloaded.video_ids

    def test_add_video_idempotent(self, storage):
        coll = make_collection()
        storage.save_collection(coll)
        v = make_video()
        storage.save_video(v)
        storage.add_video_to_collection(coll.id, v.video_id)
        storage.add_video_to_collection(coll.id, v.video_id)
        reloaded = storage.get_collection(coll.id)
        assert reloaded.video_ids.count(v.video_id) == 1

    def test_remove_video_from_collection(self, storage):
        v = make_video()
        storage.save_video(v)
        coll = make_collection(video_ids=[v.video_id])
        storage.save_collection(coll)
        storage.remove_video_from_collection(coll.id, v.video_id)
        reloaded = storage.get_collection(coll.id)
        assert v.video_id not in reloaded.video_ids

    def test_remove_video_not_in_collection_returns_false(self, storage):
        coll = make_collection()
        storage.save_collection(coll)
        assert storage.remove_video_from_collection(coll.id, "ghost_vid") is False

    def test_add_video_to_nonexistent_collection_returns_false(self, storage):
        assert storage.add_video_to_collection("ghost-coll", "vid1") is False


# ---------------------------------------------------------------------------
# get_videos_in_collection — B8 fix (O(1) lookup, no N+1)
# ---------------------------------------------------------------------------

class TestGetVideosInCollection:
    def test_returns_correct_videos(self, storage):
        v1 = make_video("vid1aaaaaaa")
        v2 = make_video("vid2aaaaaaa")
        v3 = make_video("vid3aaaaaaa")
        for v in [v1, v2, v3]:
            storage.save_video(v)
        coll = make_collection(video_ids=["vid1aaaaaaa", "vid3aaaaaaa"])
        storage.save_collection(coll)
        result = storage.get_videos_in_collection(coll.id)
        ids = [v.video_id for v in result]
        assert "vid1aaaaaaa" in ids
        assert "vid3aaaaaaa" in ids
        assert "vid2aaaaaaa" not in ids

    def test_skips_missing_video_ids_gracefully(self, storage):
        coll = make_collection(video_ids=["deleted_vid_id"])
        storage.save_collection(coll)
        result = storage.get_videos_in_collection(coll.id)
        assert result == []

    def test_nonexistent_collection_returns_empty(self, storage):
        assert storage.get_videos_in_collection("ghost-id") == []

    def test_get_collections_for_video(self, storage):
        v = make_video()
        storage.save_video(v)
        c1 = make_collection(name="C1", video_ids=[v.video_id])
        c2 = make_collection(name="C2", video_ids=[v.video_id])
        c3 = make_collection(name="C3")
        for c in [c1, c2, c3]:
            storage.save_collection(c)
        result = storage.get_collections_for_video(v.video_id)
        names = {c.name for c in result}
        assert names == {"C1", "C2"}
