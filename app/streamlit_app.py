"""YouTube Learning Tracker — Streamlit web app."""

import streamlit as st  # type: ignore[import-untyped]
import os
import sys
from pathlib import Path
from dotenv import load_dotenv  # type: ignore[import-untyped]

# ─── Path & env setup ───────────────────────────────────────────────────────────────────
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from models.video import Video, WatchStatus

# ─── Page config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init services ────────────────────────────────────────────────────────────────────
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
# ║  COMPONENT FUNCTIONS                                                     ║
# ╚════════════════════════════════════════════════════════════════════════╝

def _render_video_detail(video: Video, store: Storage) -> None:
    """Render full video detail in an expander."""
    vid = video.video_id

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

        # ─ Summary tab ──────────────────────────────────────────────────────────────────
        with tabs[0]:
            if video.summary_bullets:
                for b in video.summary_bullets:
                    st.markdown(f"• {b}")
            if video.summary_paragraph:
                st.info(video.summary_paragraph)
            if not video.summary_bullets and not video.summary_paragraph:
                if video.transcript_text:
                    if st.button("✨ Generate Summary", key=f"gen_sum_{vid}"):
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

        # ─ Notes tab ──────────────────────────────────────────────────────────────────
        with tabs[1]:
            if video.auto_notes:
                st.markdown("⁠**🤖 Auto Notes:**")
                for n in video.auto_notes:
                    st.markdown(f"• {n}")
                st.divider()
            st.markdown("⁠**✍️ Your Notes:**")
            new_notes = st.text_area(
                "notes",
                value=video.manual_notes or "",
                key=f"notes_{vid}",
                height=150,
                label_visibility="collapsed",
            )
            if st.button("💾 Save Notes", key=f"save_notes_{vid}"):
                video.manual_notes = new_notes
                store.update_video(video)
                st.success("✅ Notes saved.")

        # ─ Transcript tab ───────────────────────────────────────────────────────────
        with tabs[2]:
            if video.transcript_text:
                src = video.transcript_source or "unknown"
                st.caption(f"Source: `{src}`")
                st.text_area(
                    "transcript",
                    value=video.transcript_text,
                    height=300,
                    key=f"transcript_{vid}",
                    disabled=True,
                    label_visibility="collapsed",
                )
            else:
                st.info("⚠️ No transcript yet. Paste it below or upload a .txt file.")
                paste_key   = f"paste_{vid}"
                col_p, col_u = st.columns(2)
                with col_p:
                    pasted = st.text_area(
                        "Paste transcript text here",
                        height=200,
                        key=paste_key,
                    )
                    if st.button("💾 Save Pasted Transcript", key=f"save_paste_{vid}"):
                        text = pasted.strip()
                        if text:
                            video.transcript_text = text
                            video.transcript_source = "manual"
                            store.update_video(video)
                            st.success("✅ Transcript saved!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Please paste some text first.")
                with col_u:
                    uploaded = st.file_uploader(
                        "Or upload a .txt file",
                        type=["txt"],
                        key=f"upload_{vid}",
                    )
                    if uploaded is not None:
                        raw = uploaded.read().decode("utf-8")
                        if st.button("💾 Save Uploaded Transcript", key=f"save_upload_{vid}"):
                            if raw.strip():
                                video.transcript_text = raw.strip()
                                video.transcript_source = "upload"
                                store.update_video(video)
                                st.success("✅ Transcript saved from file!")
                                st.rerun()

        # ─ Ask tab ──────────────────────────────────────────────────────────────────────
        with tabs[3]:
            if not video.transcript_text:
                st.warning("⚠️ Add a transcript first to ask questions.")
            else:
                answer_key = f"qa_answer_{vid}"
                if answer_key not in st.session_state:
                    st.session_state[answer_key] = ""

                question = st.text_input(
                    "Ask a question about this video",
                    placeholder="e.g. What is the main concept explained?",
                    key=f"qa_input_{vid}",
                )
                if st.button("❓ Ask", key=f"ask_btn_{vid}"):
                    if question.strip():
                        with st.spinner("Thinking..."):
                            try:
                                answer = summarizer.answer_question(
                                    video.transcript_text, question, video.title
                                )
                                st.session_state[answer_key] = answer
                            except Exception as e:
                                st.session_state[answer_key] = f"Error: {e}"
                    else:
                        st.warning("⚠️ Please type a question first.")

                if st.session_state[answer_key]:
                    st.markdown("**💡 Answer:**")
                    st.success(st.session_state[answer_key])
                    if st.button("🗑️ Clear answer", key=f"clear_ans_{vid}"):
                        st.session_state[answer_key] = ""
                        st.rerun()


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
# ║  PAGE RENDERS                                                            ║
# ╚════════════════════════════════════════════════════════════════════════╝

# ─ Sidebar ──────────────────────────────────────────────────────────────────────────
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


# ─ Dashboard ───────────────────────────────────────────────────────────────────────
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


# ─ Add Video ──────────────────────────────────────────────────────────────────────
elif page == "➕ Add Video":
    st.title("➕ Add New Video")

    # — Step 1: URL input form —
    with st.form("add_video_form"):
        url = st.text_input(
            "YouTube URL",
            placeholder="https://www.youtube.com/watch?v=...",
        )
        submitted = st.form_submit_button("Fetch & Save", type="primary")

    # Persist fetched video across reruns using session_state.
    # After form submit, video data is stored in session_state["pending_video"].
    # Subsequent button clicks (paste/upload) keep the data alive without re-fetching.
    if submitted and url:
        with st.spinner("📡 Fetching video info..."):
            try:
                fetched = fetcher.fetch_video(url)
            except Exception as e:
                st.error(f"❌ Failed to fetch video: {e}")
                st.stop()

        if fetched is None:
            st.error("❌ Could not retrieve video info. Check the URL and your YouTube API key.")
            st.stop()

        st.session_state["pending_video"] = fetched
        st.session_state["pending_transcript_done"] = False

    # Render the pending-video workflow if one is in session
    if "pending_video" in st.session_state and not st.session_state.get("pending_transcript_done"):
        video: Video = st.session_state["pending_video"]

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

        # Auto-extract transcript only once
        if not video.transcript_text:
            with st.spinner("📄 Extracting transcript..."):
                transcript, source = extractor.extract(video.video_id)
            if transcript:
                video.transcript_text = transcript
                video.transcript_source = source
                st.session_state["pending_video"] = video
                st.success(f"✅ Transcript extracted via `{source}` with timestamps")

        if video.transcript_text:
            # Already have a transcript — go straight to save
            _finish_add_video(video, storage, summarizer, notes_gen, extractor)
        else:
            # No auto transcript — show manual input, persisted across reruns
            st.warning("⚠️ Auto transcript not available. Paste or upload below.")
            paste_tab, upload_tab = st.tabs(["Paste Transcript", "Upload .txt File"])

            with paste_tab:
                pasted = st.text_area("Paste transcript text here", height=200, key="add_paste")
                if st.button("💾 Use Pasted Text", key="add_paste_btn"):
                    text, src = extractor.from_text(pasted)
                    if text:
                        video.transcript_text = text
                        video.transcript_source = src
                        st.session_state["pending_video"] = video
                        st.rerun()
                    else:
                        st.warning("⚠️ Nothing to save — paste is empty.")

            with upload_tab:
                uploaded = st.file_uploader("Upload .txt file", type=["txt"], key="add_upload")
                if uploaded is not None:
                    raw = uploaded.read().decode("utf-8")
                    if raw.strip():
                        video.transcript_text = raw.strip()
                        video.transcript_source = "upload"
                        st.session_state["pending_video"] = video
                        st.rerun()


def _finish_add_video(
    video: Video,
    store: Storage,
    summ: Summarizer,
    ng: NotesGenerator,
    ext: TranscriptExtractor,
) -> None:
    """Generate summary + notes, save, and clean up session state."""
    with st.spinner("✨ Generating summary and notes..."):
        try:
            bullets, paragraph = summ.summarize(video.transcript_text, video.title)
            video.summary_bullets = bullets
            video.summary_paragraph = paragraph
            video.auto_notes = ng.generate_auto_notes(video.transcript_text, video.title)
            st.success("✅ Summary and notes generated.")
        except Exception as e:
            st.warning(f"⚠️ AI summary skipped (check API key): {e}")

    store.save_video(video)
    st.session_state.pop("pending_video", None)
    st.session_state["pending_transcript_done"] = True
    st.balloons()
    st.success("✅ Video saved to your library! Go to 📚 Library to view it.")


# ─ Library ──────────────────────────────────────────────────────────────────────────
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


# ─ Search ──────────────────────────────────────────────────────────────────────────
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


# ─ Settings ──────────────────────────────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.info("🔑 API keys are loaded from `.env` file. They are gitignored and never uploaded.")

    yt_key      = os.getenv("YOUTUBE_API_KEY", "")
    groq_key    = os.getenv("GROQ_API_KEY", "")
    openai_key  = os.getenv("OPENAI_API_KEY", "")
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
    st.warning("🗑️ This will permanently delete all saved videos from your local library.")

    if "clear_armed" not in st.session_state:
        st.session_state["clear_armed"] = False

    if not st.session_state["clear_armed"]:
        if st.button("🗑️ Clear All Data", type="secondary"):
            st.session_state["clear_armed"] = True
            st.rerun()
    else:
        st.error("⚠️ Are you sure? This cannot be undone.")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Yes, delete everything", type="primary"):
                for v in storage.get_all_videos():
                    storage.delete_video(v.video_id)
                st.session_state["clear_armed"] = False
                st.success("🗑️ Library cleared.")
                st.rerun()
        with col_no:
            if st.button("❌ Cancel"):
                st.session_state["clear_armed"] = False
                st.rerun()
