"""Audio / video downloader using yt-dlp.

Key design decisions
--------------------
* Video formats explicitly prefer H.264 (vcodec^=avc1) to avoid AV1/VP9 which
  Windows Media Player and many devices cannot decode.
* FFmpeg path is passed directly via `ffmpeg_location` opt.
* Verbose warnings are captured and stored in `last_warnings`.
* RuntimeError is raised if a downloaded video file has no audio stream.
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


def _ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _ffmpeg_available() -> bool:
    return _ffmpeg_path() is not None


def ffmpeg_version() -> str:
    path = _ffmpeg_path()
    if not path:
        return ""
    try:
        result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=5)
        return result.stdout.splitlines()[0] if result.stdout else ""
    except Exception:
        return ""


class Downloader:
    """Download audio or video from YouTube via yt-dlp."""

    def __init__(self, download_dir: str | None = None) -> None:
        self.download_dir = Path(download_dir) if download_dir else _DEFAULT_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.last_warnings: list[str] = []

    def is_available(self) -> bool:
        return _YTDLP_AVAILABLE

    def has_ffmpeg(self) -> bool:
        return _ffmpeg_available()

    def download(self, video_id: str, mode: DownloadMode = "audio") -> Path:
        if not _YTDLP_AVAILABLE:
            raise RuntimeError("yt-dlp is not installed.\nFix: py -3.11 -m pip install yt-dlp")

        ff_path = _ffmpeg_path()
        url     = f"https://www.youtube.com/watch?v={video_id}"
        opts    = self._build_opts(mode, ff_path)
        opts["outtmpl"] = str(self.download_dir / "%(title)s [%(id)s].%(ext)s")

        log_lines: list[str] = []
        # fix #2: track the *final* output path reported by yt-dlp after merging/post-processing
        final_filepath: list[str] = []

        class _Logger:
            def debug(self, msg: str) -> None: pass
            def warning(self, msg: str) -> None: log_lines.append(f"WARN: {msg}")
            def error(self, msg: str) -> None: log_lines.append(f"ERR:  {msg}")

        def _hook(d: dict[str, Any]) -> None:
            # fix #2: prefer 'info_dict' final filename over raw 'filename'
            # After merging, yt-dlp sets status='finished' on the merged file.
            if d.get("status") == "finished":
                # info_dict holds the merged output path after post-processing
                info = d.get("info_dict") or {}
                fname = (
                    info.get("filepath")
                    or info.get("_filename")
                    or d.get("filename", "")
                )
                if fname:
                    final_filepath.append(fname)

        opts["logger"]         = _Logger()
        opts["progress_hooks"] = [_hook]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)
                # fix #2: also grab the final path from extract_info return value
                if info:
                    fp = info.get("filepath") or info.get("_filename", "")
                    if fp:
                        final_filepath.append(fp)
        except Exception as exc:
            detail = "\n".join(log_lines[-10:]) if log_lines else ""
            raise RuntimeError(f"yt-dlp download failed: {exc}\n\nLog:\n{detail}") from exc

        self.last_warnings = [l for l in log_lines if "warn" in l.lower()]
        return self._resolve_output(video_id, mode, ff_path is not None, final_filepath)

    # ------------------------------------------------------------------ #
    #  Format selection — H.264 preferred everywhere                      #
    # ------------------------------------------------------------------ #

    def _build_opts(self, mode: DownloadMode, ff_path: str | None) -> dict[str, Any]:
        base: dict[str, Any] = {
            "quiet":       True,
            "no_warnings": False,
            "noplaylist":  True,
        }

        if ff_path:
            base["ffmpeg_location"] = str(Path(ff_path).parent)

        if mode == "audio":
            if ff_path:
                base["format"] = "bestaudio/best"
                base["postprocessors"] = [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": "192",
                }]
            else:
                base["format"] = "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio"

        elif mode == "video_720":
            if ff_path:
                base["format"] = (
                    "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=720][vcodec^=avc1]+bestaudio"
                    "/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=720]+bestaudio"
                    "/best[height<=720][ext=mp4]"
                    "/best[height<=720]"
                    "/best"
                )
                base["merge_output_format"] = "mp4"
            else:
                base["format"] = "best[height<=720][ext=mp4]/best[height<=720]/best"

        elif mode == "video_1080":
            if ff_path:
                base["format"] = (
                    "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=1080][vcodec^=avc1]+bestaudio"
                    "/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo[height<=1080]+bestaudio"
                    "/best[height<=1080][ext=mp4]"
                    "/best[height<=1080]"
                    "/best"
                )
                base["merge_output_format"] = "mp4"
            else:
                base["format"] = "best[height<=1080][ext=mp4]/best[height<=720][ext=mp4]/best"

        else:  # video_best
            if ff_path:
                base["format"] = (
                    "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]"
                    "/bestvideo[vcodec^=avc1]+bestaudio"
                    "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                    "/bestvideo+bestaudio"
                    "/best[ext=mp4]"
                    "/best"
                )
                base["merge_output_format"] = "mp4"
            else:
                base["format"] = "best[ext=mp4]/best"

        return base

    # ------------------------------------------------------------------ #
    #  Output resolution + audio validation                               #
    # ------------------------------------------------------------------ #

    def _resolve_output(
        self,
        video_id: str,
        mode: DownloadMode,
        had_ff: bool,
        final_filepath: list[str],
    ) -> Path:
        # fix #2: walk candidates in reverse (latest hook event last) and
        # accept only paths that actually exist on disk right now.
        for fname in reversed(final_filepath):
            p = Path(fname)

            # For audio+ffmpeg the hook fires on the pre-conversion file;
            # the real output is the .mp3 sibling.
            if mode == "audio" and had_ff:
                mp3 = p.with_suffix(".mp3")
                if mp3.exists():
                    return mp3

            # Accept the path only if it physically exists (not the deleted intermediate)
            if p.exists():
                self._assert_has_audio(p, mode)
                return p

        # Fallback: scan downloads dir for newest file matching the video ID
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
            "Download appeared to succeed but output file not found.\n"
            f"Check downloads/ for video ID: {video_id}"
        )

    def _assert_has_audio(self, path: Path, mode: DownloadMode) -> None:
        if mode == "audio":
            return
        ff_path = _ffmpeg_path()
        if not ff_path:
            return

        ffprobe_dir = Path(ff_path).parent
        ffprobe = str(ffprobe_dir / "ffprobe.exe")
        if not Path(ffprobe).exists():
            ffprobe = str(ffprobe_dir / "ffprobe")
        if not Path(ffprobe).exists():
            ffprobe = "ffprobe"

        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "a",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=15
            )
            if "audio" not in result.stdout:
                path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Downloaded file had NO audio stream and was deleted.\n"
                    f"File: {path.name}\n\n"
                    f"Fix: update yt-dlp: py -3.11 -m pip install -U yt-dlp"
                )
        except RuntimeError:
            raise
        except Exception:
            pass
