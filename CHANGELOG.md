# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

---

## [v0.6.0] — 2026-06-19

### Added
- **Watch Progress Tracking**
  - `watch_progress_sec` and `duration_sec` fields added to `Video` model (backward-compatible)
  - `_parse_duration_sec()` helper parses `MM:SS`, `H:MM:SS`, `PT1H23M45S` (ISO 8601), and bare seconds
  - `progress_pct` computed property returns 0.0–100.0 float
  - **⏱ Progress tab** on every video detail page
    - Slider (draggable, ~0.5% step granularity) showing current position in H:MM:SS format
    - Quick-set buttons: 0% · 25% · 50% · 100%
    - “Save Progress” button persists to `videos.json`
    - Auto-promotes status to `watching` when progress > 0 and status was `saved`
    - Auto-promotes status to `completed` when slider reaches 100% or quick-set 100% clicked
  - **Progress bar in video header** (detail page) shows `H:MM:SS / total` + percentage
  - **Mini progress bar on library cards** — only shown when progress > 0
  - **Library sort options** extended: `Progress ↑` (least watched first) and `Progress ↓` (most watched first)
  - **Dashboard overall progress panel** — total hours watched vs total hours saved, with a library-wide progress bar

---

## [v0.5.2] — 2026-06-19

### Added
- **One-click yt-dlp updater** in Settings page
  - "⬆️ Update yt-dlp now" button runs `pip install --upgrade yt-dlp` in-process
  - Shows current installed version, pip output summary, full log expander, clear button
  - Reminder to restart Streamlit after upgrading

---

## [v0.5.1] — 2026-06-19

### Fixed
- Downloader: H.264-first format strings, FFmpeg location explicit, audio validation, warnings surfaced
- FFmpeg status banner in Download tab
- Settings page shows FFmpeg version

---

## [v0.5.0] — 2026-06-19

### Added
- Audio/Video Downloader (`core/downloader.py`) — MP3 / MP4 720p / 1080p / best via yt-dlp
- ⬇️ Download tab on every video detail page
- `local_path` field on Video model

---

## [v0.4.0] — 2026-06-18

### Added
- Full Streamlit web app, yt-dlp transcript extractor, AI summarizer, notes generator, Q&A

---

## [v0.3.0] — 2026-06-17

### Added
- Video dataclass, Storage (JSON), YouTubeFetcher, WatchStatus enum

---

## [v0.2.0] — 2026-06-16

### Added
- Project scaffold, `.env.example`, `.gitignore`, `SECURITY.md`, run scripts

---

## [v0.1.0] — 2026-06-15

### Added
- Initial project creation, CLI skeleton, `requirements.txt`
