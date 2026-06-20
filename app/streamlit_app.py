"""YouTube Learning Tracker — Streamlit web app."""

import re
import streamlit as st  # type: ignore[import-untyped]
import os
import sys
import subprocess
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
from models.collection import Collection

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

# Plotly palette matched to STATUS_COLORS emoji hues
_STATUS_HEX = {
    "saved":     "#4C9BE8",
    "watching":  "#F5C518",
    "completed": "#2ECC71",
    "dropped":   "#E74C3C",
    "rewatch":   "#9B59B6",
}

DOWNLOAD_MODES = {
    "🎧 Audio only (MP3 192k)": "audio",
    "📹 Video 720p (MP4)": "video_720",
    "📹 Video 1080p (MP4)": "video_1080",
    "📹 Video Best quality (MP4)": "video_best",
}

EMOJI_OPTIONS = ["📁", "📚", "🎥", "🧠", "💻", "🔬", "🎨", "🎵", "💼", "🌍", "⭐", "🔥", "💯", "🏆", "🛐"]


# ╔══════════════════════════════════════════════════════
# ║  HELPERS
# ╚══════════════════════════════════════════════════════

def _fmt_seconds(sec: int) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _render_progress_bar(video: Video, compact: bool = False) -> None:
    pct = video.progress_pct
    if video.duration_sec == 0:
        return
    watched_fmt = _fmt_seconds(video.watch_progress_sec)
    total_fmt   = _fmt_seconds(video.duration_sec)
    if compact:
        if pct >= 100:
            st.progress(1.0, text=f"⏱ {total_fmt} / {total_fmt} (100%)")
        elif pct > 0:
            st.progress(pct / 100, text=f"⏱ {watched_fmt} / {total_fmt} ({pct:.0f}%)")
        else:
            st.progress(0.0, text=f"⏱ 0:00 / {total_fmt} (0%)")
    else:
        if pct >= 100:
            st.success(f"✅ Watched fully — {total_fmt}")
        elif pct > 0:
            st.progress(pct / 100, text=f"⏱ {watched_fmt} / {total_fmt}    {pct:.1f}% watched")
        else:
            st.progress(0.0, text=f"⏱ Not started — {total_fmt} total")


def _apply_progress(video: Video, new_sec: int) -> str | None:
    """
    Update watch_progress_sec and auto-transition status.

    Rules
    -----
    • new_sec >= duration  → always set COMPLETED (any prior status)
    • new_sec > 0          → SAVED → WATCHING  (start watching)
    • new_sec == 0         → COMPLETED/WATCHING → SAVED  (reset)
    • dropped / rewatch    → never silently overwritten on partial progress
                             (only overwritten when reaching 100%)

    Returns a celebratory message string when status flips to COMPLETED,
    otherwise None.
    """
    video.watch_progress_sec = new_sec
    celebration: str | None = None

    if new_sec >= video.duration_sec:
        if video.status != WatchStatus.COMPLETED:
            video.status = WatchStatus.COMPLETED
            celebration  = "🎉 Marked as **Completed**!"
    elif new_sec > 0:
        if video.status == WatchStatus.SAVED:
            video.status = WatchStatus.WATCHING
        elif video.status == WatchStatus.COMPLETED:
            video.status = WatchStatus.WATCHING
    else:
        if video.status in (WatchStatus.COMPLETED, WatchStatus.WATCHING):
            video.status = WatchStatus.SAVED

    return celebration


def _render_progress_controls(video: Video) -> None:
    vid = video.video_id
    if video.duration_sec == 0:
        st.info("ℹ️ Duration unknown — cannot track progress for this video.")
        return
    st.markdown("### ⏱ Watch Progress")
    _render_progress_bar(video, compact=False)
    st.caption("Drag the slider to update your progress, then click **Save**.")
    new_sec = st.slider(
        "Progress (seconds)",
        min_value=0,
        max_value=video.duration_sec,
        value=video.watch_progress_sec,
        step=max(1, video.duration_sec // 200),
        format="%d s",
        key=f"progress_slider_{vid}",
        label_visibility="collapsed",
    )
    q_cols = st.columns(4)
    quick_values = [
        ("0%",   0),
        ("25%",  video.duration_sec // 4),
        ("50%",  video.duration_sec // 2),
        ("100%", video.duration_sec),
    ]
    for col, (label, val) in zip(q_cols, quick_values):
        with col:
            if st.button(label, key=f"qset_{vid}_{label}", width="stretch"):
                celebration = _apply_progress(video, val)
                storage.update_video(video)
                st.session_state.pop(f"detail_status_{vid}", None)
                st.session_state.pop(f"status_{vid}", None)
                if celebration:
                    st.balloons()
                    st.success(celebration)
                st.rerun()

    if st.button("💾 Save Progress", key=f"save_prog_{vid}", type="primary"):
        celebration = _apply_progress(video, new_sec)
        storage.update_video(video)
        st.session_state.pop(f"detail_status_{vid}", None)
        st.session_state.pop(f"status_{vid}", None)
        if celebration:
            st.balloons()
            st.success(celebration)
        else:
            st.success("✅ Progress saved.")
        st.rerun()


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


def _export_study_guide(video: Video) -> str:
    """Compose a portable Markdown study guide for the given video."""
    lines: list[str] = []
    lines.append(f"# {video.title}")
    lines.append("")
    lines.append(f"**Channel:** {video.channel}")
    if video.duration:
        lines.append(f"**Duration:** {video.duration}")
    if video.published_at:
        lines.append(f"**Published:** {video.published_at[:10]}")
    lines.append(f"**URL:** {video.url}")
    if video.tags:
        lines.append(f"**Tags:** {', '.join(video.tags)}")
    lines.append("")
    if video.summary_paragraph:
        lines.append("## Summary")
        lines.append("")
        lines.append(video.summary_paragraph)
        lines.append("")
    if video.summary_bullets:
        lines.append("## Key Takeaways")
        lines.append("")
        for b in video.summary_bullets:
            lines.append(f"- {b}")
        lines.append("")
    if video.auto_notes:
        lines.append("## Auto Notes")
        lines.append("")
        for n in video.auto_notes:
            lines.append(f"- {n}")
        lines.append("")
    if video.manual_notes and video.manual_notes.strip():
        lines.append("## My Notes")
        lines.append("")
        lines.append(video.manual_notes.strip())
        lines.append("")
    return "\n".join(lines)


def _render_download_tab(video: Video) -> None:
    vid     = video.video_id
    has_ff  = downloader.has_ffmpeg()
    ff_ver  = ffmpeg_version()
    if not downloader.is_available():
        st.error("❌ yt-dlp not found.")
        st.code("py -3.11 -m pip install yt-dlp")
        return
    if has_ff:
        st.success(f"✅ FFmpeg detected — `{ff_ver.split('Copyright')[0].strip()}`  — all formats available.")
    else:
        st.warning(
            "⚠️ **FFmpeg not found on PATH.**\n\n"
            "Without FFmpeg:\n"
            "- Audio → downloads as **.m4a**\n"
            "- Video → downloads as **progressive MP4** (max ~720p)\n\n"
            "Install: `winget install --id Gyan.FFmpeg -e` then restart."
        )
    st.markdown("### ⬇️ Download")
    st.caption(f"Saved to: `{root / 'downloads'}`")
    mode_labels = list(DOWNLOAD_MODES.keys())
    mode_labels_display = (
        [
            "🎧 Audio only (M4A — no FFmpeg)",
            "📹 Video 720p (MP4 progressive — no FFmpeg)",
            "📹 Video 1080p (falls back to 720p — no FFmpeg)",
            "📹 Video Best (progressive MP4 — no FFmpeg)",
        ]
        if not has_ff else mode_labels
    )
    selected_display = st.selectbox("Format", options=mode_labels_display, key=f"dl_mode_{vid}")
    mode = list(DOWNLOAD_MODES.values())[mode_labels_display.index(selected_display)]
    if video.local_path and Path(video.local_path).exists():
        st.success(f"✅ Already downloaded: `{Path(video.local_path).name}`")
        with open(video.local_path, "rb") as f:
            file_bytes = f.read()
        fname = Path(video.local_path).name
        mime  = "audio/mpeg" if fname.endswith(".mp3") else ("audio/mp4" if fname.endswith(".m4a") else "video/mp4")
        st.download_button(label="📥 Save to computer", data=file_bytes, file_name=fname, mime=mime, key=f"dl_save_{vid}")
        st.divider()
        st.caption("Re-download in a different format ↓")
    elif video.local_path and not Path(video.local_path).exists():
        video.local_path = None
        storage.update_video(video)
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
                if downloader.last_warnings:
                    with st.expander("⚠️ yt-dlp warnings", expanded=False):
                        for w in downloader.last_warnings:
                            st.caption(w)
                with open(out_path, "rb") as f:
                    file_bytes = f.read()
                fname = out_path.name
                mime  = "audio/mpeg" if fname.endswith(".mp3") else ("audio/mp4" if fname.endswith(".m4a") else "video/mp4")
                st.download_button(label="📥 Save to computer", data=file_bytes, file_name=fname, mime=mime, key=f"dl_save_new_{vid}")
            except RuntimeError as exc:
                st.session_state[dl_key] = False
                if video.local_path:
                    video.local_path = None
                    storage.update_video(video)
                st.error(f"❌ Download failed:\n\n{exc}")


# ── fix(B2): clickable timestamps ─────────────────────────────────────────
def _linkify_timestamps(text: str, video_id: str) -> str:
    """Replace HH:MM:SS / MM:SS patterns with YouTube deep-link HTML anchors.

    fix(B2): switched from Markdown [label](url) to HTML <a href="..."> so
    that the links are rendered correctly inside the unsafe_allow_html <div>.
    fix(B10): input is HTML-escaped before substitution to prevent XSS.
    Self-contained: all helpers are local so AST-exec tests work correctly.
    """
    _TS_RE = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")  # [H:]M:SS

    _ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"}
    safe = re.sub(r'[&<>"\'`]', lambda m: _ESC.get(m.group(0), m.group(0)), text)

    def _replace(match: re.Match) -> str:
        h, m, s = match.group(1), match.group(2), match.group(3)
        total   = (int(h) if h else 0) * 3600 + int(m) * 60 + int(s)
        label   = match.group(0)
        if "youtube.com/watch" in video_id:
            url = f"{video_id}&t={total}s"
        else:
            url = f"https://www.youtube.com/watch?v={video_id}&t={total}s"
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#1a6b8a;text-decoration:none;font-weight:500;">'
            f'{label}</a>'
        )

    return _TS_RE.sub(_replace, safe)


def _render_transcript_tab(video: Video) -> None:
    """Render the Transcript tab with clickable timestamp links."""
    vid = video.video_id
    if video.transcript_text:
        st.caption(f"Source: `{video.transcript_source or 'unknown'}`  ·  Timestamps are clickable YouTube deep-links 🔗")
        view_mode = st.radio(
            "View",
            ["🔗 Clickable timestamps", "📋 Raw text"],
            horizontal=True,
            key=f"transcript_view_{vid}",
            label_visibility="collapsed",
        )
        if view_mode == "🔗 Clickable timestamps":
            linked = _linkify_timestamps(video.transcript_text, vid)
            st.markdown(
                f"""<div style="max-height:380px;overflow-y:auto;
                    background:var(--background-color,#f8f9fa);
                    border:1px solid #ddd;border-radius:6px;
                    padding:12px;font-size:0.85rem;line-height:1.7;
                    white-space:pre-wrap;word-break:break-word;">{linked}</div>""",
                unsafe_allow_html=True,
            )
        else:
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


def _render_detail_page(video: Video) -> None:
    vid = video.video_id

    fresh = storage.get_video(vid)
    if fresh is not None:
        video = fresh

    detail_key = f"detail_status_{vid}"
    if detail_key in st.session_state and st.session_state[detail_key] != video.status.value:
        del st.session_state[detail_key]

    if st.button("← Back", key="back_btn"):
        st.session_state.pop("detail_video_id", None)
        st.rerun()
    col1, col2 = st.columns([1, 2])
    with col1:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")
    with col2:
        st.title(video.title)
        st.caption(f"📺 {video.channel}  ·  ⏱ {video.duration}  ·  {(video.published_at or '')[:10]}")
        st.markdown(f"🔗 [Watch on YouTube]({video.url})")
        if video.tags:
            tag_html = "  ".join(
                f'<span style="background:#e8f4f8;border:1px solid #b3d7e8;border-radius:12px;'
                f'padding:2px 9px;font-size:0.78rem;color:#1a6b8a;white-space:nowrap;">🏷️ {t}</span>'
                for t in video.tags[:8]
            )
            st.markdown(tag_html, unsafe_allow_html=True)
        status_options = [s.value for s in WatchStatus]
        new_status = st.selectbox(
            "Status", options=status_options,
            index=status_options.index(video.status.value),
            key=detail_key,
            format_func=lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s.capitalize()}",
        )
        if new_status != video.status.value:
            video.status = WatchStatus(new_status)
            storage.update_video(video)
            st.rerun()
        _render_progress_bar(video, compact=False)

        colls = storage.get_collections_for_video(vid)
        if colls:
            badges = "  ".join(f"`{c.emoji} {c.name}`" for c in colls)
            st.caption(f"📁 In: {badges}")

    st.divider()
    tabs = st.tabs(["📝 Summary", "🗒️ Notes", "📄 Transcript", "❓ Ask", "⏱ Progress", "📁 Collections", "⬇️ Download"])

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
                        bullets, paragraph = summarizer.summarize(video.transcript_text, video.title)
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
        new_notes = st.text_area("notes", value=video.manual_notes or "", key=f"notes_{vid}", height=150, label_visibility="collapsed")
        if st.button("💾 Save Notes", key=f"save_notes_{vid}"):
            video.manual_notes = new_notes
            storage.update_video(video)
            st.success("✅ Notes saved.")
        has_content = any([
            video.summary_paragraph,
            video.summary_bullets,
            video.auto_notes,
            video.manual_notes and video.manual_notes.strip(),
        ])
        if has_content:
            st.divider()
            guide_md = _export_study_guide(video)
            st.download_button(
                label="📥 Export Study Guide (.md)",
                data=guide_md,
                file_name=f"{video.video_id}_study_guide.md",
                mime="text/markdown",
                key=f"export_guide_{vid}",
                help="Downloads a Markdown file with summary, bullets, auto-notes and your notes.",
            )

    with tabs[2]:
        _render_transcript_tab(video)

    with tabs[3]:
        if not video.transcript_text:
            st.warning("⚠️ Add a transcript first to ask questions.")
        else:
            answer_key = f"qa_answer_{vid}"
            if answer_key not in st.session_state:
                st.session_state[answer_key] = ""
            question = st.text_input("Ask a question about this video", placeholder="e.g. What is the main concept explained?", key=f"qa_input_{vid}")
            if st.button("🔍 Get Answer", key=f"ask_btn_{vid}", type="primary"):
                q = st.session_state.get(f"qa_input_{vid}", "").strip()
                if q:
                    with st.spinner("🧠 Thinking..."):
                        try:
                            ans = summarizer.answer_question(video.transcript_text, q, video.title)
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
        _render_progress_controls(video)

    with tabs[5]:
        st.markdown("### 📁 Collections")
        all_colls = storage.get_all_collections()
        current_colls = storage.get_collections_for_video(vid)
        current_ids   = {c.id for c in current_colls}

        if not all_colls:
            st.info("📦 No collections yet. Create one from the 📁 Collections page.")
        else:
            st.caption("Toggle to add or remove this video from a collection.")
            for coll in all_colls:
                in_coll = coll.id in current_ids
                label   = f"{coll.emoji} {coll.name}  ({coll.video_count} videos)"
                checked = st.checkbox(label, value=in_coll, key=f"coll_toggle_{vid}_{coll.id}")
                if checked != in_coll:
                    if checked:
                        storage.add_video_to_collection(coll.id, vid)
                        st.success(f"✅ Added to {coll.emoji} {coll.name}")
                    else:
                        storage.remove_video_from_collection(coll.id, vid)
                        st.info(f"➖ Removed from {coll.emoji} {coll.name}")
                    st.rerun()

    with tabs[6]:
        _render_download_tab(video)


# ── Feature 3: tag chips on video card ─────────────────────────────────────
def _render_tag_chips(tags: list[str], max_tags: int = 3) -> None:
    if not tags:
        return
    chips = tags[:max_tags]
    chip_html = " ".join(
        f'<span style="background:#e8f4f8;border:1px solid #b3d7e8;border-radius:12px;'
        f'padding:1px 8px;font-size:0.72rem;color:#1a6b8a;white-space:nowrap;">🏷️ {t}</span>'
        for t in chips
    )
    if len(tags) > max_tags:
        chip_html += (
            f' <span style="font-size:0.72rem;color:#888;">+{len(tags) - max_tags} more</span>'
        )
    st.markdown(chip_html, unsafe_allow_html=True)


def _render_video_card(video: Video) -> None:
    with st.container(border=True):
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")
        title_display = video.title[:52] + "..." if len(video.title) > 52 else video.title
        st.markdown(f"**{title_display}**")
        st.caption(f"{video.channel} · {video.duration}")
        if video.tags:
            _render_tag_chips(video.tags)
        _render_progress_bar(video, compact=True)
        status_options = [s.value for s in WatchStatus]
        new_status = st.selectbox(
            "Status", options=status_options,
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
# ║  DASHBOARD CHARTS  (v0.9.0)
# ╚══════════════════════════════════════════════════════

def _render_dashboard_charts(videos: list[Video]) -> None:
    """Render three Plotly insight charts below the metrics row."""
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]
    except ImportError:
        st.warning("📦 `plotly` not installed — run `pip install plotly` to enable charts.")
        return

    all_statuses = [s.value for s in WatchStatus]
    counts       = {s: 0 for s in all_statuses}
    watch_hours  = {s: 0.0 for s in all_statuses}

    for v in videos:
        counts[v.status.value] += 1
        if v.duration_sec > 0:
            watch_hours[v.status.value] += v.duration_sec / 3600

    # ── bucket videos into 4 progress bands
    bands       = ["0–25%", "25–50%", "50–75%", "75–100%"]
    band_counts = {s: [0, 0, 0, 0] for s in all_statuses}
    for v in videos:
        pct = v.progress_pct
        idx = min(int(pct // 25), 3)
        band_counts[v.status.value][idx] += 1

    chart_col1, chart_col2, chart_col3 = st.columns(3)

    # ── Chart 1: Library by status (donut)
    with chart_col1:
        st.markdown("**🍩 Library by Status**")
        labels  = [s for s in all_statuses if counts[s] > 0]
        values  = [counts[s] for s in labels]
        colors  = [_STATUS_HEX[s] for s in labels]
        fig1 = go.Figure(go.Pie(
            labels=[s.capitalize() for s in labels],
            values=values,
            hole=0.55,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="label+percent",
            hovertemplate="%{label}: %{value} video(s)<extra></extra>",
        ))
        fig1.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig1, use_container_width=True)

    # ── Chart 2: Watch time by status (horizontal bar)
    with chart_col2:
        st.markdown("**⏱ Watch Time by Status (hours)**")
        labels_wt = [s for s in all_statuses if watch_hours[s] > 0]
        if not labels_wt:
            st.caption("No duration data yet.")
        else:
            values_wt = [round(watch_hours[s], 2) for s in labels_wt]
            colors_wt = [_STATUS_HEX[s] for s in labels_wt]
            fig2 = go.Figure(go.Bar(
                x=values_wt,
                y=[s.capitalize() for s in labels_wt],
                orientation="h",
                marker=dict(color=colors_wt, line=dict(color="white", width=1)),
                hovertemplate="%{y}: %{x:.2f} h<extra></extra>",
                text=[f"{v:.1f}h" for v in values_wt],
                textposition="outside",
            ))
            fig2.update_layout(
                margin=dict(t=10, b=10, l=10, r=40),
                height=260,
                xaxis=dict(title="", showgrid=True, gridcolor="rgba(0,0,0,0.08)"),
                yaxis=dict(title=""),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Chart 3: Progress heatmap — stacked bar per band
    with chart_col3:
        st.markdown("**📊 Progress Distribution**")
        active = [s for s in all_statuses if any(band_counts[s])]
        if not active:
            st.caption("No progress data yet.")
        else:
            fig3 = go.Figure()
            for s in active:
                fig3.add_trace(go.Bar(
                    name=s.capitalize(),
                    x=bands,
                    y=band_counts[s],
                    marker_color=_STATUS_HEX[s],
                    hovertemplate=f"{s.capitalize()}: %{{y}} video(s)<extra></extra>",
                ))
            fig3.update_layout(
                barmode="stack",
                margin=dict(t=10, b=10, l=10, r=10),
                height=260,
                xaxis=dict(title="Progress band"),
                yaxis=dict(title="Videos", dtick=1),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig3, use_container_width=True)


# ╔══════════════════════════════════════════════════════
# ║  PAGE ROUTING
# ╚══════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📺 YT Learning Tracker")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "➕ Add Video", "📚 Library", "📁 Collections", "🔍 Search", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    if "_last_page" not in st.session_state:
        st.session_state["_last_page"] = page
    if st.session_state["_last_page"] != page:
        st.session_state.pop("detail_video_id", None)
        st.session_state.pop("active_collection_id", None)
        st.session_state["_last_page"] = page
    st.divider()
    counts = storage.count_by_status()
    total  = sum(counts.values())
    st.metric("Total Videos", total)
    c1, c2 = st.columns(2)
    c1.metric("🟢 Done",     counts.get("completed", 0))
    c2.metric("🟡 Watching", counts.get("watching",  0))
    n_colls = len(storage.get_all_collections())
    if n_colls:
        st.caption(f"📁 {n_colls} collection{'s' if n_colls != 1 else ''}")


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

        all_vids = storage.get_all_videos()
        vids_with_duration = [v for v in all_vids if v.duration_sec > 0]
        if vids_with_duration:
            total_sec    = sum(v.duration_sec          for v in vids_with_duration)
            watched_sec  = sum(v.watch_progress_sec    for v in vids_with_duration)
            overall_pct  = watched_sec / total_sec * 100 if total_sec else 0
            st.divider()
            prog_cols = st.columns([3, 1, 1])
            with prog_cols[0]:
                st.progress(
                    min(1.0, watched_sec / total_sec),
                    text=f"📊 Overall progress — {overall_pct:.1f}% of library watched",
                )
            with prog_cols[1]:
                h, rem = divmod(watched_sec, 3600)
                st.metric("⏱ Watched", f"{h}h {rem//60}m")
            with prog_cols[2]:
                h2, rem2 = divmod(total_sec, 3600)
                st.metric("📽️ Total", f"{h2}h {rem2//60}m")

        # ── v0.9.0: Insight charts
        st.divider()
        st.subheader("📈 Insights")
        _render_dashboard_charts(all_vids)

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
                fetched = fetcher.fetch_video(url, storage=storage)
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
            if video.tags:
                st.markdown(f"**Tags:** {', '.join(video.tags[:6])}")
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
            st.stop()
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

    search_q = st.text_input(
        "🔍 Search",
        placeholder="Filter by title or channel…",
        key="lib_search",
        label_visibility="collapsed",
    )

    col_f, col_ch, col_s = st.columns([2, 2, 2])
    with col_f:
        status_filter = st.selectbox(
            "Status",
            ["All", "saved", "watching", "completed", "dropped", "rewatch"],
            label_visibility="collapsed",
        )
    with col_s:
        sort_by = st.selectbox(
            "Sort",
            ["Recently updated", "Date Added ↓", "Date Added ↑", "Title A–Z", "Progress ↑", "Progress ↓"],
            label_visibility="collapsed",
        )

    all_videos: list[Video] = (
        storage.get_all_videos() if status_filter == "All"
        else storage.filter_by_status(WatchStatus(status_filter))
    )

    all_channels: list[str] = sorted({v.channel for v in all_videos if v.channel})
    selected_channels: list[str] = []
    with col_ch:
        if all_channels:
            selected_channels = st.multiselect(
                "Channel",
                options=all_channels,
                default=[],
                placeholder="All channels",
                key="lib_channel_filter",
                label_visibility="collapsed",
            )

    all_tags: list[str] = sorted(
        {tag for v in all_videos for tag in (v.tags or [])}
    )
    selected_tags: list[str] = []
    if all_tags:
        selected_tags = st.multiselect(
            "🏷️ Filter by tag",
            options=all_tags,
            default=[],
            placeholder="Pick one or more tags…",
            key="lib_tag_filter",
        )

    videos = all_videos
    if search_q:
        q_lower = search_q.lower()
        videos = [
            v for v in videos
            if q_lower in v.title.lower() or q_lower in (v.channel or "").lower()
        ]

    if selected_channels:
        videos = [v for v in videos if v.channel in selected_channels]

    if selected_tags:
        videos = [
            v for v in videos
            if all(tag in (v.tags or []) for tag in selected_tags)
        ]

    if sort_by == "Title A–Z":
        videos = sorted(videos, key=lambda v: v.title.lower())
    elif sort_by == "Progress ↑":
        videos = sorted(videos, key=lambda v: v.progress_pct)
    elif sort_by == "Progress ↓":
        videos = sorted(videos, key=lambda v: v.progress_pct, reverse=True)
    elif sort_by == "Date Added ↓":
        videos = sorted(videos, key=lambda v: v.created_at if hasattr(v, "created_at") and v.created_at else "", reverse=True)
    elif sort_by == "Date Added ↑":
        videos = sorted(videos, key=lambda v: v.created_at if hasattr(v, "created_at") and v.created_at else "")
    else:
        videos = sorted(videos, key=lambda v: v.updated_at, reverse=True)

    if not videos:
        active_filters = []
        if search_q:
            active_filters.append(f'"{search_q}"')
        if selected_channels:
            active_filters.append(f"channel: {', '.join(selected_channels)}")
        if selected_tags:
            active_filters.append(f"tags: {', '.join(selected_tags)}")
        if active_filters:
            st.info(f"🔍 No videos match: {' · '.join(active_filters)}")
        else:
            st.info("📦 No videos for this filter.")
    else:
        parts = [f"{len(videos)} video(s)"]
        if search_q:
            parts.append(f'🔍 "{search_q}"')
        if selected_channels:
            parts.append(f"📺 {', '.join(selected_channels)}")
        if selected_tags:
            parts.append(f"🏷️ {', '.join(selected_tags)}")
        st.caption("  ·  ".join(parts))
        cols = st.columns(3)
        for i, video in enumerate(videos):
            with cols[i % 3]:
                _render_video_card(video)


# ── Collections
elif page == "📁 Collections":
    if "detail_video_id" in st.session_state:
        v = storage.get_video(st.session_state["detail_video_id"])
        if v:
            _render_detail_page(v)
            st.stop()

    if "active_collection_id" in st.session_state:
        coll = storage.get_collection(st.session_state["active_collection_id"])
        if coll:
            if st.button("← Back to Collections", key="back_to_colls"):
                st.session_state.pop("active_collection_id", None)
                st.rerun()

            h_col1, h_col2 = st.columns([3, 1])
            with h_col1:
                st.title(f"{coll.emoji} {coll.name}")
                if coll.description:
                    st.caption(coll.description)
                st.caption(f"{coll.video_count} video{'s' if coll.video_count != 1 else ''}")
            with h_col2:
                with st.expander("✏️ Edit"):
                    new_name = st.text_input("Name", value=coll.name, key="edit_coll_name")
                    new_desc = st.text_input("Description", value=coll.description, key="edit_coll_desc")
                    new_emoji = st.selectbox("Emoji", EMOJI_OPTIONS,
                                             index=EMOJI_OPTIONS.index(coll.emoji) if coll.emoji in EMOJI_OPTIONS else 0,
                                             key="edit_coll_emoji")
                    if st.button("💾 Save Changes", key="save_coll_edit"):
                        coll.name        = new_name.strip() or coll.name
                        coll.description = new_desc.strip()
                        coll.emoji       = new_emoji
                        storage.update_collection(coll)
                        st.success("✅ Saved.")
                        st.rerun()

            st.divider()

            coll_videos = storage.get_videos_in_collection(coll.id)
            if not coll_videos:
                st.info("📦 No videos yet. Open any video → 📁 Collections tab to add it here.")
            else:
                v_cols = st.columns(3)
                for i, video in enumerate(coll_videos):
                    with v_cols[i % 3]:
                        with st.container(border=True):
                            if video.thumbnail_url:
                                st.image(video.thumbnail_url, width="stretch")
                            title_display = video.title[:52] + "..." if len(video.title) > 52 else video.title
                            st.markdown(f"**{title_display}**")
                            st.caption(f"{video.channel} · {video.duration}")
                            _render_progress_bar(video, compact=True)
                            btn_cols = st.columns(2)
                            with btn_cols[0]:
                                if st.button("📌 View", key=f"coll_view_{coll.id}_{video.video_id}", width="stretch"):
                                    st.session_state["detail_video_id"] = video.video_id
                                    st.rerun()
                            with btn_cols[1]:
                                if st.button("➖ Remove", key=f"coll_rm_{coll.id}_{video.video_id}", width="stretch"):
                                    storage.remove_video_from_collection(coll.id, video.video_id)
                                    st.rerun()

            st.divider()
            with st.expander("➕ Add videos to this collection"):
                all_vids  = storage.get_all_videos()
                not_in    = [v for v in all_vids if v.video_id not in coll.video_ids]
                if not not_in:
                    st.info("✅ All your saved videos are already in this collection.")
                else:
                    search_q2 = st.text_input("Filter videos", placeholder="Type to filter...", key=f"coll_add_search_{coll.id}")
                    filtered = [v for v in not_in if search_q2.lower() in v.title.lower() or search_q2.lower() in v.channel.lower()] if search_q2 else not_in
                    for v in filtered[:20]:
                        a_cols = st.columns([3, 1])
                        with a_cols[0]:
                            st.caption(f"{v.title[:60]}  ·  {v.channel}")
                        with a_cols[1]:
                            if st.button("➕ Add", key=f"add_to_coll_{coll.id}_{v.video_id}", width="stretch"):
                                storage.add_video_to_collection(coll.id, v.video_id)
                                st.rerun()
                    if len(filtered) > 20:
                        st.caption(f"...and {len(filtered) - 20} more. Use the filter to narrow down.")
            st.stop()

    st.title("📁 Collections")
    all_colls = storage.get_all_collections()

    with st.expander("➕ Create new collection", expanded=len(all_colls) == 0):
        with st.form("new_coll_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
            with f_col1:
                new_name = st.text_input("Collection name", placeholder="e.g. Python Course, AI Papers")
            with f_col2:
                new_emoji = st.selectbox("Emoji", EMOJI_OPTIONS)
            with f_col3:
                new_desc = st.text_input("Description (optional)")
            if st.form_submit_button("➕ Create", type="primary"):
                if new_name.strip():
                    coll = Collection(name=new_name.strip(), emoji=new_emoji, description=new_desc.strip())
                    storage.save_collection(coll)
                    st.success(f'✅ Created "{new_emoji} {new_name.strip()}"')
                    st.rerun()
                else:
                    st.warning("⚠️ Name cannot be empty.")

    if not all_colls:
        st.info("📦 No collections yet. Create one above to organise your library.")
    else:
        st.caption(f"{len(all_colls)} collection{'s' if len(all_colls) != 1 else ''}")
        c_cols = st.columns(3)
        for i, coll in enumerate(all_colls):
            with c_cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"### {coll.emoji} {coll.name}")
                    if coll.description:
                        st.caption(coll.description)
                    coll_vids = storage.get_videos_in_collection(coll.id)
                    total_in  = len(coll_vids)
                    done_in   = sum(1 for v in coll_vids if v.status == WatchStatus.COMPLETED)
                    st.caption(f"{total_in} video{'s' if total_in != 1 else ''}  ·  {done_in} completed")
                    if total_in > 0:
                        vids_dur = [v for v in coll_vids if v.duration_sec > 0]
                        if vids_dur:
                            t_sec = sum(v.duration_sec for v in vids_dur)
                            w_sec = sum(v.watch_progress_sec for v in vids_dur)
                            pct   = w_sec / t_sec if t_sec else 0
                            st.progress(pct, text=f"{pct*100:.0f}% watched")
                    card_cols = st.columns(2)
                    with card_cols[0]:
                        if st.button("📂 Open", key=f"open_coll_{coll.id}", width="stretch", type="primary"):
                            st.session_state["active_collection_id"] = coll.id
                            st.rerun()
                    with card_cols[1]:
                        if st.button("🗑️ Delete", key=f"del_coll_{coll.id}", width="stretch"):
                            st.session_state[f"del_armed_{coll.id}"] = True
                            st.rerun()
                    if st.session_state.get(f"del_armed_{coll.id}"):
                        st.error(f'Delete "{coll.name}"? Videos are kept.')
                        yes_col, no_col = st.columns(2)
                        with yes_col:
                            if st.button("✅ Yes", key=f"del_yes_{coll.id}", width="stretch"):
                                storage.delete_collection(coll.id)
                                st.session_state.pop(f"del_armed_{coll.id}", None)
                                st.rerun()
                        with no_col:
                            if st.button("❌ No", key=f"del_no_{coll.id}", width="stretch"):
                                st.session_state.pop(f"del_armed_{coll.id}", None)
                                st.rerun()


# ── Search
elif page == "🔍 Search":
    if "detail_video_id" in st.session_state:
        v = storage.get_video(st.session_state["detail_video_id"])
        if v:
            _render_detail_page(v)
            st.stop()
    st.title("🔍 Search Library")
    query = st.text_input("Search by title, channel, notes, summary, or keywords in auto-notes", placeholder="e.g. Python, React, machine learning")
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
        import importlib.metadata as _meta
        ytdlp_ver    = _meta.version("yt-dlp")
        ytdlp_status = f"✅ {ytdlp_ver}"
    except Exception:
        ytdlp_ver    = None
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
    n_colls = len(storage.get_all_collections())
    st.write(f"📁 **Collections:** {n_colls}")

    if not ff_ver:
        st.warning(
            "⚠️ FFmpeg not detected. Download feature works in limited mode.\n"
            "Install: `winget install --id Gyan.FFmpeg -e` then restart the app."
        )

    st.divider()
    st.subheader("🔄 Update yt-dlp")
    st.caption("YouTube frequently changes its download protection. Keeping yt-dlp up-to-date fixes signature errors, missing formats, and muted downloads.")
    if "ytdlp_update_log" not in st.session_state:
        st.session_state["ytdlp_update_log"] = ""
    if "ytdlp_update_done" not in st.session_state:
        st.session_state["ytdlp_update_done"] = False
    col_btn, col_ver = st.columns([1, 2])
    with col_btn:
        if st.button("⬆️ Update yt-dlp now", type="primary", key="ytdlp_update_btn"):
            with st.spinner("Running `pip install -U yt-dlp` ..."):
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                    capture_output=True, text=True,
                )
            log = (result.stdout + result.stderr).strip()
            st.session_state["ytdlp_update_log"]  = log
            st.session_state["ytdlp_update_done"] = result.returncode == 0
            st.rerun()
    with col_ver:
        if ytdlp_ver:
            st.info(f"Current version: **{ytdlp_ver}**  \nRestart Streamlit after upgrading.")
    if st.session_state["ytdlp_update_log"]:
        if st.session_state["ytdlp_update_done"]:
            last_line = [l for l in st.session_state["ytdlp_update_log"].splitlines() if l.strip()][-1]
            st.success(f"✅ Update complete — {last_line}")
            st.caption("♻️ Restart Streamlit (`Ctrl+C` then `run.ps1`) to load the new version.")
        else:
            st.error("❌ Update failed.")
        with st.expander("📋 Full log"):
            st.code(st.session_state["ytdlp_update_log"])
