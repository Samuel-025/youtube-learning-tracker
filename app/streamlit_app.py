"""YouTube Learning Tracker — Streamlit web app."""

import streamlit as st  # type: ignore[import-untyped]
import os
import sys
from pathlib import Path
from dotenv import load_dotenv  # type: ignore[import-untyped]

# ─── Path & env setup
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from core.downloader import Downloader, ffmpeg_version
from models.video import Video, WatchStatus

# ─── Page config
st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init services
storage_path = os.getenv("STORAGE_PATH", str(root / "data" / "videos.json"))
storage    = Storage(storage_path)
fetcher    = YouTubeFetcher()
extractor  = TranscriptExtractor()
summarizer = Summarizer()
notes_gen  = NotesGenerator()
downloader = Downloader(str(root / "downloads"))

STATUS_COLORS = {
    "saved":     "🔵",
    "watching":  "🟡",
    "completed": "🟢",
    "dropped":   "🔴",
    "rewatch":   "🟣",
}

DOWNLOAD_MODES = {
    "🎧 Audio only (MP3 192k)": "audio",
    "📹 Video 720p (MP4)": "video_720",
    "📹 Video 1080p (MP4)": "video_1080",
    "📹 Video Best quality (MP4)": "video_best",
}


# ╔══════════════════════════════════════════════════════
# ║  HELPERS
# ╚══════════════════════════════════════════════════════

def _finish_add_video(video: Video) -> None:
    with st.spinner("✨ Generating summary and notes..."):
        try:
            bullets, paragraph = summarizer.summarize(video.transcript_text, video.title)
            video.summary_bullets   = bullets
            video.summary_paragraph = paragraph
            video.auto_notes = notes_gen.generate_auto_notes(video.transcript_text, video.title)
            st.success("✅ Summary and notes generated.")
        except Exception as exc:
            st.warning(f"⚠️ AI summary skipped: {exc}")
    storage.save_video(video)
    st.session_state.pop("pending_video", None)
    st.session_state["pending_transcript_done"] = True
    st.balloons()
    st.success("✅ Video saved! Go to 📚 Library to view it.")


def _render_download_tab(video: Video) -> None:
    """Download tab: audio or video via yt-dlp."""
    vid     = video.video_id
    has_ff  = downloader.has_ffmpeg()
    ff_ver  = ffmpeg_version()

    if not downloader.is_available():
        st.error("❌ yt-dlp not found.")
        st.code("py -3.11 -m pip install yt-dlp")
        return

    # ── FFmpeg status banner
    if has_ff:
        st.success(f"✅ FFmpeg detected — `{ff_ver.split('Copyright')[0].strip()}`  — all formats available.")
    else:
        st.warning(
            "⚠️ **FFmpeg not found on PATH.**\n\n"
            "Without FFmpeg:\n"
            "- Audio → downloads as **.m4a** (has audio, no conversion)\n"
            "- Video → downloads as **progressive MP4** (audio + video in one file, max ~720p)\n"
            "- 1080p and Best modes fall back to 720p\n\n"
            "To enable MP3 + full HD: install FFmpeg with `winget install --id Gyan.FFmpeg -e` then restart."
        )

    st.markdown("### ⬇️ Download")
    st.caption(f"Saved to: `{root / 'downloads'}`")

    # ── Format selector with per-option notes
    mode_labels = list(DOWNLOAD_MODES.keys())
    if not has_ff:
        mode_labels_display = [
            "🎧 Audio only (M4A — no FFmpeg)",
            "📹 Video 720p (MP4 progressive — no FFmpeg)",
            "📹 Video 1080p (falls back to 720p — no FFmpeg)",
            "📹 Video Best (progressive MP4 — no FFmpeg)",
        ]
    else:
        mode_labels_display = mode_labels

    selected_display = st.selectbox(
        "Format",
        options=mode_labels_display,
        key=f"dl_mode_{vid}",
    )
    # Map display label back to mode key
    mode = list(DOWNLOAD_MODES.values())[mode_labels_display.index(selected_display)]

    # ── Show existing download
    if video.local_path and Path(video.local_path).exists():
        st.success(f"✅ Already downloaded: `{Path(video.local_path).name}`")
        with open(video.local_path, "rb") as f:
            file_bytes = f.read()
        fname = Path(video.local_path).name
        mime  = "audio/mpeg" if fname.endswith(".mp3") else (
                "audio/mp4"  if fname.endswith(".m4a") else "video/mp4")
        st.download_button(
            label="📥 Save to computer",
            data=file_bytes,
            file_name=fname,
            mime=mime,
            key=f"dl_save_{vid}",
        )
        st.divider()
        st.caption("Re-download in a different format ↓")

    # ── Download button
    dl_key = f"dl_running_{vid}"
    if dl_key not in st.session_state:
        st.session_state[dl_key] = False

    if st.button("▶️ Start Download", key=f"dl_btn_{vid}", type="primary"):
        st.session_state[dl_key] = True

    if st.session_state[dl_key]:
        label_map = {v: k for k, v in DOWNLOAD_MODES.items()}
        with st.spinner(f"Downloading {label_map.get(mode, mode)} — may take a minute..."):
            try:
                out_path = downloader.download(vid, mode)  # type: ignore[arg-type]
                video.local_path = str(out_path)
                storage.update_video(video)
                st.session_state[dl_key] = False
                st.success(f"✅ Downloaded: `{out_path.name}`")
                with open(out_path, "rb") as f:
                    file_bytes = f.read()
                fname = out_path.name
                mime  = "audio/mpeg" if fname.endswith(".mp3") else (
                        "audio/mp4"  if fname.endswith(".m4a") else "video/mp4")
                st.download_button(
                    label="📥 Save to computer",
                    data=file_bytes,
                    file_name=fname,
                    mime=mime,
                    key=f"dl_save_new_{vid}",
                )
            except RuntimeError as exc:
                st.session_state[dl_key] = False
                st.error(f"❌ Download failed:\n\n{exc}")


def _render_detail_page(video: Video) -> None:
    vid = video.video_id

    if st.button("← Back to Library", key="back_btn"):
        st.session_state.pop("detail_video_id", None)
        st.rerun()

    col1, col2 = st.columns([1, 2])
    with col1:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")
    with col2:
        st.title(video.title)
        st.caption(
            f"📺 {video.channel}  ·  ⏱ {video.duration}  ·  {(video.published_at or '')[:10]}"
        )
        st.markdown(f"🔗 [Watch on YouTube]({video.url})")
        status_options = [s.value for s in WatchStatus]
        new_status = st.selectbox(
            "Status",
            options=status_options,
            index=status_options.index(video.status.value),
            key=f"detail_status_{vid}",
            format_func=lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s.capitalize()}",
        )
        if new_status != video.status.value:
            video.status = WatchStatus(new_status)
            storage.update_video(video)
            st.rerun()

    st.divider()
    tabs = st.tabs(["📝 Summary", "🗒️ Notes", "📄 Transcript", "❓ Ask", "⬇️ Download"])

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
                        video.summary_bullets   = bullets
                        video.summary_paragraph = paragraph
                        storage.update_video(video)
                    st.rerun()
            else:
                st.warning("⚠️ Add a transcript first.")

    with tabs[1]:
        if video.auto_notes:
            st.markdown("**🤖 Auto Notes:**")
            for n in video.auto_notes:
                st.markdown(f"• {n}")
            st.divider()
        st.markdown("**✍️ Your Notes:**")
        new_notes = st.text_area(
            "notes",
            value=video.manual_notes or "",
            key=f"notes_{vid}",
            height=150,
            label_visibility="collapsed",
        )
        if st.button("💾 Save Notes", key=f"save_notes_{vid}"):
            video.manual_notes = new_notes
            storage.update_video(video)
            st.success("✅ Notes saved.")

    with tabs[2]:
        if video.transcript_text:
            st.caption(f"Source: `{video.transcript_source or 'unknown'}`")
            st.text_area(
                "transcript",
                value=video.transcript_text,
                height=350,
                key=f"transcript_{vid}",
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("⚠️ No transcript yet.")
            col_p, col_u = st.columns(2)
            with col_p:
                pasted = st.text_area("Paste transcript", height=200, key=f"paste_{vid}")
                if st.button("💾 Save Pasted", key=f"save_paste_{vid}"):
                    if pasted.strip():
                        video.transcript_text   = pasted.strip()
                        video.transcript_source = "manual"
                        storage.update_video(video)
                        st.success("✅ Saved!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Paste is empty.")
            with col_u:
                up = st.file_uploader("Upload .txt", type=["txt"], key=f"upload_{vid}")
                if up is not None:
                    raw = up.read().decode("utf-8")
                    if st.button("💾 Save File", key=f"save_upload_{vid}"):
                        if raw.strip():
                            video.transcript_text   = raw.strip()
                            video.transcript_source = "upload"
                            storage.update_video(video)
                            st.success("✅ Saved!")
                            st.rerun()

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
            if st.button("🔍 Get Answer", key=f"ask_btn_{vid}", type="primary"):
                q = st.session_state.get(f"qa_input_{vid}", "").strip()
                if q:
                    with st.spinner("🧠 Thinking..."):
                        try:
                            ans = summarizer.answer_question(
                                video.transcript_text, q, video.title
                            )
                            st.session_state[answer_key] = ans
                        except Exception as exc:
                            st.session_state[answer_key] = f"Error: {exc}"
                else:
                    st.warning("⚠️ Type a question first.")
            if st.session_state[answer_key]:
                st.markdown("---")
                st.markdown("**💡 Answer:**")
                st.success(st.session_state[answer_key])
                if st.button("🗑️ Clear", key=f"clear_ans_{vid}"):
                    st.session_state[answer_key] = ""
                    st.rerun()

    with tabs[4]:
        _render_download_tab(video)


def _render_video_card(video: Video) -> None:
    with st.container(border=True):
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")
        title_display = video.title[:52] + "..." if len(video.title) > 52 else video.title
        st.markdown(f"**{title_display}**")
        st.caption(f"{video.channel} · {video.duration}")
        status_options = [s.value for s in WatchStatus]
        new_status = st.selectbox(
            "Status",
            options=status_options,
            index=status_options.index(video.status.value),
            key=f"status_{video.video_id}",
            label_visibility="collapsed",
            format_func=lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s.capitalize()}",
        )
        if new_status != video.status.value:
            video.status = WatchStatus(new_status)
            storage.update_video(video)
            st.rerun()
        if st.button("📌 View Details", key=f"view_{video.video_id}", width="stretch"):
            st.session_state["detail_video_id"] = video.video_id
            st.rerun()


# ╔══════════════════════════════════════════════════════
# ║  PAGE ROUTING
# ╚══════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📺 YT Learning Tracker")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "➕ Add Video", "📚 Library", "🔍 Search", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    if "_last_page" not in st.session_state:
        st.session_state["_last_page"] = page
    if st.session_state["_last_page"] != page:
        st.session_state.pop("detail_video_id", None)
        st.session_state["_last_page"] = page
    st.divider()
    counts = storage.count_by_status()
    total  = sum(counts.values())
    st.metric("Total Videos", total)
    c1, c2 = st.columns(2)
    c1.metric("🟢 Done",     counts.get("completed", 0))
    c2.metric("🟡 Watching", counts.get("watching",  0))


# ── Dashboard
if page == "📊 Dashboard":
    if "detail_video_id" in st.session_state:
        v = storage.get_video(st.session_state["detail_video_id"])
        if v:
            _render_detail_page(v)
            st.stop()
    st.title("📊 Dashboard")
    videos = storage.get_all_videos()
    if not videos:
        st.info("👋 No videos yet. Go to **➕ Add Video** to get started.")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, (status, emoji) in zip(
            [c1, c2, c3, c4, c5],
            [("saved","🔵"),("watching","🟡"),("completed","🟢"),("dropped","🔴"),("rewatch","🟣")],
        ):
            col.metric(f"{emoji} {status.capitalize()}", counts.get(status, 0))
        st.divider()
        st.subheader("🕒 Recent Videos")
        recent = sorted(videos, key=lambda v: v.updated_at, reverse=True)[:6]
        cols = st.columns(3)
        for i, video in enumerate(recent):
            with cols[i % 3]:
                _render_video_card(video)


# ── Add Video
elif page == "➕ Add Video":
    st.title("➕ Add New Video")
    with st.form("add_video_form"):
        url       = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
        submitted = st.form_submit_button("Fetch & Save", type="primary")
    if submitted and url:
        with st.spinner("📡 Fetching video info..."):
            try:
                fetched = fetcher.fetch_video(url)
            except Exception as exc:
                st.error(f"❌ Failed to fetch: {exc}")
                st.stop()
        st.session_state["pending_video"]           = fetched
        st.session_state["pending_transcript_done"] = False
    if "pending_video" in st.session_state and not st.session_state.get("pending_transcript_done"):
        video: Video = st.session_state["pending_video"]
        st.success(f"✅ Found: **{video.title}** by {video.channel}")
        col1, col2 = st.columns([1, 2])
        with col1:
            if video.thumbnail_url:
                st.image(video.thumbnail_url, width="stretch")
        with col2:
            st.markdown(f"**Channel:** {video.channel}")
            st.markdown(f"**Duration:** {video.duration}")
            st.markdown(f"**Published:** {(video.published_at or '')[:10]}")
        if not video.transcript_text:
            with st.spinner("📄 Extracting transcript via yt-dlp..."):
                transcript, source = extractor.extract(video.video_id)
            if transcript:
                video.transcript_text   = transcript
                video.transcript_source = source
                st.session_state["pending_video"] = video
                st.success(f"✅ Transcript extracted via `{source}`")
        if video.transcript_text:
            _finish_add_video(video)
        else:
            st.warning("⚠️ Auto transcript unavailable. Paste or upload below.")
            paste_tab, upload_tab = st.tabs(["Paste Transcript", "Upload .txt"])
            with paste_tab:
                pasted = st.text_area("Paste here", height=200, key="add_paste")
                if st.button("💾 Use Pasted Text", key="add_paste_btn"):
                    t, src = extractor.from_text(pasted)
                    if t:
                        video.transcript_text   = t
                        video.transcript_source = src
                        st.session_state["pending_video"] = video
                        st.rerun()
                    else:
                        st.warning("⚠️ Paste is empty.")
            with upload_tab:
                up = st.file_uploader("Upload .txt", type=["txt"], key="add_upload")
                if up is not None:
                    raw = up.read().decode("utf-8")
                    if raw.strip():
                        video.transcript_text   = raw.strip()
                        video.transcript_source = "upload"
                        st.session_state["pending_video"] = video
                        st.rerun()


# ── Library
elif page == "📚 Library":
    if "detail_video_id" in st.session_state:
        v = storage.get_video(st.session_state["detail_video_id"])
        if v:
            _render_detail_page(v)
            st.stop()
    st.title("📚 Your Library")
    col_f, col_s = st.columns([2, 1])
    with col_f:
        status_filter = st.selectbox(
            "Filter", ["All", "saved", "watching", "completed", "dropped", "rewatch"]
        )
    with col_s:
        sort_by = st.selectbox("Sort", ["Recently updated", "Title A–Z"])
    videos = (
        storage.get_all_videos()
        if status_filter == "All"
        else storage.filter_by_status(WatchStatus(status_filter))
    )
    videos = (
        sorted(videos, key=lambda v: v.title.lower())
        if sort_by == "Title A–Z"
        else sorted(videos, key=lambda v: v.updated_at, reverse=True)
    )
    if not videos:
        st.info("📦 No videos for this filter.")
    else:
        st.caption(f"{len(videos)} video(s)")
        cols = st.columns(3)
        for i, video in enumerate(videos):
            with cols[i % 3]:
                _render_video_card(video)


# ── Search
elif page == "🔍 Search":
    if "detail_video_id" in st.session_state:
        v = storage.get_video(st.session_state["detail_video_id"])
        if v:
            _render_detail_page(v)
            st.stop()
    st.title("🔍 Search Library")
    query = st.text_input(
        "Search by title, channel, notes, or summary",
        placeholder="e.g. Python, React, machine learning",
    )
    if query:
        results = storage.search_videos(query)
        st.write(f"**{len(results)} result(s)** for `{query}`")
        if results:
            cols = st.columns(3)
            for i, video in enumerate(results):
                with cols[i % 3]:
                    _render_video_card(video)
        else:
            st.info("🔍 No results found.")


# ── Settings
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.info("🔑 API keys are loaded from `.env`. They are never uploaded to GitHub.")

    yt_key      = os.getenv("YOUTUBE_API_KEY", "")
    groq_key    = os.getenv("GROQ_API_KEY", "")
    openai_key  = os.getenv("OPENAI_API_KEY", "")
    ai_provider = os.getenv("AI_PROVIDER", "none")

    ff_ver = ffmpeg_version()
    ff_status = f"✅ {ff_ver.split('Copyright')[0].strip()}" if ff_ver else "❌ Not found on PATH"

    try:
        import yt_dlp as _ytdlp
        ytdlp_status = f"✅ {_ytdlp.version.__version__}"
    except ImportError:
        ytdlp_status = "❌ Not installed"

    try:
        import youtube_transcript_api as _yta  # noqa: F401
        yta_status = "✅ Installed"
    except ImportError:
        yta_status = "⚠️ Not installed"

    st.subheader("📊 Current Configuration")
    st.write(f"🔑 **YouTube API Key:** {'✅ Set' if yt_key else '❌ Not set'}")
    st.write(f"🤖 **AI Provider:** `{ai_provider}`")
    st.write(f"🔑 **Groq Key:** {'✅ Set' if groq_key else '❌ Not set'}")
    st.write(f"🔑 **OpenAI Key:** {'✅ Set' if openai_key else '➖ Not set (optional)'}")
    st.write(f"📦 **yt-dlp:** {ytdlp_status}")
    st.write(f"📦 **youtube-transcript-api:** {yta_status}")
    st.write(f"📦 **FFmpeg:** {ff_status}")
    st.write(f"💾 **Storage path:** `{storage_path}`")
    st.write(f"💾 **Storage size:** {storage.get_storage_size()}")
    st.write(f"📊 **Total saved:** {sum(storage.count_by_status().values())}")
    st.write(f"📂 **Downloads folder:** `{root / 'downloads'}`")

    if not ff_ver:
        st.warning(
            "⚠️ FFmpeg not detected. Download feature works in limited mode.\n"
            "Install: `winget install --id Gyan.FFmpeg -e` then restart the app."
        )

    st.divider()
    st.subheader("🔗 Get Free API Keys")
    st.markdown("""
| Service | Link | Notes |
|---|---|---|
| YouTube Data API v3 | [console.cloud.google.com](https://console.cloud.google.com) | Free 10,000 units/day |
| Groq (recommended)  | [console.groq.com](https://console.groq.com) | Free, no credit card |
| OpenAI (optional)   | [platform.openai.com](https://platform.openai.com) | Paid |
    """)

    st.divider()
    st.subheader("⚠️ Danger Zone")
    st.warning("🗑️ Permanently deletes all saved videos.")
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
