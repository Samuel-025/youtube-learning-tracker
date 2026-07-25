"""Unit tests for transcript extractor 429 rate limit resilience."""

from unittest.mock import MagicMock, patch
from pathlib import Path
from core.transcript_extractor import TranscriptExtractor


def test_download_vtt_fallback_on_error(tmp_path):
    extractor = TranscriptExtractor(preferred_languages=["en", "hi"])

    # Simulate yt-dlp raising an exception on the first attempt (all languages)
    # but succeeding on the single-language attempt ('en') by creating a .vtt file
    vtt_file = tmp_path / "test.vtt"

    def mock_download(urls):
        # Create dummy vtt on second call
        vtt_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nHello World\n", encoding="utf-8")

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        instance = mock_ydl_cls.return_value.__enter__.return_value
        instance.download.side_effect = mock_download

        res = extractor._download_vtt("https://www.youtube.com/watch?v=dQw4w9WgXcQ", str(tmp_path), "manual")
        assert res is not None
        assert res.name == "test.vtt"
