"""Tests for the Video data model."""

from models.video import Video, WatchStatus


def test_default_status():
    v = Video(
        video_id="abc123defgh",
        url="https://www.youtube.com/watch?v=abc123defgh",
        title="Test",
        channel="Channel",
        thumbnail_url="",
        published_at="2024-01-01T00:00:00Z",
        duration="5:00",
    )
    assert v.status == WatchStatus.SAVED


def test_to_dict_and_from_dict():
    v = Video(
        video_id="abc123defgh",
        url="https://www.youtube.com/watch?v=abc123defgh",
        title="Test",
        channel="Channel",
        thumbnail_url="",
        published_at="2024-01-01T00:00:00Z",
        duration="5:00",
        status=WatchStatus.WATCHING,
        transcript_text="Hello world",
        summary_bullets=["Point one", "Point two"],
        summary_paragraph="A short summary.",
        manual_notes="My notes here.",
    )
    d = v.to_dict()
    assert d["status"] == "watching"
    v2 = Video.from_dict(d)
    assert v2.status == WatchStatus.WATCHING
    assert v2.manual_notes == "My notes here."
    assert v2.summary_bullets == ["Point one", "Point two"]


def test_all_watch_statuses():
    for status in WatchStatus:
        v = Video(
            video_id="abc123defgh",
            url="https://www.youtube.com/watch?v=abc123defgh",
            title="Test",
            channel="Channel",
            thumbnail_url="",
            published_at="2024-01-01T00:00:00Z",
            duration="5:00",
            status=status,
        )
        d = v.to_dict()
        v2 = Video.from_dict(d)
        assert v2.status == status
