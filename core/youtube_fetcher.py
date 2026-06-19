"""YouTube Data API v3 wrapper — video metadata fetcher."""

import os
import re
from typing import Optional

from googleapiclient.discovery import build   # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
import isodate                                 # type: ignore[import-untyped]

from models.video import Video


def extract_video_id(url: str) -> Optional[str]:
    """Extract the 11-char video ID from any valid YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _best_thumbnail(thumbnails: dict) -> str:
    """Return the highest-quality thumbnail URL available."""
    for quality in ("maxres", "standard", "high", "medium", "default"):
        url = thumbnails.get(quality, {}).get("url", "")
        if url:
            return url
    return ""


class YouTubeFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self._service = None

    def _get_service(self):
        if not self._service:
            if not self.api_key:
                raise ValueError(
                    "YOUTUBE_API_KEY is not set. "
                    "Add it to your .env file: YOUTUBE_API_KEY=your_key_here"
                )
            self._service = build("youtube", "v3", developerKey=self.api_key)
        return self._service

    def fetch_video(self, url: str) -> Video:
        """
        Fetch video metadata from the YouTube Data API v3.
        Returns a Video object.  Raises ValueError / RuntimeError on failure.
        """
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract a video ID from: {url!r}")

        try:
            service = self._get_service()
            response = service.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id,
            ).execute()
        except HttpError as exc:
            raise RuntimeError(f"YouTube API error: {exc.reason}") from exc

        items = response.get("items", [])
        if not items:
            raise ValueError(
                f"No video found for ID {video_id!r}. "
                "The video may be private, deleted, or the ID is wrong."
            )

        item    = items[0]
        snippet = item["snippet"]
        content = item["contentDetails"]

        # Duration
        duration_iso = content.get("duration", "PT0S")
        duration_sec = int(isodate.parse_duration(duration_iso).total_seconds())
        mins, secs   = divmod(duration_sec, 60)
        hours, mins  = divmod(mins, 60)
        duration_str = (
            f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
        )

        return Video(
            video_id      = video_id,
            url           = f"https://www.youtube.com/watch?v={video_id}",
            title         = snippet.get("title", "Unknown Title"),
            channel       = snippet.get("channelTitle", "Unknown Channel"),
            thumbnail_url = _best_thumbnail(snippet.get("thumbnails", {})),
            published_at  = snippet.get("publishedAt", ""),
            duration      = duration_str,
        )
