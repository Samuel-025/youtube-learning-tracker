"""YouTube Data API v3 wrapper for fetching video metadata."""

import os
import re
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import isodate
from models.video import Video


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from any valid YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


class YouTubeFetcher:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self._service = None

    def _get_service(self):
        if not self._service:
            if not self.api_key:
                raise ValueError("YOUTUBE_API_KEY not set. Add it to your .env file.")
            self._service = build("youtube", "v3", developerKey=self.api_key)
        return self._service

    def fetch_video(self, url: str) -> Optional[Video]:
        """Fetch video metadata from YouTube and return a Video object."""
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        try:
            service = self._get_service()
            response = service.videos().list(
                part="snippet,contentDetails,statistics",
                id=video_id
            ).execute()

            items = response.get("items", [])
            if not items:
                raise ValueError(f"No video found for ID: {video_id}")

            item = items[0]
            snippet = item["snippet"]
            content = item["contentDetails"]

            duration_iso = content.get("duration", "PT0S")
            duration_sec = int(isodate.parse_duration(duration_iso).total_seconds())
            minutes, seconds = divmod(duration_sec, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes}:{seconds:02d}"

            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("maxres", {})
                or thumbnails.get("high", {})
                or thumbnails.get("medium", {})
                or thumbnails.get("default", {})
            ).get("url", "")

            return Video(
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=snippet.get("title", "Unknown Title"),
                channel=snippet.get("channelTitle", "Unknown Channel"),
                thumbnail_url=thumbnail_url,
                published_at=snippet.get("publishedAt", ""),
                duration=duration_str,
            )

        except HttpError as e:
            raise RuntimeError(f"YouTube API error: {e.reason}") from e
