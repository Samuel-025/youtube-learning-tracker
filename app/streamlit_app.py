import json
import os
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv  # type: ignore[import-untyped]

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.settings_store import SettingsStore
from core.exporters import export_csv, export_markdown_library, export_video_json
from core.youtube_fetcher import YouTubeFetcher, extract_video_id
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from models.video import Video, WatchStatus
from models.collection import Collection

st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

storage_path = os.getenv("STORAGE_PATH", str(root / "data" / "videos.json"))
settings_path = str(root / "data" / "settings.json")
storage = Storage(storage_path)
settings = SettingsStore(settings_path)
fetcher = YouTubeFetcher()
extractor = TranscriptExtractor()
summarizer = Summarizer()
notes_gen = NotesGenerator()

PAGES = ["📊 Dashboard", "➕ Add Video", "📚 Library", "🗂 Collections", "⚙️ Settings"]

def init_state() -> None:
    st.session_state.setdefault("page", "📊 Dashboard")
    st.session_state.setdefault("sidebar_nav", "📊 Dashboard")
    st.session_state.setdefault("detail_video_id", None)
    st.session_state.setdefault("pending_video", None)

def go(page: str, video_id: str | None = None) -> None:
    st.session_state["page"] = page
    st.session_state["sidebar_nav"] = page
    st.session_state["detail_video_id"] = video_id
    st.rerun()

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
        except Exception:
            pass
        try:
            video.auto_notes = notes_gen.generate_auto_notes(video.transcript_text, video.title)
        except Exception:
            pass
    storage.save_video(video)

def render_sidebar() -> None:
    with st.sidebar:
        st.title("📺 YouTube Tracker")
        page = st.radio("Navigate", PAGES, key="sidebar_nav")
        if page != st.session_state["page"]:
            st.session_state["page"] = page
            st.session_state["detail_video_id"] = None
            st.rerun()

def page_dashboard() -> None:
    st.title("📊 Dashboard")
    videos = all_videos()
    collections = all_collections()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos", len(videos))
    c2.metric("Collections", len(collections))
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
            st.markdown(f"**{video.title}**")
            st.caption(f"{video.channel} • {video.duration} • {video.status.value}")
        with cols[2]:
            if st.button("View", key=f"dash_view_{video.video_id}"):
                go("📚 Library", video.video_id)

def page_add_video() -> None:
    st.title("➕ Add Video")

    url = st.text_input("YouTube URL")
    fetch_clicked = st.button("Fetch video", type="primary")

    if fetch_clicked:
        try:
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

    transcript_text = video.transcript_text
    transcript_source = video.transcript_source

    if transcript_mode == "Auto-fetch":
        if st.button("Fetch transcript", key="fetch_transcript"):
            try:
                vid = extract_video_id(video.url) or video.video_id
                transcript_text, transcript_source = extractor.extract(vid)
                if transcript_text:
                    st.success(f"Transcript fetched via {transcript_source}.")
                else:
                    st.warning("No transcript found.")
            except Exception as exc:
                st.error(f"Transcript fetch failed: {exc}")

    elif transcript_mode == "Paste manually":
        transcript_text = st.text_area("Paste transcript", value=transcript_text, height=220)
        transcript_source = "manual" if transcript_text.strip() else transcript_source

    tags_raw = st.text_input("Tags (comma-separated)")
    manual_notes = st.text_area("Manual notes", value=video.manual_notes, height=140)

    if st.button("Save video", key="save_video", type="primary"):
        video.transcript_text = transcript_text.strip()
        video.transcript_source = transcript_source
        video.manual_notes = manual_notes.strip()
        video.tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        try:
            save_video_and_enrich(video)
            st.session_state["pending_video"] = None
            st.success("Video saved.")
            go("📚 Library", video.video_id)
        except Exception as exc:
            st.error(f"Could not save video: {exc}")

def render_video_detail(video: Video) -> None:
    st.subheader(video.title)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.write(f"**Channel:** {video.channel}")
        st.write(f"**URL:** {video.url}")
        st.write(f"**Duration:** {video.duration}")
        st.write(f"**Status:** {video.status.value}")
        st.write(f"**Transcript source:** {video.transcript_source or 'N/A'}")
    with c2:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, use_container_width=True)

    status = st.selectbox(
        "Status",
        [s.value for s in WatchStatus],
        index=[s.value for s in WatchStatus].index(video.status.value),
        key=f"status_{video.video_id}",
    )
    notes = st.text_area("Manual notes", value=video.manual_notes, height=180, key=f"notes_{video.video_id}")

    if st.button("Update video", key=f"update_{video.video_id}", type="primary"):
        video.status = WatchStatus(status)
        video.manual_notes = notes
        video.updated_at = datetime.now().isoformat()
        storage.update_video(video)
        st.success("Updated.")
        st.rerun()

    if video.summary_paragraph:
        st.markdown("### Summary")
        st.write(video.summary_paragraph)

    if video.summary_bullets:
        st.markdown("### Key takeaways")
        for bullet in video.summary_bullets:
            st.markdown(f"- {bullet}")

    if video.transcript_text:
        st.markdown("### Transcript")
        st.text_area("Transcript", value=video.transcript_text, height=260, disabled=True)

def page_library() -> None:
    st.title("📚 Library")
    videos = all_videos()
    if not videos:
        st.info("No videos in library yet.")
        return

    query = st.text_input("Search videos")
    status_filter = st.selectbox("Filter by status", ["All"] + [s.value for s in WatchStatus])

    filtered = videos
    if query.strip():
        q = query.lower().strip()
        filtered = [v for v in filtered if q in v.title.lower() or q in v.channel.lower() or q in " ".join(v.tags).lower()]
    if status_filter != "All":
        filtered = [v for v in filtered if v.status.value == status_filter]

    detail_id = st.session_state.get("detail_video_id")
    if detail_id:
        video = storage.get_video(detail_id)
        if video:
            if st.button("← Back to Library"):
                st.session_state["detail_video_id"] = None
                st.rerun()
            render_video_detail(video)
            st.divider()

    for video in filtered:
        cols = st.columns([1, 4, 1])
        with cols[0]:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, use_container_width=True)
        with cols[1]:
            st.markdown(f"**{video.title}**")
            st.caption(f"{video.channel} • {video.duration} • {video.status.value}")
        with cols[2]:
            if st.button("📌 View Details", key=f"lib_view_{video.video_id}"):
                st.session_state["detail_video_id"] = video.video_id
                st.rerun()

def page_collections() -> None:
    st.title("🗂 Collections")
    videos = all_videos()
    collections = all_collections()

    with st.expander("Create collection"):
        name = st.text_input("Collection name")
        description = st.text_input("Description")
        if st.button("Create collection", key="create_collection"):
            if not name.strip():
                st.error("Collection name is required.")
            else:
                coll = Collection(name=name.strip(), description=description.strip())
                storage.save_collection(coll)
                st.success("Collection created.")
                st.rerun()

    if not collections:
        st.info("No collections yet.")
        return

    for coll in collections:
        st.subheader(f"{coll.emoji} {coll.name}")
        if coll.description:
            st.caption(coll.description)

        selected = st.multiselect(
            f"Add videos to {coll.name}",
            options=[v.video_id for v in videos],
            default=coll.video_ids,
            format_func=lambda vid: next((v.title for v in videos if v.video_id == vid), vid),
            key=f"coll_{coll.id}",
        )
        if st.button("Save collection changes", key=f"save_coll_{coll.id}"):
            coll.video_ids = selected
            coll.update_timestamp()
            storage.update_collection(coll)
            st.success("Collection updated.")
            st.rerun()

def page_settings() -> None:
    st.title("⚙️ Settings")
    videos = all_videos()

    csv_data = export_csv(videos)
    st.download_button("Export CSV", csv_data, file_name="youtube_tracker.csv", mime="text/csv")

    export_json_data = json.dumps(storage.export_json(), indent=2, ensure_ascii=False)
    st.download_button("Export JSON", export_json_data, file_name="youtube_tracker.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        try:
            raw = uploaded.read().decode("utf-8")
            storage.import_json(json.loads(raw))
            st.success("Import complete.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")

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