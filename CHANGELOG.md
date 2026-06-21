# Changelog

All notable changes to YouTube Learning Tracker are documented here.

---

## [Unreleased]

---

## [v0.10.0] — 2026-06-21

### Added
- **E1 — JSON Export** — Settings page gains an "⬇️ Export JSON" button that snapshots the entire library (all videos, notes, progress, tags) and all collections into a single timestamped `.json` file available as a browser download. Thread-safe single-lock snapshot.
- **E2 — JSON Import** — Settings page gains a file uploader that reads a previously exported `.json` file with two modes:
  - **Merge** — adds only IDs not already present; safe top-up from another machine.
  - **Overwrite** — full restore; replaces the entire library with the imported data.
  - Schema version check (`schema_version: 1`) warns on unknown formats before proceeding.
- **E3 — CSV Export** — Settings page "⬇️ Export CSV" button produces a spreadsheet-friendly file with 16 columns: `video_id`, `title`, `channel`, `url`, `status`, `progress_pct`, `watch_progress_sec`, `duration_sec`, `duration`, `tags`, `published_at`, `created_at`, `updated_at`, `manual_notes`, `summary_paragraph`, `thumbnail_url`. Tags joined with ` | ` for single-cell compatibility.
- **E4 — Markdown Library Export** — Settings page "⬇️ Export Markdown" button renders the full library as a human-readable `.md` file grouped by watch status, including per-video channel, duration, progress, tags, notes, and summary. Collections section lists member video titles.
- **E5 — Per-video JSON Export** — "⬇️ Export this video" download button on each video's detail page exports that video's full record (metadata, transcript, summary, notes, progress, tags) as a standalone `.json` file. Output is compatible with E2 import (wrap in the standard envelope).
- **`core/exporters.py`** — new pure-function module (`export_csv`, `export_markdown_library`, `export_video_json`) with no Streamlit dependency; callable from CLI and tests.
- **`Storage.export_json()`** — thread-safe snapshot returning `{schema_version, exported_at, videos, collections}`.
- **`Storage.import_json(payload, merge)`** — atomic import under `_STORAGE_LOCK`; returns `(videos_imported, collections_imported)`.

---

## [v0.9.0] — 2026-06-20

### Added
- **Progress Dashboard — Insight Charts** — three interactive Plotly charts appear in the Dashboard below the overall progress bar, under a new `📈 Insights` subheader:
  - **🍩 Library by Status (donut)** — proportion of videos in each watch status with colour-coded segments and percent labels.
  - **⏱ Watch Time by Status (horizontal bar)** — total content hours broken out by status; only statuses with duration data are shown.
  - **📊 Progress Distribution (stacked bar)** — video counts bucketed into four progress bands (0–25%, 25–50%, 50–75%, 75–100%), stacked by status so you can see where videos are concentrated.
- **Weekly Watch Goal widget** — displayed in the Dashboard between the overall progress bar and Insights; computes ISO-week watched hours against a user-defined goal and renders a progress bar + remaining-hours metric.
- **Settings — Weekly Watch Goal setter** — numeric input in Settings lets users define their weekly hour target; persisted via `SettingsStore`.
- **`SettingsStore`** (`core/settings_store.py`) — lightweight JSON persistence layer for app-level settings (e.g., weekly goal); no schema migrations required.
- **`plotly>=5.0.0`** added to `requirements.txt`; charts degrade gracefully with an install hint if the package is absent.
- **Full test suite** (`tests/`) — `conftest.py` + 5 test modules covering storage, model, transcript linkifier, collections, and bug regressions (B1–B14).

### Fixed
- `_TIMESTAMP_RE` moved from module-level constant into `_linkify_timestamps` as a local compiled pattern so AST-exec test harness passes without a `NameError`.
- `make_video` / `make_collection` helpers extracted to `tests/helpers.py` to fix `ModuleNotFoundError` on conftest import.

---

## [v0.8.0] — 2026-06-20

### Added
- **Inline Library search bar** — a live text filter at the top of the Library page matches videos by title or channel name instantly, without navigating to the Search page. Composes with status filter, channel filter, and tag filter simultaneously.
- **Channel multiselect filter** — a new channel dropdown in the Library filter row lets users narrow the grid to one or more specific channels. Built dynamically from all stored `video.channel` values.
- **Tag chips on video cards** — each card in the Library, Dashboard, and Search results now renders up to 3 tag pills (`🏷️ python`, `+2 more`) below the channel/duration line, making tags visible at a glance without opening the detail page.
- **Sort by Date Added** — the Library sort dropdown now includes "Date Added ↓" and "Date Added ↑" options, reading `video.created_at` (already stored on the model since v0.3.0).
- **Clickable timestamps in Transcript tab** — a view-mode toggle (`🔗 Clickable timestamps` / `📋 Raw text`) appears in the Transcript tab. In linked mode, every `MM:SS` and `H:MM:SS` pattern in the transcript is converted to a YouTube deep-link (`?t=Ns`) that opens the exact moment in a new tab.
- **Tag filtering in Library** — multiselect chip row between status filter and video grid; AND logic requires a video to match all selected tags; count caption and empty-state message update to reflect active tag filters.

### Changed
- `_render_detail_page` — tag display in the video header upgraded from plain `st.caption` text to styled HTML badge chips for visual consistency with card chips.
- `_render_transcript_tab` extracted into its own function for clarity.
- Library filter row expanded from 2 columns to 3 columns (status + channel + sort).
- Library count caption enriched to show active search query, channels, and tags alongside the video count.
- Library empty-state message now lists all active filters so users know exactly why no results appear.

### Bug Fixes — Audit Verification (B1–B14)

All 14 bugs from the post-v0.7.2 audit have been confirmed fixed and verified directly in source code.

| Bug | Severity | Description | Fix | Verified in |
|-----|----------|-------------|-----|-------------|
| **B1** | Medium | Channel & tag pools built from all videos, ignoring active status filter | `all_videos` built once from status-filtered list | `app/streamlit_app.py` |
| **B2** | Medium | `_linkify_timestamps` emitted Markdown links inside raw HTML div | Switched to real `<a href="...">` HTML anchors | `app/streamlit_app.py` |
| **B3** | High | `get_video` parsed objects outside the lock (TOCTOU race) | Snapshot raw dict inside lock; parse outside | `core/storage.py` |
| **B4** | Medium | `Video.from_dict` did not recalculate `duration_sec` when stored value was 0 | `from_dict` recalculates via `_parse_duration_sec` | `models/video.py` |
| **B5** | Medium | `_apply_progress` never downgraded COMPLETED status on scrub-back | Added `elif` branch: COMPLETED → WATCHING | `app/streamlit_app.py` |
| **B6** | Medium | Tag pool built from raw storage instead of status-filtered list | Tag pool derived from `all_videos` | `app/streamlit_app.py` |
| **B8** | Medium | `get_videos_in_collection` made N+1 individual `get_video()` calls | Single `get_all_videos()` call + dict lookup | `core/storage.py` |
| **B9** | Medium | Library page called `get_all_videos()` once per filter stage | Single `all_videos` read; all filters operate on cached list | `app/streamlit_app.py` |
| **B10** | High | Transcript text injected into `unsafe_allow_html` without escaping (XSS) | Content routed through `_linkify_timestamps` with HTML escaping | `app/streamlit_app.py` |
| **B11** | Low | `Video.from_dict` used hardcoded `known` field set | Introspects live dataclass definition via `dataclasses.fields` | `models/video.py` |
| **B12** | Low | yt-dlp updater called bare `pip` instead of `sys.executable -m pip` | Uses `[sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]` | `app/streamlit_app.py` |
| **B13** | Low | `from datetime import datetime` imported inside functions | Moved to module top | `core/storage.py` |
| **B14** | Low | `counts` assigned after sidebar metrics widgets that reference it | `counts` assigned in sidebar block before page routing | `app/streamlit_app.py` |

---

## [v0.7.2] — 2026-06-20

### Fixed
- **`local_path` type** — changed `str = ""` to `str | None = None` on `Video` model.
- **Phantom `local_path` after download failure** — `_render_download_tab` now clears `video.local_path = None` on error and on missing-file detection.

### Added
- **Export Study Guide (.md)** — `_export_study_guide(video)` helper; download button in Notes tab.
- **YouTube API tag ingestion** — `video.tags` populated from `item["snippet"]["tags"]`; displayed in detail header and Add Video preview.

---

## [v0.7.1] — 2026-06-20

### Fixed
- `importlib.metadata` used to read yt-dlp version.
- All 14 deprecated `use_container_width=True` calls replaced with `width='stretch'`.
- Downloader: `_ffprobe_path()`, progress hook, `quiet`/`verbose` flags, extractor args.
- 11-bug omnibus patch: API consistency, storage guard, `st.stop()`, download key reset, atomic clear, search fields, warnings, ffmpeg location, requirements floor, collections remove button.
- 15-bug audit resolve: atomic writes, `_resolve_output`, UUID4, stream-safe download, YouTubeFetcher live/quota, TranscriptExtractor dedup, Summarizer parse guard, batch collection writes, log fallback, storage cache, cleanup errors, corrupt log, env mismatch warn, typed list fields.
- View-details lag, 0% progress bar, stale selectbox, detail page status overwrite, SyntaxError curly quotes.

---

## [v0.7.0] — 2026-06-19

### Added
- **Collections / Playlists** — `models/collection.py`, Collections CRUD in `core/storage.py`, 📁 Collections sidebar page, Collections tab on video detail page, collections badge in detail header, sidebar + Settings count.

---

## [v0.6.0] — 2026-06-19

### Added
- Watch Progress Tracking — slider, progress bar, card indicators, dashboard panel.
- `watch_progress_sec`, `duration_sec` fields + `progress_pct` property on Video model.
- Library sort by Progress ↑ / ↓.

---

## [v0.5.2] — 2026-06-19

### Added
- One-click yt-dlp updater in Settings.

---

## [v0.5.1] — 2026-06-19

### Fixed
- H.264-first downloads, FFmpeg detection, audio validation, warnings surfaced.

---

## [v0.5.0] — 2026-06-19

### Added
- Audio/Video Downloader (MP3 / MP4 via yt-dlp).

---

## [v0.4.0] — 2026-06-18

### Added
- Full Streamlit web app, transcript extractor, AI summarizer, notes, Q&A.

---

## [v0.3.0] — 2026-06-17

### Added
- Video model, Storage, YouTubeFetcher, WatchStatus.

---

## [v0.2.0] — 2026-06-16

### Added
- Project scaffold, run scripts, security hardening.

---

## [v0.1.0] — 2026-06-15

### Added
- Initial project, CLI skeleton.
