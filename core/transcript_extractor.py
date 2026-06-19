"""Transcript extraction with auto and manual fallback."""

import os
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


class TranscriptExtractor:
    def __init__(self, preferred_languages: list = None):
        self.preferred_languages = preferred_languages or ["en", "en-US", "en-GB", "hi"]

    def extract(self, video_id: str) -> tuple[str, str]:
        """
        Try to auto-extract transcript.
        Returns (transcript_text, source) where source is 'auto' or 'unavailable'.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try preferred languages first
            try:
                transcript = transcript_list.find_transcript(self.preferred_languages)
            except Exception:
                # Fallback: use any available transcript, auto-translate to English
                transcript = list(transcript_list)[0]
                if transcript.language_code not in self.preferred_languages:
                    try:
                        transcript = transcript.translate("en")
                    except Exception:
                        pass

            entries = transcript.fetch()
            text = " ".join([e["text"] for e in entries])
            text = text.replace("\n", " ").strip()
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
            text = f.read().strip()
        return text, "upload"
