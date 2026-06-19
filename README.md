# 📺 YouTube Learning Tracker

Save YouTube videos, extract transcripts, generate AI summaries and notes, track watch status, ask questions — and now **download audio or video** directly.

> **Local-first.** All your data stays on your machine. Nothing is uploaded to GitHub — API keys, video library, transcripts, and downloaded files are all excluded by `.gitignore`.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 Save videos | Paste a YouTube URL — title, channel, thumbnail, duration auto-fetched |
| 📄 Transcripts | Auto-extracted via yt-dlp (manual + auto captions) or paste/upload |
| 🤖 AI Summary | Bullet points + paragraph summary via Groq / OpenAI / Anthropic |
| 🗒️ Notes | Auto-generated notes + your own manual notes per video |
| 🎯 Watch status | saved → watching → completed → dropped → rewatch |
| ❓ Ask questions | Ask anything about a video — answered from its transcript |
| ⬇️ Download | Download audio (MP3) or video (720p / 1080p / best MP4) via yt-dlp |
| 🔍 Search | Full-text search across titles, channels, notes, and summaries |

---

## 🚀 Quick Start

### 1. Clone
```powershell
git clone https://github.com/Samuel-025/youtube-learning-tracker.git
cd youtube-learning-tracker
```

### 2. Install Python dependencies
```powershell
py -3.11 -m pip install -r requirements.txt
```

### 3. Install FFmpeg (required for download feature)

FFmpeg is a **system binary**, not a pip package. Install it with:

```powershell
# Windows (winget — recommended)
winget install --id Gyan.FFmpeg -e

# Windows (Chocolatey)
choco install ffmpeg -y

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg -y
```

> ⚠️ Do NOT run `pip install ffmpeg` — that installs a useless stub that does nothing.

Verify: `ffmpeg -version`

### 4. Configure API keys
```powershell
copy .env.example .env
# Edit .env and fill in your keys
```

### 5. Run
```powershell
.\run.ps1
# or
py -3.11 -m streamlit run app/streamlit_app.py
```

---

## 🔑 API Keys

| Key | Required | Free | Get it |
|---|---|---|---|
| `YOUTUBE_API_KEY` | Yes | ✅ 10k req/day | [console.cloud.google.com](https://console.cloud.google.com) |
| `GROQ_API_KEY` | Recommended | ✅ No credit card | [console.groq.com](https://console.groq.com) |
| `OPENAI_API_KEY` | Optional | ❌ Paid | [platform.openai.com](https://platform.openai.com) |
| `ANTHROPIC_API_KEY` | Optional | ❌ Paid | [console.anthropic.com](https://console.anthropic.com) |

All keys go in `.env` (never committed to Git).

---

## ⬇️ Download Feature

Open any saved video → click the **⬇️ Download** tab.

| Mode | Format | Quality |
|---|---|---|
| 🎧 Audio only | MP3 | 192k best audio |
| 📹 Video 720p | MP4 | 720p + audio merged |
| 📹 Video 1080p | MP4 | 1080p + audio merged |
| 📹 Video Best | MP4 | Highest available |

Files are saved to `downloads/` inside the project folder. That folder is in `.gitignore` — **downloaded files are never pushed to GitHub**.

After download, a **📥 Save to computer** button lets you save the file wherever you want.

---

## 🔒 Privacy & Security

| What | Where stored | Uploaded to GitHub? |
|---|---|---|
| API keys | `.env` | ❌ Never |
| Video library | `data/videos.json` | ❌ Never |
| Transcripts | inside `videos.json` | ❌ Never |
| Notes | inside `videos.json` | ❌ Never |
| Downloaded files | `downloads/*.mp3/mp4` | ❌ Never |
| AI summaries | inside `videos.json` | ❌ Never |

Only source code is pushed to GitHub. All personal data stays local.

---

## 📁 Project Structure

```
youtube-learning-tracker/
├── app/
│   └── streamlit_app.py      # Streamlit web UI
├── core/
│   ├── downloader.py         # yt-dlp audio/video download
│   ├── notes_generator.py    # Auto notes from transcript
│   ├── storage.py            # JSON persistence
│   ├── summarizer.py         # AI summarization + Q&A
│   ├── transcript_extractor.py # yt-dlp + fallback transcript
│   └── youtube_fetcher.py    # YouTube Data API v3
├── models/
│   └── video.py              # Video dataclass + WatchStatus enum
├── data/
│   └── .gitkeep              # Folder tracked; videos.json ignored
├── downloads/
│   └── .gitkeep              # Folder tracked; all media files ignored
├── .env.example              # Template — copy to .env and fill in keys
├── .gitignore                # Blocks keys, data, downloads, media
├── requirements.txt          # Python deps + FFmpeg install instructions
├── run.bat                   # Windows batch launcher
├── run.ps1                   # PowerShell launcher
└── cli.py                    # CLI interface
```

---

## 🛡️ Security

See [SECURITY.md](SECURITY.md) for responsible disclosure policy.

---

## 📝 License

MIT — see [LICENSE](LICENSE).
