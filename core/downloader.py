"""Audio / video downloader using yt-dlp.

Key design decisions
--------------------
* FFmpeg is detected at import time via shutil.which().
* When FFmpeg is missing:
    - audio   → downloads best m4a/webm natively (no conversion, still has audio)
    - video   → downloads best single-file progressive MP4 (has both streams baked in)
* When FFmpeg is present:
    - audio   → extracts MP3 at 192k
    - video   → downloads best video + best audio as separate streams, merges to MP4
* A RuntimeError is raised — never silently delivers a muted file.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

try:
    import yt_dlp  # type: ignore[import-untyped]
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "downloads"

DownloadMode = Literal["audio", "video_720", "video_1080", "video_best"]


def _ffmpeg_available() -> bool:
    """Return True if the ffmpeg binary is on the system PATH."""
    return shutil.which("ffmpeg") is not None


def ffmpeg_version() -> str:
    """Return ffmpeg version string, or empty string if not found."""
    if not _ffmpeg_available():
        return ""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        return first_line  # e.g. "ffmpeg version 7.1 Copyright ..."
    except Exception:
        return ""


class Downloader:
    """Download audio or video from YouTube via yt-dlp."""

    def __init__(self, download_dir: str | None = None) -> None:
        self.download_dir = Path(download_dir) if download_dir else _DEFAULT_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return _YTDLP_AVAILABLE

    def has_ffmpeg(self) -> bool:
        return _ffmpeg_available()

    def download(self, video_id: str, mode: DownloadMode = "audio") -> Path:
        """
        Download audio or video for a YouTube video ID.

        Parameters
        ----------
        video_id : YouTube video ID (e.g. 'dQw4w9WgXcQ')
        mode     : 'audio'       → MP3 192k (ffmpeg) or best m4a/webm (no ffmpeg)
                   'video_720'   → 720p MP4 with audio
                   'video_1080'  → 1080p MP4 with audio
                   'video_best'  → highest quality MP4 with audio

        Returns
        -------
        Path to the downloaded file.

        Raises
        ------
        RuntimeError on any failure (including audio-less download detection).
        """
        if not _YTDLP_AVAILABLE:
            raise RuntimeError(
                "yt-dlp is not installed.\nFix: py -3.11 -m pip install yt-dlp"
            )

        has_ff = _ffmpeg_available()
        url    = f"https://www.youtube.com/watch?v={video_id}"
        opts   = self._build_opts(mode, has_ff)
        opts["outtmpl"] = str(self.download_dir / "%(title)s [%(id)s].%(ext)s")

        downloaded_files: list[str] = []

        def _hook(d: dict[str, Any]) -> None:
            if d.get("status") == "finished":
                fname = d.get("filename", "")
                if fname:
                    downloaded_files.append(fname)

        opts["progress_hooks"] = [_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                ydl.extract_info(url, download=True)
        except Exception as exc:
            raise RuntimeError(f"yt-dlp download failed:\n{exc}") from exc

        return self._resolve_output(video_id, mode, has_ff, downloaded_files)

    # ------------------------------------------------------------------ #
    #  Format selection                                                    #
    # ------------------------------------------------------------------ #

    def _build_opts(self, mode: DownloadMode, has_ff: bool) -> dict[str, Any]:
        base: dict[str, Any] = {
            "quiet":      True,
            "no_warnings": True,
            "noplaylist": True,
        }

        if mode == "audio":
            if has_ff:
                # FFmpeg present: download best audio stream, convert to MP3
                base["format"] = "bestaudio/best"
                base["postprocessors"] = [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": "192",
                }]
            else:
                # No FFmpeg: download best native audio-only stream (m4a preferred)
                # These formats ALREADY contain audio — no merge needed
                base["format"] = (
                    "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"
                )

        elif mode == "video_720":
            if has_ff:
                # Separate best video + best audio, merge with FFmpeg → MP4
                base["format"] = (
                    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=720]+bestaudio"
                    "/best[height<=720]"
                )
                base["merge_output_format"] = "mp4"
            else:
                # Progressive MP4: video + audio already in one container
                # YouTube provides these up to 720p
                base["format"] = (
                    "best[height<=720][ext=mp4]"
                    "/best[height<=720]"
                    "/best"
                )

        elif mode == "video_1080":
            if has_ff:
                base["format"] = (
                    "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=1080]+bestaudio"
                    "/best[height<=1080]"
                )
                base["merge_output_format"] = "mp4"
            else:
                # 1080p progressive MP4 is rarely available — fall back to 720p
                base["format"] = (
                    "best[height<=1080][ext=mp4]"
                    "/best[height<=720][ext=mp4]"
                    "/best"
                )

        else:  # video_best
            if has_ff:
                base["format"] = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo+bestaudio"
                    "/best"
                )
                base["merge_output_format"] = "mp4"
            else:
                # Without FFmpeg, best we can do is best progressive MP4
                base["format"] = (
                    "best[ext=mp4]/best"
                )

        return base

    # ------------------------------------------------------------------ #
    #  Output resolution                                                   #
    # ------------------------------------------------------------------ #

    def _resolve_output(
        self,
        video_id: str,
        mode: DownloadMode,
        had_ff: bool,
        downloaded_files: list[str],
    ) -> Path:
        """Find and validate the final output file."""

        # 1. Check hook-reported filenames first
        for fname in reversed(downloaded_files):
            p = Path(fname)
            # FFmpeg renames .webm/.m4a → .mp3 after audio postprocess
            if mode == "audio" and had_ff:
                mp3 = p.with_suffix(".mp3")
                if mp3.exists():
                    return mp3
            if p.exists():
                self._assert_has_audio(p, mode)
                return p

        # 2. Scan downloads/ for newest file matching video_id
        candidates = sorted(
            self.download_dir.glob(f"*{video_id}*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            best = candidates[0]
            self._assert_has_audio(best, mode)
            return best

        raise RuntimeError(
            "Download appeared to succeed but the output file was not found.\n"
            f"Check the downloads/ folder manually for video ID: {video_id}"
        )

    def _assert_has_audio(self, path: Path, mode: DownloadMode) -> None:
        """
        For video modes: use ffprobe (part of ffmpeg) to verify the file
        actually has an audio stream. Raises RuntimeError if audio is absent.
        Only runs if ffmpeg is available — otherwise we trust the format string.
        """
        if mode == "audio":
            return  # audio-only file — no video stream expected, skip check
        if not _ffmpeg_available():
            return  # can't probe without ffprobe — trust the progressive format

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=codec_type",
                    "-of", "csv=p=0",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15
            )
            if "audio" not in result.stdout:
                # File has no audio stream — delete it and raise a clear error
                path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Downloaded file had NO audio stream and was deleted.\n"
                    f"File: {path.name}\n"
                    f"This usually means FFmpeg couldn't merge streams.\n"
                    f"Fix: close any programs using the file, then try again."
                )
        except RuntimeError:
            raise
        except Exception:
            pass  # ffprobe failed for unrelated reason — don't block the download
