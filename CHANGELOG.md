# Changelog

All notable changes to YouTube Learning Tracker will be documented here.

Format: [Semantic Versioning](https://semver.org)

---

## [1.0.1] — 2026-06-19

### Fixed
- `core/transcript_extractor.py` — switched to `YouTubeTranscriptApi().list()` instance
  method (v1.x API); removed duplicate unreachable `except Exception` clause
  (`reportUnusedExcept`)
- `core/notes_generator.py` — replaced `hasattr(block, "text")` with
  `isinstance(block, TextBlock)` from `anthropic.types` to properly narrow
  the Anthropic SDK content union type and silence `reportAttributeAccessIssue`
  for `ThinkingBlock`, `ToolUseBlock`, `RedactedThinkingBlock`, etc.
- `core/summarizer.py` — same `isinstance(block, TextBlock)` fix applied to
  both `_summarize_anthropic()` and `answer_question()`
- `cli.py` — added `if fetched is None: return` guard after `fetcher.fetch_video()`
  to prevent `Video | None` attribute access errors
- `requirements.txt` — bumped `youtube-transcript-api` pin from `>=0.6.2` to
  `>=1.0.0` to match the v1.x instance API now used in `transcript_extractor.py`;
  uncommented `anthropic` and `openai` so all optional AI providers install cleanly

---

## [1.0.0] — 2026-06-19

### Added
- Initial V1 project structure — web app + CLI
- `core/storage.py` — local JSON read/write with search and filter
- `core/youtube_fetcher.py` — YouTube Data API v3 wrapper
- `core/transcript_extractor.py` — auto transcript + manual/upload fallback
- `core/summarizer.py` — bullet + paragraph summary (Anthropic / OpenAI / Groq / basic)
- `core/notes_generator.py` — auto notes generation + manual notes support
- `models/video.py` — Video dataclass with WatchStatus enum
- `cli.py` — full CLI with add, list, view, status, transcript, summary, note, search, stats
- `app/streamlit_app.py` — web dashboard with Dashboard, Add Video, Library, Search, Settings
- `.env.example` and `.streamlit/secrets.toml.example`
- `.gitignore` — blocks data files, env files, and personal data
- `requirements.txt`

### Watch Statuses
- Saved, Watching, Completed, Dropped, Rewatch

### AI Providers
- Anthropic Claude, OpenAI GPT, Groq (free tier), or basic fallback

---

## [Upcoming] — V2
- Transcript-based Q&A
- Auto-tagging by topic and channel
- Better note organization
- Improved summary options

## [Upcoming] — V3
- Playlist import
- Revision reminders
- Export (Markdown, PDF, CSV)
- Learning analytics
