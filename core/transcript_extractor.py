"""Transcript extraction with auto and manual fallback."""

import os
from typing import Optional

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
    _YT_AVAILABLE = True
except ImportError:
    _YT_AVAILABLE = False
    TranscriptsDisabled = Exception  # type: ignore
    NoTranscriptFound = Exception    # type: ignore


class TranscriptExtractor:
    DEFAULT_LANGUAGES: list[str] = ["en", "en-US", "en-GB", "hi"]

    def __init__(self, preferred_languages: Optional[list[str]] = None):
        self.preferred_languages: list[str] = (
            preferred_languages if preferred_languages is not None else self.DEFAULT_LANGUAGES
        )

    def extract(self, video_id: str) -> tuple[str, str]:
        """
        Try to auto-extract transcript.
        Returns (transcript_text, source) where source is 'auto' or 'unavailable'.
        Transcript text includes [MM:SS] or [HH:MM:SS] timestamps for each segment.
        """
        if not _YT_AVAILABLE:
            return "", "unavailable (youtube-transcript-api not installed)"

        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            try:
                transcript = transcript_list.find_transcript(self.preferred_languages)
            except Exception:
                available = list(transcript_list)
                if not available:
                    return "", "unavailable"
                transcript = available[0]
                if transcript.language_code not in self.preferred_languages:
                    try:
                        transcript = transcript.translate("en")
                    except Exception:
                        pass

            entries = transcript.fetch()
            text_parts: list[str] = []
            for entry in entries:
                if isinstance(entry, dict):
                    start = entry.get("start", 0)
                    text  = entry.get("text", "").replace("\n", " ").strip()
                else:
                    start = float(getattr(entry, "start", 0))
                    text  = str(getattr(entry, "text", "")).replace("\n", " ").strip()

                if not text:
                    continue

                # Format timestamp — [MM:SS] for videos <100 min, [HHH:MM:SS] for longer
                total_sec = int(start)
                hours, remainder = divmod(total_sec, 3600)
                mins, secs = divmod(remainder, 60)
                if hours > 0:
                    timestamp = f"[{hours}:{mins:02d}:{secs:02d}]"
                else:
                    timestamp = f"[{mins:02d}:{secs:02d}]"
                text_parts.append(f"{timestamp} {text}")

            text = "\n".join(text_parts).strip()
            return text, "auto"

        except Exception:
            return "", "unavailable"

    def from_text(self, text: str) -> tuple[str, str]:
        """Accept manually pasted transcript text."""
        return text.strip(), "manual"

    def from_file(self, filepath: str) -> tuple[str, str]:
        """Accept transcript from uploaded .txt file."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content, "upload"
