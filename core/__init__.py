"""Core package — lazy imports to avoid hard crash on missing dependencies."""
# Classes are imported lazily so a missing optional dependency
# (e.g. google-api-python-client, anthropic, groq) only errors when
# that specific feature is used, not at app startup.

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import Storage
    from .youtube_fetcher import YouTubeFetcher
    from .transcript_extractor import TranscriptExtractor
    from .summarizer import Summarizer
    from .notes_generator import NotesGenerator


def __getattr__(name: str):
    if name == "Storage":
        from .storage import Storage
        return Storage
    if name == "YouTubeFetcher":
        from .youtube_fetcher import YouTubeFetcher
        return YouTubeFetcher
    if name == "TranscriptExtractor":
        from .transcript_extractor import TranscriptExtractor
        return TranscriptExtractor
    if name == "Summarizer":
        from .summarizer import Summarizer
        return Summarizer
    if name == "NotesGenerator":
        from .notes_generator import NotesGenerator
        return NotesGenerator
    raise AttributeError(f"module 'core' has no attribute {name!r}")


__all__ = [
    "Storage",
    "YouTubeFetcher",
    "TranscriptExtractor",
    "Summarizer",
    "NotesGenerator",
]
