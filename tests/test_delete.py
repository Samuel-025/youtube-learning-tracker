"""Unit tests for video deletion & batch cleanup features in storage.py and cli.py."""

from unittest.mock import MagicMock, patch
from argparse import Namespace
from pathlib import Path
from models.video import Video, WatchStatus
from core.storage import Storage
import cli


def make_video(video_id: str, local_path: str | None = None) -> Video:
    return Video(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=f"Title {video_id}",
        channel="Test Channel",
        thumbnail_url="http://example.com/thumb.jpg",
        published_at="2026-01-01",
        duration="10:00",
        local_path=local_path,
    )


def test_delete_video_with_file_cleanup(tmp_path):
    storage_file = tmp_path / "videos.json"
    storage = Storage(str(storage_file))

    dummy_media = tmp_path / "test_vid.mp4"
    dummy_media.write_text("dummy video content")

    v = make_video("v123", str(dummy_media))
    storage.save_video(v)
    assert storage.get_video("v123") is not None
    assert dummy_media.exists()

    res = storage.delete_video("v123", delete_local_file=True)
    assert res is True
    assert storage.get_video("v123") is None
    assert not dummy_media.exists()


def test_delete_videos_batch(tmp_path):
    storage_file = tmp_path / "videos.json"
    storage = Storage(str(storage_file))

    v1 = make_video("v1")
    v2 = make_video("v2")
    v3 = make_video("v3")
    storage.save_video(v1)
    storage.save_video(v2)
    storage.save_video(v3)

    count = storage.delete_videos_batch(["v1", "v3"])
    assert count == 2
    assert storage.get_video("v1") is None
    assert storage.get_video("v2") is not None
    assert storage.get_video("v3") is None


def test_cli_delete_command(capsys):
    args = Namespace(command="delete", video_id="non_existent_id", keep_file=False)
    cli.cmd_delete(args)
    captured = capsys.readouterr()
    assert "Video not found" in captured.out
