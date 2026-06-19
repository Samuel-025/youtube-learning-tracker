"""Audio / video downloader using yt-dlp."""

import os
from pathlib import Path
from typing import Any, Literal

try:
    import yt_dlp  # type: ignore[import-untyped]
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False

# Default download folder: project_root/downloads/
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "downloads"

DownloadMode = Literal["audio", "video_720", "video_1080", "video_best"]


class Downloader:
    """Download audio or video for a YouTube URL via yt-dlp."""

    def __init__(self, download_dir: str | None = None) -> None:
        self.download_dir = Path(download_dir) if download_dir else _DEFAULT_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        return _YTDLP_AVAILABLE

    def download(self, video_id: str, mode: DownloadMode = "audio") -> Path:
        """
        Download a YouTube video.

        Parameters
        ----------
        video_id : str   YouTube video ID (not full URL)
        mode     : str   'audio'        → best MP3 (192k)
                         'video_720'    → MP4 up to 720p + audio merged
                         'video_1080'   → MP4 up to 1080p + audio merged
                         'video_best'   → best available quality

        Returns
        -------
        Path  Absolute path to the downloaded file.

        Raises
        ------
        RuntimeError  if yt-dlp is not installed or download fails.
        """
        if not _YTDLP_AVAILABLE:
            raise RuntimeError(
                "yt-dlp is not installed. Run: py -3.11 -m pip install yt-dlp"
            )

        url = f"https://www.youtube.com/watch?v={video_id}"
        opts = self._build_opts(mode)
        opts["outtmpl"] = str(self.download_dir / "%(title)s [%(id)s].%(ext)s")

        # Collect the actual output filename from yt-dlp's postprocessor hook
        downloaded_files: list[str] = []

        def _hook(d: dict[str, Any]) -> None:
            if d.get("status") == "finished":
                downloaded_files.append(d.get("filename", ""))

        opts["progress_hooks"] = [_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc

        # Resolve final path: prefer hook result, fall back to yt-dlp info dict
        if downloaded_files:
            path = Path(downloaded_files[-1])
            # For audio, yt-dlp renames .webm/.m4a → .mp3 after postprocess
            if mode == "audio":
                mp3 = path.with_suffix(".mp3")
                if mp3.exists():
                    return mp3
            if path.exists():
                return path

        # Last resort: scan download dir for newest file matching the video id
        candidates = sorted(
            self.download_dir.glob(f"*{video_id}*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

        raise RuntimeError("Download appeared to succeed but output file not found.")

    # ------------------------------------------------------------------ #
    #  Internal                                                            #
    # ------------------------------------------------------------------ #

    def _build_opts(self, mode: DownloadMode) -> dict[str, Any]:
        base: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        if mode == "audio":
            base.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })

        elif mode == "video_720":
            base["format"] = (
                "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            )
            base["merge_output_format"] = "mp4"

        elif mode == "video_1080":
            base["format"] = (
                "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            )
            base["merge_output_format"] = "mp4"

        else:  # video_best
            base["format"] = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            )
            base["merge_output_format"] = "mp4"

        return base
