"""YouTube Learning Tracker — Streamlit web app."""

import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ─── Path & env setup (must come before any local imports) ──────────────────
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from models.video import Video, WatchStatus

# ─── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init services ───────────────────────────────────────────────────────
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


# ╔════════════════════════════════════════════════════════════════════════╗
# ║  COMPONENT FUNCTIONS — defined BEFORE any page render calls           ║
# ╚════════════════════════════════════════════════════════════════════════╝

def _render_video_detail(video: Video, store: Storage) -> None:
    """Render full video detail in an expander."""
    with st.expander(f"📺 {video.title}", expanded=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, use_container_width=True)
        with col2:
            st.markdown(f"**Channel:** {video.channel}")
            st.markdown(f"**Duration:** {video.duration}")
            published = (video.published_at or "")[:10]
            st.markdown(f"**Published:** {published}")
            st.markdown(f"**[Watch on YouTube]({video.url})**")

        tabs = st.tabs(["📝 Summary", "🗒️ Notes", "📄 Transcript", "❓ Ask"])

        with tabs[0]:  # Summary
            if video.summary_bullets:
                for b in video.summary_bullets:
                    st.markdown(f"• {b}")
            if video.summary_paragraph:
                st.info(video.summary_paragraph)
            if not video.summary_bullets and not video.summary_paragraph:
                if video.transcript_text:
                    if st.button("✨ Generate Summary", key=f"gen_sum_{video.video_id}"):
                        with st.spinner("Generating..."):
                            bullets, paragraph = summarizer.summarize(
                                video.transcript_text, video.title
                            )
                            video.summary_bullets = bullets
                            video.summary_paragraph = paragraph
                            store.update_video(video)
                        st.rerun()
                else:
                    st.warning("⚠️ Add a transcript first to generate a summary.")

        with tabs[1]:  # Notes
            if video.auto_notes:
                st.markdown("**🤖 Auto Notes:**")
                for n in video.auto_notes:
                    st.markdown(f"• {n}")
                st.divider()
            st.markdown("**✍️ Your Notes:**")
            new_notes = st.text_area(
                "notes",
                value=video.manual_notes or "",
                key=f"notes_{video.video_id}",
                height=150,
                label_visibility="collapsed",
            )
            if st.button("💾 Save Notes", key=f"save_notes_{video.video_id}"):
                video.manual_notes = new_notes
                store.update_video(video)
                st.success("✅ Notes saved.")

        with tabs[2]:  # Transcript
            if video.transcript_text:
                src = video.transcript_source or "unknown"
                st.caption(f"Source: `{src}`")
                st.text_area(
                    "transcript",
                    value=video.transcript_text,
                    height=300,
                    key=f"transcript_{video.video_id}",
                    disabled=True,
                    label_visibility="collapsed",
                )
            else:
                st.info("⚠️ No transcript yet.")
                pasted = st.text_area(
                    "Paste transcript text",
                    height=200,
                    key=f"paste_{video.video_id}",
                )
                if st.button("💾 Save Transcript", key=f"save_trans_{video.video_id}"):
                    if pasted.strip():
                        video.transcript_text = pasted.strip()
                        video.transcript_source = "manual"
                        store.update_video(video)
                        st.success("✅ Transcript saved.")
                        st.rerun()

        with tabs[3]:  # Ask
            if not video.transcript_text:
                st.warning("⚠️ Add a transcript first to ask questions.")
            else:
                question = st.text_input(
                    "Ask a question about this video",
                    placeholder="e.g. What is the main concept explained?",
                    key=f"qa_{video.video_id}",
                )
                if st.button("❓ Ask", key=f"ask_{video.video_id}") and question:
                    with st.spinner("Thinking..."):
                        try:
                            answer = summarizer.answer_question(
                                video.transcript_text, question, video.title
                            )
                            st.markdown(f"**Answer:** {answer}")
                        except Exception as e:
                            st.error(f"Could not answer: {e}")


def _render_video_card(video: Video, store: Storage) -> None:
    """Render a compact video card with status selector and detail toggle."""
    with st.container(border=True):
        if video.thumbnail_url:
            st.image(video.thumbnail_url, use_container_width=True)

        title_display = video.title[:52] + "..." if len(video.title) > 52 else video.title
        st.markdown(f"**{title_display}**")
        st.caption(f"{video.channel} · {video.duration}")

        status_options = [s.value for s in WatchStatus]
        current_index = status_options.index(video.status.value)
        new_status = st.selectbox(
            "Status",
            options=status_options,
            index=current_index,
            key=f"status_{video.video_id}",
            label_visibility="collapsed",
            format_func=lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s.capitalize()}",
        )
        if new_status != video.status.value:
            video.status = WatchStatus(new_status)
            store.update_video(video)
            st.rerun()

        if st.button("📌 View Details", key=f"view_{video.video_id}", use_container_width=True):
            _render_video_detail(video, store)


# ╔════════════════════════════════════════════════════════════════════════╗
# ║  PAGE RENDERS                                                          ║
# ╚════════════════════════════════════════════════════════════════════════╝

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📺 YT Learning Tracker")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "➕ Add Video", "📚 Library", "🔍 Search", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    st.divider()
    counts = storage.count_by_status()
    total = sum(counts.values())
    st.metric("Total Videos", total)
    c1, c2 = st.columns(2)
    c1.metric("🟢 Done", counts.get("completed", 0))
    c2.metric("🟡 Watching", counts.get("watching", 0))


# ─── Dashboard ───────────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    videos = storage.get_all_videos()

    if not videos:
        st.info("👋 No videos saved yet. Go to **➕ Add Video** to get started.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, (status, emoji) in zip(
            [c1, c2, c3, c4, c5],
            [("saved", "🔵"), ("watching", "🟡"), ("completed", "🟢"), ("dropped", "🔴"), ("rewatch", "🟣")],
        ):
            col.metric(f"{emoji} {status.capitalize()}", counts.get(status, 0))

        st.divider()
        st.subheader("🕒 Recent Videos")
        recent = sorted(videos, key=lambda v: v.updated_at, reverse=True)[:6]
        cols = st.columns(3)
        for i, video in enumerate(recent):
            with cols[i % 3]:
                _render_video_card(video, storage)


# ─── Add Video ──────────────────────────────────────────────────────────────
elif page == "➕ Add Video":
    st.title("➕ Add New Video")

    with st.form("add_video_form"):
        url = st.text_input(
            "YouTube URL",
            placeholder="https://www.youtube.com/watch?v=...",
        )
        submitted = st.form_submit_button("Fetch & Save", type="primary")

    if submitted and url:
        # ─ Step 1: Fetch metadata
        with st.spinner("📡 Fetching video info..."):
            try:
                video: Video = fetcher.fetch_video(url)
            except Exception as e:
                st.error(f"❌ Failed to fetch video: {e}")
                st.stop()

        st.success(f"✅ Found: **{video.title}** by {video.channel}")
        col1, col2 = st.columns([1, 2])
        with col1:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, use_container_width=True)
        with col2:
            st.markdown(f"**Channel:** {video.channel}")
            st.markdown(f"**Duration:** {video.duration}")
            published = (video.published_at or "")[:10]
            st.markdown(f"**Published:** {published}")

        # ─ Step 2: Transcript
        with st.spinner("📄 Extracting transcript..."):
            transcript, source = extractor.extract(video.video_id)

        if transcript:
            st.success(f"✅ Transcript extracted via `{source}`")
            video.transcript_text = transcript
            video.transcript_source = source
        else:
            st.warning("⚠️ Auto transcript not available for this video.")
            tab_paste, tab_upload = st.tabs(["Paste Transcript", "Upload .txt File"])
            with tab_paste:
                pasted = st.text_area("Paste transcript text here", height=200)
                if st.button("Use Pasted Text"):
                    text, src = extractor.from_text(pasted)
                    video.transcript_text = text
                    video.transcript_source = src
                    st.success("✅ Transcript saved.")
            with tab_upload:
                uploaded = st.file_uploader("Upload .txt file", type=["txt"])
                if uploaded is not None:
                    raw = uploaded.read().decode("utf-8")
                    text, src = extractor.from_text(raw)
                    video.transcript_text = text
                    video.transcript_source = src
                    st.success("✅ Transcript loaded from file.")

        # ─ Step 3: AI summary + notes
        if video.transcript_text:
            with st.spinner("✨ Generating summary and notes..."):
                try:
                    bullets, paragraph = summarizer.summarize(
                        video.transcript_text, video.title
                    )
                    video.summary_bullets = bullets
                    video.summary_paragraph = paragraph
                    video.auto_notes = notes_gen.generate_auto_notes(
                        video.transcript_text, video.title
                    )
                    st.success("✅ Summary and notes generated.")
                except Exception as e:
                    st.warning(f"⚠️ AI summary skipped (check API key): {e}")

        # ─ Step 4: Save
        storage.save_video(video)
        st.balloons()
        st.success("✅ Video saved to your library! Go to 📚 Library to view it.")


# ─── Library ───────────────────────────────────────────────────────────────
elif page == "📚 Library":
    st.title("📚 Your Library")

    col_f, col_s = st.columns([2, 1])
    with col_f:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "saved", "watching", "completed", "dropped", "rewatch"],
        )
    with col_s:
        sort_by = st.selectbox("Sort by", ["Recently updated", "Title A–Z"])

    if status_filter == "All":
        videos = storage.get_all_videos()
    else:
        videos = storage.filter_by_status(WatchStatus(status_filter))

    if sort_by == "Title A–Z":
        videos = sorted(videos, key=lambda v: v.title.lower())
    else:
        videos = sorted(videos, key=lambda v: v.updated_at, reverse=True)

    if not videos:
        st.info("📦 No videos found for this filter.")
    else:
        st.caption(f"{len(videos)} video(s)")
        cols = st.columns(3)
        for i, video in enumerate(videos):
            with cols[i % 3]:
                _render_video_card(video, storage)


# ─── Search ────────────────────────────────────────────────────────────────
elif page == "🔍 Search":
    st.title("🔍 Search Library")
    query = st.text_input(
        "Search by title, channel, tags, or notes",
        placeholder="e.g. Python, React, machine learning",
    )
    if query:
        results = storage.search_videos(query)
        st.write(f"**{len(results)} result(s)** for `{query}`")
        if results:
            cols = st.columns(3)
            for i, video in enumerate(results):
                with cols[i % 3]:
                    _render_video_card(video, storage)
        else:
            st.info("🔍 No results found. Try a different keyword.")


# ─── Settings ──────────────────────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.info("🔑 API keys are loaded from `.env` file. They are gitignored and never uploaded.")

    yt_key = os.getenv("YOUTUBE_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    ai_provider = os.getenv("AI_PROVIDER", "groq")

    st.subheader("📊 Current Configuration")
    st.write(f"🔑 **YouTube API Key:** {'✅ Set' if yt_key else '❌ Not set — video metadata will not load'}")
    st.write(f"🤖 **AI Provider:** `{ai_provider}`")
    st.write(f"🔑 **Groq API Key:** {'✅ Set' if groq_key else '❌ Not set'}")
    st.write(f"🔑 **OpenAI API Key:** {'✅ Set' if openai_key else '➖ Not set (optional)'}")
    st.write(f"💾 **Storage file:** `{storage_path}`")
    st.write(f"📊 **Total videos saved:** {sum(storage.count_by_status().values())}")

    st.divider()
    st.subheader("🔗 Get Free API Keys")
    st.markdown("""
    | Service | Link | Notes |
    |---|---|---|
    | YouTube Data API v3 | [console.cloud.google.com](https://console.cloud.google.com) | Free 10,000 units/day |
    | Groq (recommended) | [console.groq.com](https://console.groq.com) | Free, no credit card |
    | OpenAI (optional) | [platform.openai.com](https://platform.openai.com) | Paid |
    """)

    st.divider()
    st.subheader("⚠️ Danger Zone")
    st.warning("This will permanently delete all saved videos from your local library.")
    if st.button("🗑️ Clear All Data", type="secondary"):
        confirm = st.checkbox("Yes, I understand this cannot be undone")
        if confirm:
            for v in storage.get_all_videos():
                storage.delete_video(v.video_id)
            st.success("🗑️ Library cleared.")
            st.rerun()
