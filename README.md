# 📺 YouTube Learning Tracker

> Local-first web app and CLI to save YouTube videos, extract transcripts, generate summaries and notes, and track your learning progress.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-orange.svg)](CHANGELOG.md)

---

## 🚀 What It Does

YouTube Learning Tracker helps you:
- 📌 **Save** YouTube videos by URL
- 📝 **Extract** transcripts (auto + manual fallback)
- 🧠 **Summarize** content (bullets + paragraph styles)
- 🗒️ **Create** auto and manual notes per video
- 📊 **Track** watch status (Saved / Watching / Completed / Dropped / Rewatch)
- 🔍 **Search** and filter your saved video library

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

---

## 🛠️ Tech Stack

- **Language:** Python 3.11+
- **Web App:** Streamlit
- **CLI:** argparse + Rich
- **Storage:** Local JSON (no database needed for V1)
- **YouTube API:** YouTube Data API v3
- **Transcript:** youtube-transcript-api
- **Summarization:** AI via API (Anthropic / OpenAI / Groq — configurable)

---

## 📦 Installation

```bash
# 1. Clone the repo
git clone https://github.com/Samuel-025/youtube-learning-tracker.git
cd youtube-learning-tracker

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

---

## ▶️ Usage

### Web App
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
```

---

## 🗂️ Project Structure

```
youtube-learning-tracker/
├── app/                        # Streamlit web app
│   ├── streamlit_app.py        # Main entry point
│   ├── pages/
│   │   ├── 01_dashboard.py
│   │   ├── 02_add_video.py
│   │   └── 03_video_detail.py
│   └── components/
│       ├── video_card.py
│       └── sidebar.py
├── core/                       # Shared business logic
│   ├── __init__.py
│   ├── youtube_fetcher.py      # YouTube Data API wrapper
│   ├── transcript_extractor.py # Transcript auto + fallback
│   ├── summarizer.py           # Bullet + paragraph summary
│   ├── notes_generator.py      # Auto + manual notes
│   └── storage.py              # Local JSON read/write
├── models/
│   ├── __init__.py
│   └── video.py                # Video data model
├── data/                       # Local storage (gitignored)
│   └── .gitkeep
├── cli.py                      # CLI entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── CHANGELOG.md
└── README.md
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | ✅ | YouTube Data API v3 key |
| `ANTHROPIC_API_KEY` | Optional | For Claude-based summaries |
| `OPENAI_API_KEY` | Optional | For GPT-based summaries |
| `GROQ_API_KEY` | Optional | For free Groq-based summaries |

Get a free YouTube API key at [console.cloud.google.com](https://console.cloud.google.com).

---

## 🗺️ Roadmap

### V1 — Core (current)
- Save, transcript, summarize, notes, status tracking

### V2 — Study Mode
- Ask questions from transcript text
- Auto-tagging by topic and channel
- Improved note organization

### V3 — Automation
- Playlist import
- Revision reminders
- Export (Markdown, PDF, CSV)
- Learning analytics

---

## 📄 License

MIT — see [LICENSE](LICENSE)
