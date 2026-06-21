"""Shared factory helpers for the test suite.

Import from here in all test modules:
    from helpers import make_video, make_collection

Do NOT import from conftest directly — pytest auto-loads conftest but does
not put it on sys.path as a regular module.
"""

from models.video import Video, WatchStatus
from models.collection import Collection


def make_video(
    video_id: str = "abcdefghijk",
    title: str = "Test Video",
    channel: str = "Test Channel",
    duration: str = "10:00",
    status: WatchStatus = WatchStatus.SAVED,
    tags: list | None = None,
    rating: int = 0,
    due_date: str | None = None,
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
        rating=rating,
        due_date=due_date,
    )


def make_collection(name: str = "My Collection", video_ids: list | None = None) -> Collection:
    return Collection(name=name, video_ids=video_ids or [])
