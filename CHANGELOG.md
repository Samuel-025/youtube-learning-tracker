# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

---

## [v0.5.1] — 2026-06-19

### Fixed
- **Downloader: videos now play correctly in Windows Media Player**
  - Root cause: YouTube serves AV1 video codec by default; Windows Media Player cannot decode AV1
  - Fix: format strings now explicitly prefer **H.264 (`vcodec^=avc1`)** with progressive fallbacks
  - All downloads are now compatible with Windows Media Player, VLC, Edge, Chrome, and all devices
- **FFmpeg location passed directly to yt-dlp** via `ffmpeg_location` option (parent directory of binary)
  - Eliminates PATH lookup ambiguity inside yt-dlp on Windows (WinGet installs FFmpeg to a non-standard location)
- **Audio stream validation** after every video download using `ffprobe`
  - If a file has no audio stream it is deleted immediately and a clear `RuntimeError` is raised
  - Never silently saves a muted file again
- **yt-dlp warnings surfaced** — signature/n-challenge warnings stored in `Downloader.last_warnings`
  - Previously swallowed silently; now visible for debugging
- **FFmpeg status banner** in Download tab
  - Green ✅ with version string when FFmpeg detected
  - Yellow ⚠️ with install instructions when FFmpeg missing
  - Format labels change to reflect no-FFmpeg limitations (M4A instead of MP3, progressive MP4)
- **Settings page** now shows FFmpeg version alongside yt-dlp and youtube-transcript-api status

### Changed
- `core/downloader.py` — complete rewrite of `_build_opts()` with H.264-first format strings and 5-level fallback chain
- `app/streamlit_app.py` — Download tab shows FFmpeg banner; error messages now display full `RuntimeError` detail

---

## [v0.5.0] — 2026-06-19

### Added
- **Audio/Video Downloader** (`core/downloader.py`)
  - Download any saved video as MP3 (192k), MP4 720p, MP4 1080p, or best quality
  - Uses yt-dlp under the hood — same engine used for transcript extraction
  - Files saved to `downloads/` folder (excluded from Git — never uploaded)
  - `local_path` field added to `Video` model to remember downloaded files
- **⬇️ Download tab** on every video detail page
  - Format selector (audio / 720p / 1080p / best)
  - Start Download button with live spinner
  - 📥 Save to computer button streams file directly to browser after download
  - Re-shows previously downloaded file if `local_path` still exists on disk
- **Security hardening**
  - `downloads/` folder added to `.gitignore` with `.gitkeep` placeholder
  - All media extensions blocked globally
  - `requirements.txt` updated with clear FFmpeg installation instructions

### Changed
- `models/video.py` — added `local_path: str = ""` field
- `app/streamlit_app.py` — detail page now has 5 tabs: Summary / Notes / Transcript / Ask / Download
- Settings page now shows yt-dlp version, `downloads/` folder path

### Fixed
- Prevented accidental `pip install ffmpeg` confusion in requirements.txt

---

## [v0.4.0] — 2026-06-18

### Added
- Full Streamlit web app (`app/streamlit_app.py`)
  - Dashboard, Add Video, Library, Search, Settings pages
  - Video detail page with Summary / Notes / Transcript / Ask tabs
  - Watch status selector on every card and detail view
- yt-dlp transcript extractor (`core/transcript_extractor.py`) — no API key needed
- AI Summarizer (`core/summarizer.py`) — Groq / OpenAI / Anthropic / offline
- Notes generator (`core/notes_generator.py`) — auto bullet notes from transcript
- Q&A from transcript using AI (`summarizer.answer_question`)

### Changed
- `Storage` class now supports `filter_by_status`, `search_videos`, `count_by_status`, `get_storage_size`

---

## [v0.3.0] — 2026-06-17

### Added
- `Video` dataclass model with full field schema
- `Storage` class — JSON-based persistence in `data/videos.json`
- `YouTubeFetcher` — metadata fetch via YouTube Data API v3
- `WatchStatus` enum: saved / watching / completed / dropped / rewatch

---

## [v0.2.0] — 2026-06-16

### Added
- Project scaffold: `core/`, `models/`, `app/`, `tests/`, `data/`
- `.env.example` with all supported keys
- `.gitignore` hardened against API keys, user data, virtual envs
- `SECURITY.md` — responsible disclosure policy
- `run.bat` and `run.ps1` launchers

---

## [v0.1.0] — 2026-06-15

### Added
- Initial project creation
- Basic CLI skeleton (`cli.py`)
- `requirements.txt` baseline
