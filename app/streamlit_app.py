import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, date
from typing import cast

import streamlit as st
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env", override=True)

from core.storage import Storage
from core.settings_store import SettingsStore
from core.exporters import (
    export_csv,
    export_markdown_library,
    export_video_json,
    export_anki_csv,
    export_all_anki_csv,
    export_obsidian_markdown,
    sync_to_notion,
)
from core.youtube_fetcher import YouTubeFetcher, extract_video_id
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from core.downloader import Downloader, ffmpeg_version, DownloadMode
from core.due_date import due_badge
from core.ui_helpers import _apply_progress, _week_watched_hours, _linkify_timestamps
from models.video import Video, WatchStatus
from models.collection import Collection

try:
    import plotly.express as px
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

css_file = root / "app" / "style.css"
if css_file.exists():
    st.markdown(f"<style>{css_file.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

storage_path = os.getenv("STORAGE_PATH", str(root / "data" / "videos.json"))
settings_path = str(root / "data" / "settings.json")
storage = Storage(storage_path)
settings = SettingsStore(settings_path)
fetcher = YouTubeFetcher()
extractor = TranscriptExtractor()
summarizer = Summarizer()
notes_gen = NotesGenerator()
downloader = Downloader()

PAGES = ["📊 Dashboard", "➕ Add Video", "📚 Library", "🗂 Collections", "⚙️ Settings"]


def init_state() -> None:
    st.session_state.setdefault("page", "📊 Dashboard")
    st.session_state.setdefault("detail_video_id", None)
    st.session_state.setdefault("pending_video", None)
    st.session_state.setdefault("import_done", False)


# ── on_click callbacks (run before widgets, safe for session state) ──

def _cb_nav(page: str) -> None:
    st.session_state["page"] = page
    st.session_state["sidebar_nav"] = page
    st.session_state["detail_video_id"] = None


def _cb_view_video(video_id: str) -> None:
    st.session_state["page"] = "📚 Library"
    st.session_state["sidebar_nav"] = "📚 Library"
    st.session_state["detail_video_id"] = video_id


def _cb_back_to_library() -> None:
    st.session_state["detail_video_id"] = None


def _cb_clear_import() -> None:
    st.session_state["import_done"] = False


def all_videos() -> list[Video]:
    return storage.get_all_videos()


def all_collections() -> list[Collection]:
    return storage.get_all_collections()


def save_video_and_enrich(video: Video) -> None:
    if video.transcript_text.strip():
        try:
            bullets, paragraph = summarizer.summarize(video.transcript_text, video.title)
            video.summary_bullets = bullets
            video.summary_paragraph = paragraph
        except Exception as exc:
            st.warning(f"Summary generation skipped: {exc}")
        try:
            video.auto_notes = notes_gen.generate_auto_notes(video.transcript_text, video.title)
        except Exception as exc:
            st.warning(f"Auto-notes generation skipped: {exc}")
    storage.save_video(video)


def render_sidebar() -> None:
    with st.sidebar:
        st.title("📺 YouTube Tracker")
        if "sidebar_nav" not in st.session_state or st.session_state["sidebar_nav"] != st.session_state["page"]:
            st.session_state["sidebar_nav"] = st.session_state["page"]
        current = st.radio("Navigate", PAGES, key="sidebar_nav")
        if current != st.session_state["page"]:
            st.session_state["page"] = current
            st.session_state["detail_video_id"] = None
            st.rerun()


# ── Dashboard ──

def page_dashboard() -> None:
    st.title("📊 Dashboard")
    videos = all_videos()
    colls = all_collections()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos", len(videos))
    c2.metric("Collections", len(colls))
    c3.metric("Completed", sum(1 for v in videos if v.status == WatchStatus.COMPLETED))
    c4.metric("Watching", sum(1 for v in videos if v.status == WatchStatus.WATCHING))

    st.subheader("Recently Added")
    recent = sorted(videos, key=lambda v: v.created_at, reverse=True)[:8]
    if not recent:
        st.info("No videos saved yet.")
        return

    for video in recent:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, width="stretch")
        with cols[1]:
            meta = f"{video.channel} • {video.duration} • {video.status.value}"
            badge = due_badge(video)
            if badge:
                meta += f" • {badge[0]} {badge[1]}"
            st.markdown(f"**{video.title}**")
            st.caption(meta)
            if video.rating:
                st.markdown("⭐" * video.rating)
        with cols[2]:
            st.button("View", key=f"dash_view_{video.video_id}", on_click=_cb_view_video, args=(video.video_id,))


# ── Add Video ──

def page_add_video() -> None:
    st.title("➕ Add Video")

    url = st.text_input("YouTube URL")
    fetch_clicked = st.button("Fetch video", type="primary")

    if fetch_clicked:
        try:
            with st.spinner("Fetching metadata…"):
                video = fetcher.fetch_video(url, storage=storage)
            st.session_state["pending_video"] = video
            st.success("Metadata fetched.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not fetch metadata: {exc}")

    pending = st.session_state.get("pending_video")
    if not pending:
        return

    video: Video = pending
    st.subheader(video.title)
    if video.thumbnail_url:
        st.image(video.thumbnail_url, width=320)
    st.write(f"**Channel:** {video.channel}")
    st.write(f"**Duration:** {video.duration}")
    st.write(f"**Published:** {video.published_at}")

    transcript_mode = st.radio(
        "Transcript source",
        ["Auto-fetch", "Paste manually", "Skip for now"],
        horizontal=True,
        key="transcript_mode",
    )

    if transcript_mode == "Auto-fetch":
        if st.button("Fetch transcript", key="fetch_transcript"):
            try:
                vid = extract_video_id(video.url) or video.video_id
                with st.spinner("Fetching transcript…"):
                    fetched_text, fetched_source = extractor.extract(vid)
                if fetched_text:
                    video.transcript_text = fetched_text
                    video.transcript_source = fetched_source
                    st.success(f"Transcript fetched via {fetched_source}.")
                else:
                    st.warning("No transcript found.")
            except Exception as exc:
                st.error(f"Transcript fetch failed: {exc}")

    transcript_text = video.transcript_text
    if transcript_mode == "Paste manually":
        transcript_text = st.text_area("Paste transcript", value=video.transcript_text, height=220)

    tags_raw = st.text_input("Tags (comma-separated)")
    manual_notes = st.text_area("Manual notes", value=video.manual_notes, height=140)

    if st.button("Save video", key="save_video", type="primary"):
        video.transcript_text = transcript_text.strip()
        if transcript_mode == "Auto-fetch":
            pass
        elif transcript_mode == "Paste manually":
            video.transcript_source = "manual" if transcript_text.strip() else video.transcript_source
        else:
            video.transcript_source = ""
        video.manual_notes = manual_notes.strip()
        video.tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        try:
            with st.spinner("Generating summary and notes…"):
                save_video_and_enrich(video)
            st.session_state["pending_video"] = None
            st.success("Video saved.")
            st.session_state["page"] = "📚 Library"
            st.session_state["sidebar_nav"] = "📚 Library"
            st.session_state["detail_video_id"] = video.video_id
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save video: {exc}")


# ── Video Detail ──

def render_video_detail(video: Video) -> None:
    col_left, col_right = st.columns([3, 1])
    with col_left:
        st.subheader(video.title)
        st.write(f"**Channel:** {video.channel}  •  **Duration:** {video.duration}")
        st.write(f"**URL:** {video.url}")
    with col_right:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")

    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
    with c1:
        status = st.selectbox(
            "Status",
            [s.value for s in WatchStatus],
            index=[s.value for s in WatchStatus].index(video.status.value),
            key=f"status_{video.video_id}",
        )
    with c2:
        rating = st.select_slider(
            "Rating",
            options=[0, 1, 2, 3, 4, 5],
            value=video.rating,
            format_func=lambda x: "No rating" if x == 0 else "⭐" * x,
            key=f"rating_{video.video_id}",
        )
    with c3:
        due = video.due_date
        try:
            due_parsed = date.fromisoformat(due) if due else None
        except (ValueError, TypeError):
            due_parsed = None
        due_date_val = st.date_input(
            "Due date",
            value=due_parsed or date.today(),
            key=f"due_{video.video_id}",
        )
        clear_due = st.checkbox("Clear due date", key=f"clear_due_{video.video_id}")
    with c4:
        colls_for_video = storage.get_collections_for_video(video.video_id)
        st.write("**Collections**")
        if colls_for_video:
            for c in colls_for_video:
                st.caption(f"{c.emoji} {c.name}")
        else:
            st.caption("None")
    with c5:
        st.write("**Export**")
        json_str = export_video_json(video)
        st.download_button(
            "📄 JSON", json_str,
            file_name=f"{video.video_id}.json",
            mime="application/json",
            key=f"export_{video.video_id}",
        )

    col_u1, col_u2 = st.columns([1, 1])
    with col_u1:
        if st.button("Update video", key=f"update_{video.video_id}", type="primary"):
            video.status = WatchStatus(status)
            video.rating = rating
            if clear_due:
                video.due_date = None
            else:
                video.due_date = due_date_val.isoformat()
            video.updated_at = datetime.now().isoformat()
            storage.update_video(video)
            st.success("Updated.")
            st.rerun()

    with col_u2:
        with st.popover("🗑️ Delete Video"):
            st.warning(f"Are you sure you want to delete '{video.title}'?")
            del_files = st.checkbox("Also delete downloaded media file on disk", value=True, key=f"del_files_{video.video_id}")
            if st.button("Yes, Delete Video", key=f"confirm_del_{video.video_id}", type="primary"):
                storage.delete_video(video.video_id, del_files)
                st.session_state["detail_video_id"] = None
                st.success("Video deleted.")
                st.rerun()

    st.divider()

    tabs = st.tabs(["Summary", "Transcript", "Notes", "Progress", "Download", "Q&A", "⚡ Study & Export"])

    with tabs[0]:
        if video.summary_paragraph:
            st.markdown("### Summary")
            st.write(video.summary_paragraph)
        if video.summary_bullets:
            st.markdown("### Key Takeaways")
            for bullet in video.summary_bullets:
                st.markdown(f"- {bullet}")
        if not video.summary_paragraph and not video.summary_bullets:
            st.info("No summary available. Add a transcript and save to generate one.")

    with tabs[1]:
        if video.transcript_text:
            view_mode = st.radio("View mode", ["📋 Raw text", "🔗 Clickable timestamps"], horizontal=True, key="ts_mode")
            if view_mode == "🔗 Clickable timestamps":
                linked = _linkify_timestamps(video.transcript_text, video.url)
                st.markdown(linked, unsafe_allow_html=True)
            else:
                st.text_area("Transcript", value=video.transcript_text, height=400, disabled=True)
        else:
            st.info("No transcript available.")

    with tabs[2]:
        c_n1, c_n2 = st.columns(2)
        with c_n1:
            st.markdown("### Auto-generated Notes")
            if video.auto_notes:
                for note in video.auto_notes:
                    st.markdown(f"- {note}")
            else:
                st.info("No auto-notes generated.")
        with c_n2:
            st.markdown("### Manual Notes")
            new_notes = st.text_area("Edit notes", value=video.manual_notes, height=200, key=f"notes_{video.video_id}")
            if st.button("Save notes", key=f"save_notes_{video.video_id}"):
                video.manual_notes = new_notes
                video.updated_at = datetime.now().isoformat()
                storage.update_video(video)
                st.success("Notes saved.")
                st.rerun()

    with tabs[3]:
        st.markdown("### Watch Progress")
        if video.duration_sec <= 0:
            st.warning("Duration unknown — cannot show progress slider.")
        else:
            current_pct = video.progress_pct
            new_pct = st.slider("Progress (%)", 0, 100, int(current_pct), key=f"prog_slider_{video.video_id}")
            col_q1, col_q2, col_q3, col_q4, col_q5 = st.columns(5)
            with col_q1:
                if st.button("0%", key=f"prog_0_{video.video_id}"):
                    new_pct = 0
            with col_q2:
                if st.button("25%", key=f"prog_25_{video.video_id}"):
                    new_pct = 25
            with col_q3:
                if st.button("50%", key=f"prog_50_{video.video_id}"):
                    new_pct = 50
            with col_q4:
                if st.button("75%", key=f"prog_75_{video.video_id}"):
                    new_pct = 75
            with col_q5:
                if st.button("100%", key=f"prog_100_{video.video_id}"):
                    new_pct = 100

            st.progress(new_pct / 100)
            new_sec = int(new_pct / 100 * video.duration_sec)
            if st.button("Apply progress", key=f"apply_prog_{video.video_id}", type="primary"):
                celebration = _apply_progress(video, new_sec)
                video.updated_at = datetime.now().isoformat()
                storage.update_video(video)
                if celebration:
                    st.success(celebration)
                else:
                    st.success(f"Progress set to {new_pct}%.")
                st.rerun()

    with tabs[4]:
        st.markdown("### Download")
        ff_version = ffmpeg_version()
        if ff_version:
            st.success(f"✅ FFmpeg detected: {ff_version}")
        else:
            st.warning("⚠️ FFmpeg not found. Audio saves as M4A, video max 720p progressive.")

        if not downloader.is_available():
            st.error("yt-dlp is not installed. Run: `pip install yt-dlp`")
        else:
            dl_mode = st.selectbox(
                "Format",
                ["audio", "video_720", "video_1080", "video_best"],
                format_func=lambda x: {
                    "audio": "🎧 Audio (MP3)",
                    "video_720": "📹 Video 720p",
                    "video_1080": "📹 Video 1080p",
                    "video_best": "📹 Video Best",
                }[x],
                key=f"dl_mode_{video.video_id}",
            )
            if st.button("Download", key=f"dl_btn_{video.video_id}", type="primary"):
                try:
                    with st.spinner("Downloading…"):
                        path = downloader.download(video.video_id, cast(DownloadMode, dl_mode))
                    if path.exists():
                        video.local_path = str(path)
                        video.updated_at = datetime.now().isoformat()
                        storage.update_video(video)
                        st.success(f"Downloaded: {path.name}")
                except RuntimeError as exc:
                    video.local_path = None
                    video.updated_at = datetime.now().isoformat()
                    storage.update_video(video)
                    st.error(str(exc))

        if video.local_path:
            lp = Path(video.local_path)
            if lp.exists():
                sz = lp.stat().st_size / 1024 / 1024
                st.info(f"📁 Downloaded: {lp.name} ({sz:.1f} MB)")
                with open(lp, "rb") as f:
                    st.download_button("📂 Open file", f, file_name=lp.name, key=f"open_{video.video_id}")

    with tabs[5]:
        st.markdown("### Ask a Question")
        question = st.text_input("Ask a question about this video", key=f"q_{video.video_id}")
        if st.button("Ask", key=f"ask_{video.video_id}") and question.strip():
            if not video.transcript_text.strip():
                st.warning("No transcript available to answer questions.")
            else:
                with st.spinner("Thinking…"):
                    answer = summarizer.answer_question(video.transcript_text, question, video.title)
                st.markdown("**Answer:**")
                st.write(answer)

    with tabs[6]:
        st.markdown("### ⚡ Study & Integrations Suite")
        st.caption("Generate AI flashcards, export Obsidian notes, download Anki decks, or sync directly with Notion.")

        c_fc1, c_fc2 = st.columns([2, 1])
        with c_fc1:
            st.markdown("#### 🃏 AI Flashcards")
            if video.flashcards:
                for idx, fc in enumerate(video.flashcards, 1):
                    with st.expander(f"🎴 Card #{idx}: {fc.get('front', '')[:60]}…"):
                        st.markdown(f"**Q:** {fc.get('front', '')}")
                        st.markdown(f"**A:** {fc.get('back', '')}")
            else:
                st.info("No flashcards generated yet for this video.")

        with c_fc2:
            st.markdown("#### ⚙️ Generate")
            if st.button("✨ Generate AI Flashcards", key=f"gen_fc_{video.video_id}", type="primary"):
                if not video.transcript_text.strip():
                    st.warning("No transcript available to generate flashcards.")
                else:
                    with st.spinner("Generating flashcards with AI…"):
                        fc_list = summarizer.generate_flashcards(video.transcript_text, video.title)
                    if fc_list:
                        video.flashcards = fc_list
                        video.updated_at = datetime.now().isoformat()
                        storage.update_video(video)
                        st.success(f"Generated {len(fc_list)} flashcards!")
                        st.rerun()
                    else:
                        st.warning("Could not generate flashcards.")

        st.divider()
        st.markdown("#### 📤 Export & Sync Options")
        c_exp1, c_exp2, c_exp3 = st.columns(3)

        with c_exp1:
            st.markdown("**📦 Anki Flashcard Deck**")
            st.caption("TSV format ready to import directly into Anki.")
            anki_tsv = export_anki_csv(video)
            st.download_button(
                "📥 Download Anki Deck (.tsv)",
                anki_tsv,
                file_name=f"{video.video_id}_anki.tsv",
                mime="text/tab-separated-values",
                key=f"dl_anki_{video.video_id}",
            )

        with c_exp2:
            st.markdown("**🪨 Obsidian Markdown Note**")
            st.caption("Formatted with YAML frontmatter, tags & GFM callouts.")
            obs_md = export_obsidian_markdown(video)
            st.download_button(
                "📥 Download Obsidian Note (.md)",
                obs_md,
                file_name=f"{video.video_id}_obsidian.md",
                mime="text/markdown",
                key=f"dl_obs_{video.video_id}",
            )

        with c_exp3:
            st.markdown("**📝 Notion Cloud Sync**")
            st.caption("Sync video metadata & notes directly into your Notion Database.")
            load_dotenv(root / ".env", override=True)
            env_key = os.getenv("NOTION_API_KEY", "").strip()
            env_db = os.getenv("NOTION_DATABASE_ID", "").strip()

            has_env_credentials = bool(env_key and env_db)

            if has_env_credentials:
                st.caption("🔒 *Loaded securely from `.env`*")
                use_custom = False
                key_to_use = env_key
                db_to_use = env_db

                with st.expander("⚙️ Override Credentials (Optional)", expanded=False):
                    override_key = st.text_input("Custom API Token", type="password", key=f"nk_ov_{video.video_id}")
                    override_db = st.text_input("Custom Database ID or URL", key=f"ndb_ov_{video.video_id}")
                    if override_key.strip() and override_db.strip():
                        use_custom = True
                        key_to_use = override_key.strip()
                        db_to_use = override_db.strip()
            else:
                st.caption("⚠️ *Credentials not configured in `.env`*")
                with st.expander("🔑 Enter Notion Credentials", expanded=True):
                    key_to_use = st.text_input("API Token", type="password", key=f"nk_in_{video.video_id}").strip()
                    db_to_use = st.text_input("Database ID or URL", type="password", key=f"ndb_in_{video.video_id}").strip()

            if st.button("🚀 Sync to Notion", key=f"sync_notion_btn_{video.video_id}", type="primary"):
                if not key_to_use or not db_to_use:
                    st.warning("Please configure Notion API Token and Database ID in `.env` or in the fields above.")
                else:
                    try:
                        with st.spinner("Syncing to Notion…"):
                            sync_to_notion(video, key_to_use, db_to_use)
                        st.success("✓ Synced to Notion successfully!")
                    except Exception as exc:
                        err_str = str(exc)
                        if key_to_use:
                            err_str = err_str.replace(key_to_use, "[REDACTED_TOKEN]")
                        st.error(f"Notion Sync failed: {err_str}")


# ── Library ──

def page_library() -> None:
    st.title("📚 Library")
    videos = all_videos()
    if not videos:
        st.info("No videos in library yet.")
        return

    detail_id = st.session_state.get("detail_video_id")
    if detail_id:
        video = storage.get_video(detail_id)
        if video:
            st.button("← Back to Library", on_click=_cb_back_to_library)
            render_video_detail(video)
            return

    c_s, c_f, c_t, c_o = st.columns([2, 1, 2, 1])
    with c_s:
        query = st.text_input("🔍 Search", placeholder="Search videos…")
    with c_f:
        status_filter = st.selectbox("Status", ["All"] + [s.value for s in WatchStatus])
    with c_o:
        sort_by = st.selectbox(
            "Sort by",
            ["Newest", "Oldest", "Title A–Z", "Title Z–A", "Progress ↑", "Progress ↓"],
        )

    all_tags = sorted(set(t for v in videos for t in (v.tags or [])))
    with c_t:
        selected_tags = st.multiselect("Filter by tags", all_tags, placeholder="Select tags…")

    filtered = videos
    if query.strip():
        q = query.lower().strip()
        filtered = [
            v for v in filtered
            if q in v.title.lower()
            or q in v.channel.lower()
            or q in " ".join(v.tags).lower()
            or q in (v.manual_notes or "").lower()
        ]
    if status_filter != "All":
        filtered = [v for v in filtered if v.status.value == status_filter]
    if selected_tags:
        for tag in selected_tags:
            filtered = [v for v in filtered if tag in (v.tags or [])]

    if sort_by == "Newest":
        filtered.sort(key=lambda v: v.created_at, reverse=True)
    elif sort_by == "Oldest":
        filtered.sort(key=lambda v: v.created_at)
    elif sort_by == "Title A–Z":
        filtered.sort(key=lambda v: v.title.lower())
    elif sort_by == "Title Z–A":
        filtered.sort(key=lambda v: v.title.lower(), reverse=True)
    elif sort_by == "Progress ↑":
        filtered.sort(key=lambda v: v.progress_pct)
    elif sort_by == "Progress ↓":
        filtered.sort(key=lambda v: v.progress_pct, reverse=True)

    st.caption(f"{len(filtered)} video(s)")

    with st.expander("⚡ Batch Actions & Library Flashcards Export"):
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            st.markdown("**📦 Export All Library Flashcards**")
            all_anki = export_all_anki_csv(videos)
            st.download_button(
                "📥 Download All Anki Decks (.tsv)",
                all_anki,
                file_name="library_all_anki.tsv",
                mime="text/tab-separated-values",
                key="dl_all_anki_lib",
            )
        with c_b2:
            st.markdown("**🗑️ Bulk Delete Videos**")
            to_del = st.multiselect("Select videos to remove", options=filtered, format_func=lambda v: v.title, key="bulk_del_select")
            if to_del:
                del_files_batch = st.checkbox("Also delete downloaded media files", value=True, key="bulk_del_files_chk")
                if st.button(f"Delete Selected ({len(to_del)})", type="primary", key="bulk_del_btn"):
                    ids = [v.video_id for v in to_del]
                    count = storage.delete_videos_batch(ids, delete_local_files=del_files_batch)
                    st.success(f"Successfully deleted {count} video(s).")
                    st.rerun()

    for video in filtered:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, width="stretch")
        with cols[1]:
            meta = f"{video.channel} • {video.duration} • {video.status.value}"
            badge = due_badge(video)
            if badge:
                meta += f" • {badge[0]} {badge[1]}"
            st.markdown(f"**{video.title}**")
            st.caption(meta)
            if video.rating:
                st.markdown("⭐" * video.rating)
            if video.tags:
                st.caption("Tags: " + ", ".join(video.tags[:3]))
            if video.duration_sec > 0:
                st.progress(video.progress_pct / 100)
        with cols[2]:
            st.button("View", key=f"lib_view_{video.video_id}", on_click=_cb_view_video, args=(video.video_id,))


# ── Collections ──

def page_collections() -> None:
    st.title("🗂 Collections")
    videos = all_videos()
    colls = all_collections()

    with st.expander("➕ Create collection"):
        c1, c2 = st.columns([1, 5])
        with c1:
            emoji = st.text_input("Emoji", value="📁", max_chars=2)
        with c2:
            name = st.text_input("Collection name")
        description = st.text_input("Description")
        if st.button("Create", key="create_collection", type="primary"):
            if not name.strip():
                st.error("Name is required.")
            else:
                coll = Collection(name=name.strip(), description=description.strip(), emoji=emoji.strip() or "📁")
                storage.save_collection(coll)
                st.success(f"Collection '{name}' created.")
                st.rerun()

    if not colls:
        st.info("No collections yet.")
        return

    for coll in colls:
        with st.expander(f"{coll.emoji} {coll.name}", expanded=True):
            if coll.description:
                st.caption(coll.description)

            coll_videos = storage.get_videos_in_collection(coll.id)
            total = len(coll.video_ids)
            completed = sum(1 for v in coll_videos if v.status == WatchStatus.COMPLETED)
            if total > 0:
                st.progress(completed / total)
                st.caption(f"{completed}/{total} completed")
            else:
                st.caption("No videos in this collection.")

            if coll_videos:
                cols = st.columns(3)
                for i, v in enumerate(coll_videos):
                    with cols[i % 3]:
                        label = v.title[:50] + "…" if len(v.title) > 50 else v.title
                        st.caption(f"**{label}**")
                        if v.thumbnail_url:
                            st.image(v.thumbnail_url, width="stretch")

            st.divider()
            selected = st.multiselect(
                "Add/remove videos",
                options=[v.video_id for v in videos],
                default=coll.video_ids,
                format_func=lambda vid: next((v.title for v in videos if v.video_id == vid), vid),
                key=f"coll_mgmt_{coll.id}",
            )
            if st.button("Save changes", key=f"save_coll_{coll.id}"):
                coll.video_ids = selected
                coll.update_timestamp()
                storage.update_collection(coll)
                st.success("Collection updated.")
                st.rerun()


# ── Settings ──

def page_settings() -> None:
    st.title("⚙️ Settings")

    st.subheader("🎯 Weekly Watch Goal")
    goal = st.number_input("Hours per week", min_value=0.0, step=0.5, value=float(settings.weekly_goal_hours))
    if st.button("Save goal", key="save_goal"):
        settings.weekly_goal_hours = goal
        st.success(f"Weekly goal set to {goal}h.")
        st.rerun()

    st.divider()

    st.subheader("📤 Export")
    videos = all_videos()
    colls = all_collections()

    col_ex1, col_ex2, col_ex3 = st.columns(3)
    with col_ex1:
        csv_data = export_csv(videos)
        st.download_button(
            "📄 Export CSV", csv_data,
            file_name="youtube_tracker.csv", mime="text/csv",
            width="stretch",
        )
    with col_ex2:
        export_data = json.dumps(storage.export_json(), indent=2, ensure_ascii=False)
        st.download_button(
            "📦 Export JSON", export_data,
            file_name="youtube_tracker.json", mime="application/json",
            width="stretch",
        )
    with col_ex3:
        md_data = export_markdown_library(videos, colls)
        st.download_button(
            "📝 Export Markdown", md_data,
            file_name="youtube_tracker.md", mime="text/markdown",
            width="stretch",
        )

    st.divider()

    st.subheader("📥 Import JSON")
    import_mode = st.radio("Import mode", ["Merge (add missing)", "Overwrite (full replace)"], horizontal=True)
    uploaded = st.file_uploader("Upload a JSON file", type=["json"], key="import_uploader")
    if uploaded is not None and not st.session_state["import_done"]:
        try:
            raw = uploaded.read().decode("utf-8")
            payload = json.loads(raw)
            merge = "Merge" in import_mode
            v_imported, c_imported = storage.import_json(payload, merge=merge)
            st.success(f"Import complete: {v_imported} videos, {c_imported} collections {'added' if merge else 'replaced'}.")
            st.session_state["import_done"] = True
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    if st.session_state["import_done"]:
        st.button("Clear import state", key="clear_import", on_click=_cb_clear_import)

    st.divider()

    st.subheader("⬆️ Update yt-dlp")
    if st.button("Check and update yt-dlp", key="update_ytdlp", type="primary"):
        with st.spinner("Updating yt-dlp…"):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    st.success("yt-dlp updated successfully.")
                else:
                    st.error(f"Update failed:\n{result.stderr}")
            except subprocess.TimeoutExpired:
                st.error("Update timed out.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.divider()

    st.subheader("💾 Storage")
    st.caption(f"Data file: `{storage.get_storage_path()}`")
    st.caption(f"File size: {storage.get_storage_size()}")
    st.caption(f"Total videos: {len(videos)}")
    st.caption(f"Total collections: {len(colls)}")


# ── Main ──

def main() -> None:
    init_state()
    render_sidebar()

    page = st.session_state["page"]
    if page == "📊 Dashboard":
        page_dashboard()
    elif page == "➕ Add Video":
        page_add_video()
    elif page == "📚 Library":
        page_library()
    elif page == "🗂 Collections":
        page_collections()
    elif page == "⚙️ Settings":
        page_settings()


if __name__ == "__main__":
    main()
