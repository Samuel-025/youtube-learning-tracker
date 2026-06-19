# 📺 YouTube Learning Tracker

> **v0.7.0** — Save, organise, summarise, track, and download YouTube videos from a clean Streamlit web app running entirely on your local machine.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 Save videos | Paste any YouTube URL — fetches metadata, thumbnail & transcript automatically |
| 📚 Library | Browse saved videos, filter by status, sort by title / date / progress |
| 📁 Collections | Group videos into named, emoji-tagged playlists with per-collection progress bars |
| ⏱️ Watch Progress | Slider + quick-set buttons to track how far through each video you are |
| 🤖 AI Summary | Bullet-point summary + paragraph overview generated from the transcript |
| 🗒️ Notes | Auto-generated notes + your own manual notes per video |
| 💬 Q&A | Ask any question about a video — answered from its transcript |
| ⬇️ Download | Save as **MP3** (audio) or **MP4** (720p / 1080p / best) using yt-dlp + FFmpeg |
| 🔍 Search | Full-text search across titles, channels, notes, and summaries |
| 📊 Dashboard | At-a-glance counts + overall watch-progress bar across your whole library |
| ⚙️ Settings | One-click **yt-dlp updater** to fix YouTube signature / JS-challenge errors |

---

## 🚀 Quick Start

### 1. Prerequisites

| Tool | Install |
|---|---|
| Python 3.11 | [python.org](https://python.org) |
| FFmpeg 6+ | `winget install --id Gyan.FFmpeg -e` (Windows) |
| Git | [git-scm.com](https://git-scm.com) |

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

## ⬇️ Download Feature

The Download tab on every video detail page lets you save videos locally.

### Format Options

| Format | Codec | Plays in |
|---|---|---|
| 🎧 Audio only | MP3 192k | All players |
| 📹 Video 720p | H.264 + AAC → MP4 | All players incl. Windows Media Player |
| 📹 Video 1080p | H.264 + AAC → MP4 | All players incl. Windows Media Player |
| 📹 Video Best | H.264 + AAC → MP4 | All players incl. Windows Media Player |

> Downloads use **H.264** specifically to ensure compatibility with Windows Media Player, which cannot decode AV1 (YouTube’s newer default codec).

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
│   └── streamlit_app.py       # Main web UI (all pages)
├── core/
│   ├── __init__.py            # Groq model cascade helper
│   ├── downloader.py          # yt-dlp wrapper — H.264 MP4 / MP3
│   ├── notes_generator.py     # Auto bullet notes
│   ├── storage.py             # JSON persistence (videos + collections)
│   ├── summarizer.py          # AI summary + Q&A (Groq / OpenAI)
│   ├── transcript_extractor.py# yt-dlp subtitle extraction
│   └── youtube_fetcher.py     # YouTube Data API v3 metadata
├── models/
│   ├── video.py               # Video dataclass + WatchStatus enum
│   └── collection.py          # Collection dataclass
├── data/
│   ├── videos.json            # Your saved videos (gitignored)
│   └── collections.json       # Your collections (gitignored)
├── downloads/                 # Downloaded media files (gitignored)
├── tests/
├── .env.example
├── CHANGELOG.md
├── requirements.txt
├── run.bat
└── run.ps1
```

---

## 🔧 Troubleshooting

### yt-dlp: “Signature solving failed” / muted download / missing formats

YouTube regularly updates its JS challenge. Keeping yt-dlp current fixes this.

**Easiest fix — use the in-app updater:**
Go to **⚙️ Settings → Update yt-dlp** and click the button. Restart Streamlit after.

**Or run manually:**
```powershell
py -3.11 -m pip install -U yt-dlp
```

### Video plays without sound / won’t play in Windows Media Player

YouTube serves AV1 by default — Windows Media Player cannot decode AV1. The downloader forces H.264. If you have an old download:
1. Delete the file from `downloads/`
2. Re-download via the app

### “FFmpeg not found”

```powershell
winget install --id Gyan.FFmpeg -e
# Close terminal, reopen, then:
ffmpeg -version
```

### “yt-dlp not installed”

```powershell
py -3.11 -m pip install yt-dlp
```

### Transcript not found

Some videos disable transcripts. Use the **Paste** or **Upload** option in the Transcript tab on the video detail page.

### AI summary fails

Check your `.env` — ensure `GROQ_API_KEY` or `OPENAI_API_KEY` is set and `AI_PROVIDER` matches.

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
