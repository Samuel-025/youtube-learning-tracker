"""Tests for Storage class."""

import pytest
import json
import os
from pathlib import Path
from models.video import Video, WatchStatus
from core.storage import Storage


@pytest.fixture
def tmp_storage(tmp_path):
    path = str(tmp_path / "videos.json")
    return Storage(path)


def make_video(video_id="abc123defgh"):
    return Video(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title="Test Video",
        channel="Test Channel",
        thumbnail_url="https://img.youtube.com/vi/abc123defgh/hqdefault.jpg",
        published_at="2024-01-01T00:00:00Z",
        duration="10:00",
    )


def test_save_and_get(tmp_storage):
    video = make_video()
    tmp_storage.save_video(video)
    result = tmp_storage.get_video(video.video_id)
    assert result is not None
    assert result.title == "Test Video"


def test_get_all(tmp_storage):
    tmp_storage.save_video(make_video("id1aaaaaaaa"))
    tmp_storage.save_video(make_video("id2aaaaaaaa"))
    all_videos = tmp_storage.get_all_videos()
    assert len(all_videos) == 2


def test_delete(tmp_storage):
    video = make_video()
    tmp_storage.save_video(video)
    assert tmp_storage.delete_video(video.video_id) is True
    assert tmp_storage.get_video(video.video_id) is None


def test_status_filter(tmp_storage):
    v1 = make_video("id1aaaaaaaa")
    v2 = make_video("id2aaaaaaaa")
    v2.status = WatchStatus.COMPLETED
    tmp_storage.save_video(v1)
    tmp_storage.save_video(v2)
    completed = tmp_storage.filter_by_status(WatchStatus.COMPLETED)
    assert len(completed) == 1
    assert completed[0].video_id == "id2aaaaaaaa"


def test_search(tmp_storage):
    v = make_video()
    v.title = "Python Tutorial for Beginners"
    tmp_storage.save_video(v)
    results = tmp_storage.search_videos("python")
    assert len(results) == 1


def test_count_by_status(tmp_storage):
    tmp_storage.save_video(make_video("id1aaaaaaaa"))
    v2 = make_video("id2aaaaaaaa")
    v2.status = WatchStatus.WATCHING
    tmp_storage.save_video(v2)
    counts = tmp_storage.count_by_status()
    assert counts["saved"] == 1
    assert counts["watching"] == 1
