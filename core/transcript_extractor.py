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
    # Explicit list — never None, so Pylance is satisfied
    DEFAULT_LANGUAGES: list[str] = ["en", "en-US", "en-GB", "hi"]

    def __init__(self, preferred_languages: Optional[list[str]] = None):
        self.preferred_languages: list[str] = (
            preferred_languages if preferred_languages is not None else self.DEFAULT_LANGUAGES
        )

    def extract(self, video_id: str) -> tuple[str, str]:
        """
        Try to auto-extract transcript.
        Returns (transcript_text, source) where source is 'auto' or 'unavailable'.
        """
        if not _YT_AVAILABLE:
            return "", "unavailable (youtube-transcript-api not installed)"

        try:
            # v1.x API: instantiate first, then call instance method
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list_transcripts(video_id)

            # Try preferred languages first
            try:
                transcript = transcript_list.find_transcript(self.preferred_languages)
            except Exception:
                # Fallback: use first available, try to translate to English
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
            # youtube-transcript-api >= 1.0 returns FetchedTranscript (iterable of dicts)
            text_parts: list[str] = []
            for entry in entries:
                if isinstance(entry, dict):
                    text_parts.append(entry.get("text", ""))
                else:
                    # FetchedTranscriptSnippet object
                    text_parts.append(str(getattr(entry, "text", "")))

            text = " ".join(text_parts).replace("\n", " ").strip()
            return text, "auto"

        except (TranscriptsDisabled, NoTranscriptFound):
            return "", "unavailable"
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
