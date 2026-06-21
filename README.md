# 📺 YouTube Learning Tracker

> **v0.11.2** — Save, organise, summarise, track, download, export, rate, and schedule YouTube videos from a clean Streamlit web app running entirely on your local machine.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 Save videos | Paste any YouTube URL — fetches metadata, thumbnail, tags & transcript automatically |
| 📚 Library | Browse saved videos; filter by status, channel, and tags; sort by title / date added / progress |
| 🔎 Inline Library search | Live text filter by title or channel — composes with all other filters simultaneously |
| 🏷️ Tag filtering | Multiselect tag chips in the Library — AND logic across all selected tags |
| 📁 Collections | Group videos into named, emoji-tagged playlists with per-collection progress bars |
| ⏱️ Watch Progress | Slider + quick-set buttons to track how far through each video you are |
| 📊 Dashboard Insight Charts | Three interactive Plotly charts — status donut, watch-time bar, progress distribution |
| 🎯 Weekly Watch Goal | ISO-week progress bar on the Dashboard; set your hourly goal in Settings |
| ⭐ Star Rating | Rate any video 1–5 stars (0 = unrated); shown on cards, detail view, and Markdown export |
| 📅 Watch Reminders | Set an optional due date per video; dashboard badges flag overdue / due-soon / this-week |
| 🤖 AI Summary | Bullet-point summary + paragraph overview generated from the transcript |
| 🗒️ Notes | Auto-generated notes + your own manual notes per video |
| 📥 Export Study Guide | Download a portable `.md` file with title, tags, summary, takeaways, and notes |
| 💬 Q&A | Ask any question about a video — answered from its transcript |
| 🔗 Clickable timestamps | Transcript tab toggle converts every `MM:SS` to a YouTube deep-link that opens the exact moment |
| ⬇️ Download | Save as **MP3** (audio) or **MP4** (720p / 1080p / best) using yt-dlp + FFmpeg |
| 🔍 Search | Full-text search across titles, channels, notes, summaries, and auto-notes |
| 📤 Export Library | Export full library as **JSON** (backup/restore), **CSV** (spreadsheet), or **Markdown** (readable report) |
| 📥 Import JSON | Restore from a backup — **Merge** (add missing) or **Overwrite** (full replace) modes |
| 📄 Per-video JSON | Export any single video's full record as a standalone `.json` file |
| ⚙️ Settings | yt-dlp updater, weekly goal setter, export / import panel, and app-level preferences |

---

## 🚀 Quick Start

### 1. Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://python.org) |
| FFmpeg | 6+ | `winget install --id Gyan.FFmpeg -e` (Windows) |
| Git | any | [git-scm.com](https://git-scm.com) |

> **After installing FFmpeg, close and reopen your terminal** so the PATH updates.

### 2. Clone & Install

```powershell
git clone https://github.com/Samuel-025/youtube-learning-tracker.git
cd youtube-learning-tracker
py -3.11 -m pip install -r requirements.txt
```

### 3. Configure API Keys

```powershell
copy .env.example .env
# Edit .env with your keys
```

| Key | Required | Get it |
|---|---|---|
| `YOUTUBE_API_KEY` | ✅ Yes | [console.cloud.google.com](https://console.cloud.google.com) — free 10k units/day |
| `GROQ_API_KEY` | Recommended | [console.groq.com](https://console.groq.com) — free, no credit card |
| `OPENAI_API_KEY` | Optional | [platform.openai.com](https://platform.openai.com) |
| `AI_PROVIDER` | Optional | `groq` (default) / `openai` / `none` |

### 4. Run

```powershell
.\run.ps1
# or
py -3.11 -m streamlit run app/streamlit_app.py
```

Open **http://localhost:8501** in your browser.

### Updating an existing install

```powershell
git pull origin main
py -3.11 -m pip install -r requirements.txt
# Also update yt-dlp (YouTube changes its protection frequently):
py -3.11 -m pip install -U yt-dlp
```

---

## 📊 Dashboard

The Dashboard gives you a full picture of your library at a glance.

- **Counts panel** — total videos broken down by watch status (Unwatched / Watching / Completed)
- **Overall progress bar** — percentage of total library duration watched
- **🎯 Weekly Watch Goal** — ISO-week progress bar showing hours watched vs. your goal; set your target in ⚙️ Settings
- **📈 Insights** — three interactive Plotly charts:
  - **🍩 Library by Status (donut)** — proportion of videos in each status with percent labels
  - **⏱ Watch Time by Status (horizontal bar)** — total content hours per status
  - **📊 Progress Distribution (stacked bar)** — video counts in four progress bands (0–25%, 25–50%, 50–75%, 75–100%), stacked by status
- **📅 Due-date badges** — overdue (🔴), due today / soon (🟡), and this-week (🟢) reminders surfaced inline
- **Recently Added** — quick-access cards for the latest saved videos; **View** button navigates directly to the video's detail page in the Library

> Charts require `plotly>=5.0.0` (included in `requirements.txt`). A friendly install hint appears if the package is missing.

---

## 🎯 Weekly Watch Goal

- Go to **⚙️ Settings → Weekly Watch Goal** and enter your target hours per week
- The Dashboard shows a progress bar for the current ISO week with watched hours, remaining hours, and your goal
- When the goal is met you get a 🏆 success banner
- If no goal is set, the widget shows a soft nudge with your raw watched hours for the week
- Goal is persisted locally in `data/settings.json` via `SettingsStore`

---

## ⭐ Star Rating

- Rate any video **1–5 stars** from its detail page (0 = unrated)
- Rating is shown as ⭐ stars on Library cards, in the video detail header, and in Markdown library exports
- Exported as a numeric `rating` column in CSV
- Stored on the `Video` model; clamped to 0–5 automatically

---

## 📅 Watch Reminders / Due Dates

- Set an optional **due date** (YYYY-MM-DD) on any video's detail page
- The `core/due_date.py` module classifies urgency automatically:
  - 🔴 **Overdue** — past due date
  - 🟡 **Due today** / **Due soon** — within 2 days
  - 🟢 **This week** — 3–7 days away
- Badges appear on the Dashboard and video cards
- Due date is exported in both CSV and Markdown library exports

---

## 📤 Export & Import

All export / import controls live in **⚙️ Settings**.

| Action | Format | Notes |
|---|---|---|
| ⬇️ Export JSON | `.json` | Full backup — all videos, notes, progress, tags, collections. Timestamped filename. |
| ⬆️ Import JSON (Merge) | `.json` | Adds only IDs not already present — safe top-up from another machine. |
| ⬆️ Import JSON (Overwrite) | `.json` | Full restore — replaces the entire library. Schema version check runs first. |
| ⬇️ Export CSV | `.csv` | 18-column spreadsheet: id, title, channel, url, status, progress, duration, tags, dates, notes, summary, thumbnail, rating, due_date. Tags joined with ` \| `. |
| ⬇️ Export Markdown | `.md` | Human-readable report grouped by watch status; includes channel, duration, progress, tags, notes, summary, star rating, and due date per video. Collections section lists member titles. |
| ⬇️ Export this video | `.json` | Per-video record from the detail page — metadata, transcript, summary, notes, progress, tags. Compatible with JSON Import. |

> Export functions live in `core/exporters.py` — pure Python, no Streamlit dependency; fully callable from CLI and tests.

---

## 📁 Collections

Collections let you group any saved videos into named playlists.

- Create a collection with a name, emoji, and optional description
- Open a collection to see its videos in a card grid
- Add / remove videos from the **Collections** tab on any video detail page
- Each collection card shows video count, completed count, and a **progress bar**
- Deleting a collection never deletes the videos — they stay in your library
- Stored in `data/collections.json` (local only, gitignored)

---

## ⏱️ Watch Progress

- Every video detail page has a **Progress** tab with a slider and quick-set buttons (0% / 25% / 50% / 100%)
- Progress bars appear on every video card in the Library and Collections views
- Setting progress to 100% automatically marks the video as **Completed**
- The Dashboard shows an overall progress bar across your whole library
- Library can be sorted by **Progress ↑** or **Progress ↓**

---

## 🏷️ Tags

- Tags are ingested automatically from the YouTube Data API (`snippet.tags`) when you add a video
- Up to 3 tag chips appear on every video card in the Library, Dashboard, and Search results
- Use the **Filter by tag** multiselect in the Library to narrow results — AND logic across all selected tags
- First 8 tags are shown in the video detail header

---

## 🔗 Clickable Timestamps

- Open any video's **Transcript** tab and toggle to **🔗 Clickable timestamps** mode
- Every `MM:SS` or `H:MM:SS` pattern becomes a clickable YouTube deep-link (`?t=Ns`) that opens the exact moment in a new tab
- Switch back to **📋 Raw text** mode for plain copy-paste

---

## ⬇️ Download Feature

The Download tab on every video detail page lets you save videos locally.

### Format Options

| Format | Codec | Plays in |
|---|---|---|
| 🎧 Audio only | MP3 192k | All players |
| 📹 Video 720p | H.264 + AAC → MP4 | All players incl. Windows Media Player |
| 📹 Video 1080p | H.264 + AAC → MP4 | All players incl. Windows Media Player |
| 📹 Video Best | H.264 + AAC → MP4 | All players incl. Windows Media Player |

> Downloads use **H.264** specifically to ensure compatibility with Windows Media Player, which cannot decode AV1 (YouTube's newer default codec).

### FFmpeg Status

The Download tab shows a banner:
- ✅ **Green** — FFmpeg detected, all formats available, MP3 conversion enabled
- ⚠️ **Yellow** — FFmpeg not found; audio saves as `.m4a`, video saves as progressive MP4 (max 720p)

### Install FFmpeg (Windows)

```powershell
winget install --id Gyan.FFmpeg -e
# Close and reopen terminal after install
ffmpeg -version  # verify
```

---

## 🗂️ Project Structure

```
youtube-learning-tracker/
├── app/
│   └── streamlit_app.py        # Main web UI (all pages)
├── core/
│   ├── __init__.py             # Groq model cascade helper
│   ├── downloader.py           # yt-dlp wrapper — H.264 MP4 / MP3
│   ├── due_date.py             # Due-date helpers (days_until, due_status, due_badge)
│   ├── exporters.py            # Pure export functions: CSV, Markdown, per-video JSON
│   ├── notes_generator.py      # Auto bullet notes
│   ├── settings_store.py       # Lightweight JSON settings persistence
│   ├── storage.py              # JSON persistence (videos + collections) + export_json / import_json
│   ├── summarizer.py           # AI summary + Q&A (Groq / OpenAI)
│   ├── transcript_extractor.py # yt-dlp subtitle extraction
│   └── youtube_fetcher.py      # YouTube Data API v3 metadata
├── models/
│   ├── video.py                # Video dataclass + WatchStatus enum (rating, due_date fields)
│   └── collection.py           # Collection dataclass
├── data/
│   ├── videos.json             # Your saved videos (gitignored)
│   ├── collections.json        # Your collections (gitignored)
│   └── settings.json           # App-level settings — weekly goal etc. (gitignored)
├── downloads/                  # Downloaded media files (gitignored)
├── tests/
│   ├── conftest.py
│   ├── helpers.py
│   ├── test_collection.py
│   ├── test_due_date.py
│   ├── test_exporters.py
│   ├── test_linkify.py
│   ├── test_search.py
│   ├── test_settings_store.py
│   ├── test_storage.py
│   └── test_video_model.py
├── .env.example
├── CHANGELOG.md
├── requirements.txt
├── run.bat
└── run.ps1
```

---

## 🧪 Running Tests

```powershell
py -3.11 -m pytest tests/ -v
```

The test suite (10 modules) covers storage, the Video model, transcript timestamp linkifier (incl. XSS escape), collections, full-text search, CSV/Markdown/JSON exporters, `SettingsStore`, due-date classification helpers, and bug regressions (B1–B14). Shared fixtures live in `conftest.py` and `helpers.py`.

---

## 🔧 Troubleshooting

### yt-dlp: "Signature solving failed" / muted download / missing formats

YouTube regularly updates its JS challenge. Keeping yt-dlp current fixes this.

**Easiest fix — use the in-app updater:**
Go to **⚙️ Settings → Update yt-dlp** and click the button. Restart Streamlit after.

**Or run manually:**
```powershell
py -3.11 -m pip install -U yt-dlp
```

> The downloader automatically uses `player_client=['web','android']` to bypass the Deno/EJS challenge solver requirement on most videos. If warnings still appear, updating yt-dlp resolves them.

### Video plays without sound / won't play in Windows Media Player

YouTube serves AV1 by default — Windows Media Player cannot decode AV1. The downloader forces H.264. If you have an old download:
1. Delete the file from `downloads/`
2. Re-download via the app

### "FFmpeg not found"

```powershell
winget install --id Gyan.FFmpeg -e
# Close terminal, reopen, then:
ffmpeg -version
```

### "yt-dlp not installed"

```powershell
py -3.11 -m pip install yt-dlp
```

### Transcript not found

Some videos disable transcripts. Use the **Paste** or **Upload** option in the Transcript tab on the video detail page.

### AI summary fails

Check your `.env` — ensure `GROQ_API_KEY` or `OPENAI_API_KEY` is set and `AI_PROVIDER` matches.

### Insight charts not showing

```powershell
py -3.11 -m pip install plotly
```

---

## 🛡️ Privacy & Security

- All data is stored **locally** in `data/` — never uploaded anywhere
- Downloaded media is stored in `downloads/` — gitignored, never committed
- API keys live in `.env` — gitignored, never committed
- See [SECURITY.md](SECURITY.md) for the responsible disclosure policy

---

## 📄 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## 📄 License

MIT — see [LICENSE](LICENSE)
