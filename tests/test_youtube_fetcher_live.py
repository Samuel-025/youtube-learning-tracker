"""Unit tests for YouTube URL parser including live URLs."""

from core.youtube_fetcher import extract_video_id


def test_extract_video_id_live_url():
    url = "https://www.youtube.com/live/v8bXHLxuTUs?si=H3jz2hcTc0r2uIiD"
    assert extract_video_id(url) == "v8bXHLxuTUs"


def test_extract_video_id_standard_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_shorts_url():
    url = "https://www.youtube.com/shorts/abcdefghijk"
    assert extract_video_id(url) == "abcdefghijk"
