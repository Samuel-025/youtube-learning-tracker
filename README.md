# 📺 YouTube Learning Tracker

> Local-first web app and CLI to save YouTube videos, extract transcripts, generate summaries and notes, and track your learning progress.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.1-orange.svg)](CHANGELOG.md)

---

## 🚀 What It Does

YouTube Learning Tracker helps you:
- 📌 **Save** YouTube videos by URL
- 📝 **Extract** transcripts (auto + manual fallback)
- 🧠 **Summarize** content (bullets + paragraph styles)
- 🗒️ **Create** auto and manual notes per video
- 📊 **Track** watch status (Saved / Watching / Completed / Dropped / Rewatch)
- 🔍 **Search** and filter your saved video library
- ❓ **Ask questions** answered from the video transcript

---

## ✨ V1 Features

| Feature | Web App | CLI |
|---|---|---|
| Add video by URL | ✅ | ✅ |
| Fetch metadata (title, channel, thumbnail) | ✅ | ✅ |
| Store transcript text | ✅ | ✅ |
| Manual transcript paste / upload | ✅ | ✅ |
| Bullet + paragraph summary | ✅ | ✅ |
| Auto-generated notes | ✅ | ✅ |
| Manual notes | ✅ | ✅ |
| Watch status tracking | ✅ | ✅ |
| Search & filter library | ✅ | ✅ |
| Local JSON storage | ✅ | ✅ |
| Ask questions from transcript | ✅ | ✅ |

---

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **Web App:** Streamlit
- **CLI:** argparse + Rich
- **Storage:** Local JSON (no database needed for V1)
- **YouTube API:** YouTube Data API v3
- **Transcript:** youtube-transcript-api ≥ 1.0.0
- **Summarization:** AI via API (Anthropic / OpenAI / Groq — configurable)

---

## 📋 Prerequisites

Before you start, make sure you have:
- **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- **A YouTube Data API v3 key** — [console.cloud.google.com](https://console.cloud.google.com) (free, 10,000 units/day)
- **An AI provider key** *(optional but recommended for smart summaries)*
  - **Groq** (free, no credit card) — [console.groq.com](https://console.groq.com) ✅ Recommended
  - OpenAI or Anthropic — paid, optional

> 💡 **No AI key?** Set `AI_PROVIDER=none` in your `.env` — the app still works with basic text summaries.

---

## 📦 Installation

```bash
# 1. Clone the repo
git clone https://github.com/Samuel-025/youtube-learning-tracker.git
cd youtube-learning-tracker

# 2. Create virtual environment
python -m venv venv

# Activate — Linux / Mac
source venv/bin/activate

# Activate — Windows (PowerShell)
venv\Scripts\Activate.ps1

# Activate — Windows (CMD)
venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env       # Windows
cp .env.example .env         # Linux / Mac

# 5. Edit .env with your API keys
# At minimum set YOUTUBE_API_KEY=your_key_here
```

---

## ▶️ Running Locally

### Web App (Streamlit)
```bash
streamlit run app/streamlit_app.py
```
Opens at `http://localhost:8501`

### CLI
```bash
python cli.py --help

# Add a video
python cli.py add "https://www.youtube.com/watch?v=VIDEO_ID"

# List all saved videos
python cli.py list

# View video details
python cli.py view VIDEO_ID

# Update watch status
python cli.py status VIDEO_ID watching

# Show transcript
python cli.py transcript VIDEO_ID

# Show summary
python cli.py summary VIDEO_ID

# Add a note
python cli.py note VIDEO_ID "Your note text here"

# Ask a question about a video
python cli.py ask VIDEO_ID "What is the main concept?"

# Search library
python cli.py search "python"

# Show stats
python cli.py stats
```

---

## 🗂️ Project Structure

```
youtube-learning-tracker/
├── app/                        # Streamlit web app
│   └── streamlit_app.py        # Main entry point (single-file app)
├── core/                       # Shared business logic
│   ├── youtube_fetcher.py      # YouTube Data API v3 wrapper
│   ├── transcript_extractor.py # Transcript auto + fallback
│   ├── summarizer.py           # Bullet + paragraph summary + Q&A
│   ├── notes_generator.py      # Auto + manual notes
│   └── storage.py              # Local JSON read/write
├── models/
│   └── video.py                # Video dataclass with WatchStatus enum
├── data/                       # Local storage (gitignored — your data stays local)
│   └── .gitkeep
├── cli.py                      # CLI entry point
├── requirements.txt
├── .env.example                # Copy to .env and fill in your keys
├── .gitignore
├── CHANGELOG.md
└── README.md
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | ✅ Yes | YouTube Data API v3 key |
| `AI_PROVIDER` | Optional | `groq` / `openai` / `anthropic` / `none` (default: `groq`) |
| `GROQ_API_KEY` | Optional | Free Groq API key (recommended) |
| `OPENAI_API_KEY` | Optional | OpenAI API key |
| `ANTHROPIC_API_KEY` | Optional | Anthropic Claude API key |
| `STORAGE_PATH` | Optional | Path to JSON storage file (default: `data/videos.json`) |

---

## ⚠️ Known Issues

- **Transcript unavailable for some videos** — YouTube restricts transcripts on certain videos (music, movies, auto-captions disabled). Use the manual paste or upload fallback in the app.
- **YouTube API quota** — The free tier gives 10,000 units/day. Each video fetch uses ~1 unit. Adding many videos quickly may hit the limit.
- **youtube-transcript-api v1.x required** — The project uses the v1.x instance API (`YouTubeTranscriptApi().list()`). Versions below 1.0.0 will not work.

---

## 🗺️ Roadmap

### V1 — Core (current)
- Save, transcript, summarize, notes, status tracking, Q&A

### V2 — Study Mode
- Auto-tagging by topic and channel
- Improved note organization
- Tag-based filtering

### V3 — Automation
- Playlist import
- Revision reminders
- Export (Markdown, PDF, CSV)
- Learning analytics

---

## 📄 License

MIT — see [LICENSE](LICENSE)
