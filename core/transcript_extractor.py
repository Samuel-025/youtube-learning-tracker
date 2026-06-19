"""Transcript extraction: yt-dlp primary, youtube-transcript-api fallback."""

import os
import re
import json
import tempfile
from pathlib import Path
from typing import Optional

# yt-dlp (primary)
try:
    import yt_dlp  # type: ignore[import-untyped]
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False

# youtube-transcript-api (fallback)
try:
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import-untyped]
    _YT_AVAILABLE = True
except ImportError:
    _YT_AVAILABLE = False

# Strip VTT markup tags like <00:00:01.000>, <c>, </c>
_VTT_TAG_RE    = re.compile(r"<[^>]+>")
_TIMESTAMP_LINE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}"
)


class TranscriptExtractor:
    DEFAULT_LANGUAGES: list[str] = ["en", "en-US", "en-GB", "hi"]

    def __init__(self, preferred_languages: Optional[list[str]] = None):
        self.preferred_languages: list[str] = (
            preferred_languages or self.DEFAULT_LANGUAGES
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def extract(self, video_id: str) -> tuple[str, str]:
        """
        Auto-extract transcript for *video_id*.
        Returns (transcript_text, source_label).
        Tries yt-dlp first, falls back to youtube-transcript-api.
        """
        # 1. yt-dlp
        if _YTDLP_AVAILABLE:
            text, src = self._extract_ytdlp(video_id)
            if text:
                return text, src

        # 2. youtube-transcript-api fallback
        if _YT_AVAILABLE:
            text, src = self._extract_yt_api(video_id)
            if text:
                return text, src

        return "", "unavailable"

    def from_text(self, text: str) -> tuple[str, str]:
        """Accept manually pasted transcript text."""
        return text.strip(), "manual"

    def from_file(self, filepath: str) -> tuple[str, str]:
        """Accept transcript from uploaded .txt file."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content, "upload"

    # ------------------------------------------------------------------ #
    #  yt-dlp extractor                                                    #
    # ------------------------------------------------------------------ #

    def _extract_ytdlp(self, video_id: str) -> tuple[str, str]:
        """Download subtitles via yt-dlp and parse into timestamped text."""
        url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try manual subs first, then auto-generated
            for sub_type, ydl_key in [("manual", "subtitles"), ("auto", "automatic_captions")]:
                vtt_path = self._download_vtt(url, tmpdir, sub_type)
                if vtt_path:
                    text = self._parse_vtt(vtt_path)
                    if text:
                        src = f"yt-dlp ({sub_type} subs)"
                        return text, src

        return "", ""

    def _download_vtt(self, url: str, outdir: str, sub_type: str) -> Optional[Path]:
        """Use yt-dlp to download the best available subtitle file to outdir."""
        lang_codes = self.preferred_languages + ["en"]

        ydl_opts: dict = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
            "subtitlesformat": "vtt",
            "subtitleslangs": lang_codes,
        }

        if sub_type == "manual":
            ydl_opts["writesubtitles"] = True
        else:
            ydl_opts["writeautomaticsub"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception:
            pass

        # Find the downloaded .vtt file
        for f in Path(outdir).glob("*.vtt"):
            return f
        return None

    def _parse_vtt(self, vtt_path: Path) -> str:
        """Parse a VTT subtitle file into clean [MM:SS] timestamped lines."""
        raw = vtt_path.read_text(encoding="utf-8", errors="ignore")
        lines = raw.splitlines()

        segments: list[tuple[float, str]] = []
        current_start: Optional[float] = None
        current_text: list[str] = []

        for line in lines:
            line = line.strip()

            # Timestamp line: 00:00:01.000 --> 00:00:04.000
            if _TIMESTAMP_LINE.match(line):
                # Save previous segment
                if current_start is not None and current_text:
                    text = " ".join(current_text).strip()
                    if text:
                        segments.append((current_start, text))
                # Parse new start time
                start_str = line.split("-->")[0].strip()
                current_start = self._vtt_time_to_seconds(start_str)
                current_text = []

            elif line and not line.startswith("WEBVTT") and not line.isdigit() and "-->" not in line:
                # Content line — strip VTT markup tags
                clean = _VTT_TAG_RE.sub("", line).strip()
                if clean and clean not in current_text:
                    current_text.append(clean)

        # Flush last segment
        if current_start is not None and current_text:
            text = " ".join(current_text).strip()
            if text:
                segments.append((current_start, text))

        # Deduplicate consecutive identical lines (auto-subs repeat a lot)
        deduped: list[tuple[float, str]] = []
        prev = ""
        for start, text in segments:
            if text != prev:
                deduped.append((start, text))
                prev = text

        # Format with timestamps
        parts: list[str] = []
        for start, text in deduped:
            total_sec = int(start)
            hours, rem = divmod(total_sec, 3600)
            mins, secs = divmod(rem, 60)
            ts = f"[{hours}:{mins:02d}:{secs:02d}]" if hours else f"[{mins:02d}:{secs:02d}]"
            parts.append(f"{ts} {text}")

        return "\n".join(parts)

    @staticmethod
    def _vtt_time_to_seconds(ts: str) -> float:
        """Convert VTT timestamp HH:MM:SS.mmm to total seconds."""
        try:
            ts = ts.split(".")[0]  # drop milliseconds
            parts = ts.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + int(s)
            elif len(parts) == 2:
                m, s = parts
                return int(m) * 60 + int(s)
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------ #
    #  youtube-transcript-api fallback                                     #
    # ------------------------------------------------------------------ #

    def _extract_yt_api(self, video_id: str) -> tuple[str, str]:
        """Fallback: extract via youtube-transcript-api."""
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
                try:
                    transcript = transcript.translate("en")
                except Exception:
                    pass

            entries = transcript.fetch()
            parts: list[str] = []
            for entry in entries:
                if isinstance(entry, dict):
                    start = entry.get("start", 0)
                    text  = entry.get("text", "").replace("\n", " ").strip()
                else:
                    start = float(getattr(entry, "start", 0))
                    text  = str(getattr(entry, "text", "")).replace("\n", " ").strip()
                if not text:
                    continue
                total_sec = int(start)
                hours, rem = divmod(total_sec, 3600)
                mins, secs = divmod(rem, 60)
                ts = f"[{hours}:{mins:02d}:{secs:02d}]" if hours else f"[{mins:02d}:{secs:02d}]"
                parts.append(f"{ts} {text}")

            return "\n".join(parts).strip(), "youtube-transcript-api"
        except Exception:
            return "", "unavailable"
