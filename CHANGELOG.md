# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

---

## [v0.8.0] — 2026-06-20

### Added
- **Inline Library search bar** — a live text filter at the top of the Library page matches videos by title or channel name instantly, without navigating to the Search page. Composes with status filter, channel filter, and tag filter simultaneously.
- **Channel multiselect filter** — a new channel dropdown in the Library filter row lets users narrow the grid to one or more specific channels. Built dynamically from all stored `video.channel` values.
- **Tag chips on video cards** — each card in the Library, Dashboard, and Search results now renders up to 3 tag pills (`🏷️ python`, `+2 more`) below the channel/duration line, making tags visible at a glance without opening the detail page.
- **Sort by Date Added** — the Library sort dropdown now includes "Date Added ↓" and "Date Added ↑" options, reading `video.created_at` (already stored on the model since v0.3.0).
- **Clickable timestamps in Transcript tab** — a view-mode toggle (`🔗 Clickable timestamps` / `📋 Raw text`) appears in the Transcript tab. In linked mode, every `MM:SS` and `H:MM:SS` pattern in the transcript is converted to a YouTube deep-link (`?t=Ns`) that opens the exact moment in a new tab. A `_linkify_timestamps` helper (regex-based, zero extra dependencies) handles the conversion.
- **Tag filtering in Library** — multiselect chip row between status filter and video grid; AND logic requires a video to match all selected tags; count caption and empty-state message update to reflect active tag filters. *(Shipped as part of this release batch.)*

### Changed
- `_render_detail_page` — tag display in the video header upgraded from plain `st.caption` text to styled HTML badge chips for visual consistency with card chips.
- `_render_transcript_tab` extracted into its own function for clarity; Transcript tab now routes through this helper.
- Library filter row expanded from 2 columns (status + sort) to 3 columns (status + channel + sort) to accommodate the new channel filter without crowding.
- Library count caption enriched to show active search query, channels, and tags alongside the video count.
- Library empty-state message now lists all active filters so users know exactly why no results appear.

---

## [v0.7.2] — 2026-06-20

### Fixed
- **`local_path` type** — changed `str = ""` to `str | None = None` on `Video` model; resolves two Pylance `reportAttributeAccessIssue` errors in `streamlit_app.py` (lines 278, 309). Empty-string sentinel from existing `videos.json` files is normalised to `None` in `__post_init__` for backwards compatibility.
- **Phantom `local_path` after download failure** — `_render_download_tab` now clears `video.local_path = None` and persists to storage in two places:
  - On every render, if `local_path` is set but the file no longer exists on disk (externally deleted)
  - Immediately inside the `RuntimeError` handler when `downloader.download()` fails, so no stale pointer remains in `videos.json`

### Added
- **Export Study Guide (.md)** — new `_export_study_guide(video)` helper composes title, channel, URL, tags, summary paragraph, key takeaways, auto-notes, and manual notes into a portable Markdown file. A `📥 Export Study Guide (.md)` download button appears in the Notes tab whenever any content field is populated.
- **YouTube API tag ingestion** — `video.tags` (already stored on the model) is now displayed in two places: the video detail page header (`🏷️ tag1 · tag2`, first 8 tags) and the Add Video preview card (first 6 tags). Tags are populated automatically from `item["snippet"]["tags"]` in the YouTube Data API response; falls back to `[]` gracefully when absent or when the API key is unused.

---

## [v0.7.1] — 2026-06-20

### Fixed
- **`importlib.metadata`** used to read yt-dlp version — resolves Pylance `reportAttributeAccessIssue` on `_ytdlp.version.__version__`
- **Streamlit API** — replaced all 14 deprecated `use_container_width=True` calls with `width='stretch'` (removed after 2025-12-31)
- **Downloader — 4 bugs patched**
  - `_ffprobe_path()` now uses `shutil.which` with parent-dir priority (no silent PATH fallback)
  - Progress hook filters by file extension so intermediate `.f398.mp4` / `.f140.m4a` paths are never stored as `final_filepath`
  - Switched `quiet=False` + `verbose=False` so JS-challenge warnings are captured in `last_warnings` instead of being swallowed
  - Added `extractor_args youtube.player_client=['web','android']` to bypass Deno/EJS challenge solver on most videos
- **11-bug omnibus patch**
  - `st.image` / `st.button` API consistency across all call sites
  - `storage=` passed to `fetcher.fetch_video()` to skip redundant API calls for already-saved videos
  - `st.stop()` added after `_finish_add_video()` to prevent double-render
  - Download key reset on error so the Start Download button is not stuck
  - "Clear All Data" now wipes videos + all collection refs atomically (no orphans)
  - `search_videos` now searches `summary_bullets` and `auto_notes` fields
  - Downloader surfaces JS challenge warnings via `st.warning` in the UI
  - `ffmpeg_location` passed to transcript yt-dlp opts on Windows
  - `requirements.txt` yt-dlp floor bumped to `>=2024.11.0`
  - Collections detail view Remove button uses `use_container_width=True`
- **15-bug audit resolve**
  - Storage: atomic writes via `os.replace()` + `threading.Lock`
  - Downloader: `_resolve_output` no longer returns deleted post-processed file
  - Collection: full UUID4 instead of 8-char truncation
  - Streamlit: guard `st.stop()` usage, stream-safe download info
  - YouTubeFetcher: handle live/premiere zero-duration + quota 403 message
  - TranscriptExtractor: deduplicate `lang_codes`, fix fallback gap
  - Summarizer: `_parse_response` paragraph contamination guard
  - Storage: batch collection writes in `delete_video` (single read/write)
  - Core: log model fallback events
  - YouTubeFetcher: check storage cache before API call
  - TranscriptExtractor: `ignore_cleanup_errors` on `TemporaryDirectory`
  - Storage: log corrupt records instead of silently dropping
  - Streamlit: warn if yt-dlp update Python env mismatch
  - Models: typed `list[str]` fields on `Video`
- **View-details lag** — route to detail page before rendering card grid on Library / Search / Collections (eliminates freeze)
- **0% progress bar** — show grey bar for saved/unwatched videos in compact mode instead of nothing
- **Stale selectbox** — clear `session_state` before render so `index` is respected after status auto-transition
- **Detail page status overwrite** — re-fetch video from storage in `_render_detail_page` to prevent selectbox overwriting progress-saved status on rerun
- **SyntaxError** — curly quotes in f-strings on lines 717 + 738 replaced with straight quotes

---

## [v0.7.0] — 2026-06-19

### Added
- **Collections / Playlists**
  - New `models/collection.py` — `Collection` dataclass with `id`, `name`, `emoji`, `description`, `video_ids`, timestamps
  - `Collection` now exported from `models/__init__.py`
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
