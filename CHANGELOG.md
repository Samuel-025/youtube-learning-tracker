# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

---

## [v0.7.0] — 2026-06-19

### Added
- **Collections / Playlists**
  - New `models/collection.py` — `Collection` dataclass with `id`, `name`, `emoji`, `description`, `video_ids`, timestamps
  - Collections stored in `data/collections.json` (separate from `videos.json`, gitignored)
  - **`core/storage.py`** extended with full collections CRUD:
    - `save_collection`, `get_collection`, `get_all_collections`, `update_collection`, `delete_collection`
    - `add_video_to_collection`, `remove_video_from_collection`
    - `get_videos_in_collection`, `get_collections_for_video`
    - `delete_video` now auto-removes the video from all collections
  - **📁 Collections page** (new sidebar entry between Library and Search)
    - Grid of collection cards showing name, emoji, video count, completed count, and per-collection progress bar
    - ➕ Create form: name + emoji picker (15 options) + optional description
    - 📂 Open a collection to see its videos in a 3-column grid
    - ✏️ Edit name / emoji / description inline
    - ➕ Add videos panel inside each collection (searchable, shows up to 20 at a time)
    - ➖ Remove video from collection without deleting it from library
    - 🗑️ Delete collection with confirm guard (videos are kept)
  - **📁 Collections tab** on every video detail page (7th tab)
    - Checkbox list of all collections — toggle to add/remove this video instantly
  - **Collections badge** in video detail header showing which collections the video belongs to
  - **Sidebar** shows collection count below the status metrics
  - **Settings page** shows collection count in configuration panel

---

## [v0.6.0] — 2026-06-19

### Added
- Watch Progress Tracking — slider, progress bar, card indicators, dashboard panel
- `watch_progress_sec`, `duration_sec` fields + `progress_pct` property on Video model
- Library sort by Progress ↑ / ↓

---

## [v0.5.2] — 2026-06-19

### Added
- One-click yt-dlp updater in Settings

---

## [v0.5.1] — 2026-06-19

### Fixed
- H.264-first downloads, FFmpeg detection, audio validation, warnings surfaced

---

## [v0.5.0] — 2026-06-19

### Added
- Audio/Video Downloader (MP3 / MP4 via yt-dlp)

---

## [v0.4.0] — 2026-06-18

### Added
- Full Streamlit web app, transcript extractor, AI summarizer, notes, Q&A

---

## [v0.3.0] — 2026-06-17

### Added
- Video model, Storage, YouTubeFetcher, WatchStatus

---

## [v0.2.0] — 2026-06-16

### Added
- Project scaffold, run scripts, security hardening

---

## [v0.1.0] — 2026-06-15

### Added
- Initial project, CLI skeleton
