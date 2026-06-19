# 📺 YouTube Learning Tracker

A personal learning companion that saves, organises, summarises, and downloads YouTube videos — all from a clean Streamlit web app running locally on your machine.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 Save videos | Paste any YouTube URL to fetch metadata, thumbnail, and transcript automatically |
| 📚 Library | Browse your saved videos, filter by status, sort by title or date |
| 🤖 AI Summary | Bullet-point summary + paragraph overview generated from the transcript |
| 🗒️ Notes | Auto-generated notes + your own manual notes per video |
| 💬 Q&A | Ask any question about a video — answered from its transcript |
| ⬇️ Download | Download as **MP3** (audio) or **MP4** (720p / 1080p / best) — H.264, plays everywhere |
| 🔍 Search | Full-text search across titles, channels, notes, and summaries |
| 📊 Dashboard | At-a-glance counts: saved / watching / completed / dropped / rewatch |

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

> **Note:** Downloads use H.264 video codec specifically to ensure compatibility with Windows Media Player, which cannot decode AV1 (YouTube's newer default codec).

### FFmpeg Status

The Download tab shows a banner:
- ✅ **Green** — FFmpeg detected, all formats available, MP3 conversion enabled
- ⚠️ **Yellow** — FFmpeg not found; audio downloads as `.m4a`, video downloads as progressive MP4 (max 720p)

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
│   └── streamlit_app.py      # Main web UI
├── core/
│   ├── downloader.py          # yt-dlp wrapper — H.264 MP4 / MP3 downloads
│   ├── summarizer.py          # AI summary + Q&A (Groq / OpenAI)
│   ├── notes_generator.py     # Auto bullet notes
│   ├── storage.py             # JSON persistence
│   ├── transcript_extractor.py# yt-dlp transcript extraction
│   └── youtube_fetcher.py     # YouTube Data API v3 metadata
├── models/
│   └── video.py               # Video dataclass + WatchStatus enum
├── data/
│   └── videos.json            # Your saved videos (git-ignored)
├── downloads/                 # Downloaded media files (git-ignored)
├── tests/
├── .env.example
├── requirements.txt
├── run.bat
└── run.ps1
```

---

## 🔧 Troubleshooting

### Video plays without sound / video won't play in Windows Media Player
YouTube now serves AV1 video by default — Windows Media Player cannot decode AV1. The downloader forces H.264. If you have an old download:
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
Some videos disable transcripts. Use the **Paste** or **Upload** option in the Transcript tab.

### AI summary fails
Check your `.env` — ensure `GROQ_API_KEY` or `OPENAI_API_KEY` is set and `AI_PROVIDER` matches.

---

## 🛡️ Privacy & Security

- All data is stored **locally** in `data/videos.json` — never uploaded anywhere
- Downloaded media is stored in `downloads/` — git-ignored, never committed
- API keys live in `.env` — git-ignored, never committed
- See [SECURITY.md](SECURITY.md) for the responsible disclosure policy

---

## 📄 License

MIT — see [LICENSE](LICENSE)
