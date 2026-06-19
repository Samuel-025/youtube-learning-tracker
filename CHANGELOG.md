# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

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
  - All media extensions (`.mp3`, `.mp4`, `.mkv`, `.webm`, `.m4a`, `.wav`, etc.) blocked globally
  - `requirements.txt` updated with clear FFmpeg installation instructions

### Changed
- `models/video.py` — added `local_path: str = ""` field (backward-compatible, safe loader ignores it on old data)
- `app/streamlit_app.py` — detail page now has 5 tabs: Summary / Notes / Transcript / Ask / Download
- Settings page now shows yt-dlp version, `downloads/` folder path

### Fixed
- Prevented accidental `pip install ffmpeg` confusion — requirements.txt now documents the correct system binary install method

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
