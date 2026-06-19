"""YouTube Learning Tracker — Streamlit web app."""

import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from models.video import Video, WatchStatus

st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init ───────────────────────────────────────────────
storage_path = os.getenv("STORAGE_PATH", str(root / "data" / "videos.json"))
storage = Storage(storage_path)
fetcher = YouTubeFetcher()
extractor = TranscriptExtractor()
summarizer = Summarizer()
notes_gen = NotesGenerator()

STATUS_COLORS = {
    "saved": "🔵",
    "watching": "🟡",
    "completed": "🟢",
    "dropped": "🔴",
    "rewatch": "🟣",
}

# ─── Sidebar ────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📺 YT Learning Tracker")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "➕ Add Video", "📚 Library", "🔍 Search", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    st.divider()
    counts = storage.count_by_status()
    total = sum(counts.values())
    st.metric("Total Videos", total)
    cols = st.columns(2)
    cols[0].metric("Completed", counts.get("completed", 0))
    cols[1].metric("Watching", counts.get("watching", 0))


# ─── Dashboard ──────────────────────────────────────────
if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    videos = storage.get_all_videos()

    if not videos:
        st.info("No videos saved yet. Go to **➕ Add Video** to get started.")
    else:
        # Stats row
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, (status, emoji) in zip(
            [c1, c2, c3, c4, c5],
            [("saved", "🔵"), ("watching", "🟡"), ("completed", "🟢"), ("dropped", "🔴"), ("rewatch", "🟣")]
        ):
            col.metric(f"{emoji} {status.capitalize()}", counts.get(status, 0))

        st.divider()
        st.subheader("Recent Videos")
        recent = sorted(videos, key=lambda v: v.updated_at, reverse=True)[:6]
        cols = st.columns(3)
        for i, video in enumerate(recent):
            with cols[i % 3]:
                _render_video_card(video, storage)


# ─── Add Video ──────────────────────────────────────────
elif page == "➕ Add Video":
    st.title("➕ Add New Video")
    with st.form("add_video_form"):
        url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        submitted = st.form_submit_button("Save Video", type="primary")

    if submitted and url:
        with st.spinner("Fetching video info..."):
            try:
                video = fetcher.fetch_video(url)
            except Exception as e:
                st.error(f"Failed to fetch video: {e}")
                st.stop()

        st.success(f"✅ Found: **{video.title}** by {video.channel}")
        col1, col2 = st.columns([1, 2])
        with col1:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, use_column_width=True)
        with col2:
            st.markdown(f"**Channel:** {video.channel}")
            st.markdown(f"**Duration:** {video.duration}")
            st.markdown(f"**Published:** {video.published_at[:10]}")

        with st.spinner("Extracting transcript..."):
            transcript, source = extractor.extract(video.video_id)

        if transcript:
            st.success(f"✅ Transcript extracted ({source})")
            video.transcript_text = transcript
            video.transcript_source = source
        else:
            st.warning("⚠️ Auto transcript not available.")
            tab_paste, tab_upload = st.tabs(["Paste Transcript", "Upload .txt File"])
            with tab_paste:
                pasted = st.text_area("Paste transcript text here", height=200)
                if st.button("Use Pasted Text"):
                    video.transcript_text, video.transcript_source = extractor.from_text(pasted)
                    st.success("✅ Transcript saved.")
            with tab_upload:
                uploaded = st.file_uploader("Upload .txt file", type=["txt"])
                if uploaded:
                    text = uploaded.read().decode("utf-8")
                    video.transcript_text, video.transcript_source = extractor.from_text(text)
                    st.success("✅ Transcript loaded from file.")

        if video.transcript_text:
            with st.spinner("Generating summary and notes..."):
                bullets, paragraph = summarizer.summarize(video.transcript_text, video.title)
                video.summary_bullets = bullets
                video.summary_paragraph = paragraph
                video.auto_notes = notes_gen.generate_auto_notes(video.transcript_text, video.title)
            st.success("✅ Summary and notes generated.")

        storage.save_video(video)
        st.balloons()
        st.success(f"✅ Video saved to your library!")


# ─── Library ────────────────────────────────────────────
elif page == "📚 Library":
    st.title("📚 Your Library")
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "saved", "watching", "completed", "dropped", "rewatch"]
    )
    if status_filter == "All":
        videos = storage.get_all_videos()
    else:
        videos = storage.filter_by_status(WatchStatus(status_filter))

    if not videos:
        st.info("No videos found.")
    else:
        cols = st.columns(3)
        for i, video in enumerate(sorted(videos, key=lambda v: v.updated_at, reverse=True)):
            with cols[i % 3]:
                _render_video_card(video, storage)


# ─── Search ─────────────────────────────────────────────
elif page == "🔍 Search":
    st.title("🔍 Search Library")
    query = st.text_input("Search by title, channel, or notes", placeholder="e.g. Python, React, machine learning")
    if query:
        results = storage.search_videos(query)
        st.write(f"**{len(results)} result(s)** for '{query}'")
        if results:
            cols = st.columns(3)
            for i, video in enumerate(results):
                with cols[i % 3]:
                    _render_video_card(video, storage)
        else:
            st.info("No results found.")


# ─── Settings ───────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.info("API keys are loaded from `.env` file or Streamlit secrets.")

    st.subheader("Current Configuration")
    yt_key = os.getenv("YOUTUBE_API_KEY", "")
    ai_key = os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("OPENAI_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    ai_provider = os.getenv("AI_PROVIDER", "none")

    st.write(f"🔑 **YouTube API Key:** {'✅ Set' if yt_key else '❌ Not set'}")
    st.write(f"🤖 **AI Provider:** `{ai_provider}`")
    st.write(f"🔑 **AI API Key:** {'✅ Set' if ai_key else '❌ Not set'}")
    st.write(f"💾 **Storage Path:** `{storage_path}`")

    st.subheader("Get API Keys")
    st.markdown("""
    - **YouTube API Key:** [console.cloud.google.com](https://console.cloud.google.com) → Enable *YouTube Data API v3*
    - **Groq (Free):** [console.groq.com](https://console.groq.com) — Free tier, fastest
    - **Anthropic:** [console.anthropic.com](https://console.anthropic.com)
    - **OpenAI:** [platform.openai.com](https://platform.openai.com)
    """)


# ─── Video Card Component ────────────────────────────────
def _render_video_card(video: Video, storage: Storage):
    """Render a video card with details and status controls."""
    with st.container(border=True):
        if video.thumbnail_url:
            st.image(video.thumbnail_url, use_column_width=True)
        st.markdown(f"**{video.title[:50]}{'...' if len(video.title) > 50 else ''}**")
        st.caption(f"{video.channel} · {video.duration}")

        status_emoji = STATUS_COLORS.get(video.status.value, "⚪")
        new_status = st.selectbox(
            "Status",
            options=[s.value for s in WatchStatus],
            index=[s.value for s in WatchStatus].index(video.status.value),
            key=f"status_{video.video_id}",
            label_visibility="collapsed"
        )
        if new_status != video.status.value:
            video.status = WatchStatus(new_status)
            storage.update_video(video)
            st.rerun()

        if st.button("View Details", key=f"view_{video.video_id}", use_container_width=True):
            st.session_state["selected_video"] = video.video_id
            _render_video_detail(video, storage)


def _render_video_detail(video: Video, storage: Storage):
    """Render full video detail in an expander."""
    with st.expander(f"📺 {video.title}", expanded=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, use_column_width=True)
        with col2:
            st.markdown(f"**Channel:** {video.channel}")
            st.markdown(f"**Duration:** {video.duration}")
            st.markdown(f"**Published:** {video.published_at[:10]}")
            st.markdown(f"**[Watch on YouTube]({video.url})**")

        tabs = st.tabs(["📝 Summary", "🗒️ Notes", "📄 Transcript"])

        with tabs[0]:
            if video.summary_bullets:
                for b in video.summary_bullets:
                    st.markdown(f"• {b}")
            if video.summary_paragraph:
                st.info(video.summary_paragraph)
            elif not video.transcript_text:
                st.warning("Add a transcript first to generate a summary.")

        with tabs[1]:
            if video.auto_notes:
                st.markdown("**Auto Notes:**")
                for n in video.auto_notes:
                    st.markdown(f"• {n}")
            st.markdown("**Manual Notes:**")
            new_notes = st.text_area(
                "Your notes",
                value=video.manual_notes,
                key=f"notes_{video.video_id}",
                height=150
            )
            if st.button("Save Notes", key=f"save_notes_{video.video_id}"):
                video.manual_notes = new_notes
                storage.update_video(video)
                st.success("✅ Notes saved.")

        with tabs[2]:
            if video.transcript_text:
                st.text_area(
                    "Transcript",
                    value=video.transcript_text,
                    height=300,
                    key=f"transcript_{video.video_id}",
                    disabled=True
                )
            else:
                pasted = st.text_area("Paste transcript text", height=200, key=f"paste_{video.video_id}")
                if st.button("Save Transcript", key=f"save_trans_{video.video_id}"):
                    video.transcript_text = pasted.strip()
                    video.transcript_source = "manual"
                    storage.update_video(video)
                    st.success("✅ Transcript saved.")
