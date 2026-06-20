"""Shared pytest fixtures for YouTube Learning Tracker test suite."""

import pytest
from models.video import Video, WatchStatus
from models.collection import Collection
from core.storage import Storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_video(
    video_id: str = "abcdefghijk",
    title: str = "Test Video",
    channel: str = "Test Channel",
    duration: str = "10:00",
    status: WatchStatus = WatchStatus.SAVED,
    tags: list[str] | None = None,
) -> Video:
    return Video(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title=title,
        channel=channel,
        thumbnail_url="https://img.youtube.com/vi/abcdefghijk/hqdefault.jpg",
        published_at="2024-01-01T00:00:00Z",
        duration=duration,
        status=status,
        tags=tags or [],
    )


def make_collection(name: str = "My Collection", video_ids: list[str] | None = None) -> Collection:
    return Collection(name=name, video_ids=video_ids or [])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def storage(tmp_path):
    """Isolated Storage instance backed by a temp directory — never touches data/."""
    return Storage(str(tmp_path / "videos.json"))


@pytest.fixture
def video():
    """A default unsaved Video object."""
    return make_video()


@pytest.fixture
def collection():
    """A default unsaved Collection object."""
    return make_collection()
