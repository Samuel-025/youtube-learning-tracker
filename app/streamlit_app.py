"""YouTube Learning Tracker — Streamlit web app (v0.11.0)."""

import re
import json
import streamlit as st  # type: ignore[import-untyped]
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from dotenv import load_dotenv  # type: ignore[import-untyped]

# ─── Path & env setup ────────────────────────────────────────────────────────
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from core.storage import Storage
from core.settings_store import SettingsStore
from core.exporters import export_csv, export_markdown_library, export_video_json
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from core.downloader import Downloader, ffmpeg_version
from core.due_date import due_badge, due_status, days_until
from models.video import Video, WatchStatus
from models.collection import Collection

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Learning Tracker",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Init services ────────────────────────────────────────────────────────────
storage_path = os.getenv("STORAGE_PATH", str(root / "data" / "videos.json"))
settings_path = str(root / "data" / "settings.json")
storage    = Storage(storage_path)
settings   = SettingsStore(settings_path)
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

_STAR_LABELS = ["☆ Unrated", "⭐ 1", "⭐⭐ 2", "⭐⭐⭐ 3", "⭐⭐⭐⭐ 4", "⭐⭐⭐⭐⭐ 5"]


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


def _current_week_bounds() -> tuple[datetime, datetime]:
    """Return (monday_00:00, sunday_23:59:59) for the current ISO week in UTC."""
    now    = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end   = week_start + timedelta(days=7) - timedelta(seconds=1)
    return week_start, week_end


def _week_watched_hours(videos: list[Video]) -> float:
    """Sum watch_progress_sec for videos updated this ISO week, in hours."""
    week_start, week_end = _current_week_bounds()
    total_sec = 0
    for v in videos:
        if not v.updated_at:
            continue
        try:
            updated = datetime.fromisoformat(v.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if week_start <= updated <= week_end:
                total_sec += v.watch_progress_sec
        except (ValueError, AttributeError):
            continue
    return total_sec / 3600


def _render_weekly_goal(videos: list[Video]) -> None:
    """Render the weekly watch goal progress widget on the Dashboard."""
    goal_hours    = settings.weekly_goal_hours
    watched_hours = _week_watched_hours(videos)
    week_start, _ = _current_week_bounds()
    week_label    = week_start.strftime("Week of %b %d")

    if goal_hours <= 0:
        st.info(
            f"🎯 **Weekly Watch Goal** — not set yet.  "
            f"You've watched **{watched_hours:.1f}h** this week.  "
            f"Set a goal in ⚙️ Settings."
        )
        return

    pct       = min(watched_hours / goal_hours, 1.0)
    remaining = max(goal_hours - watched_hours, 0)
    goal_met  = watched_hours >= goal_hours

    st.markdown(f"**🎯 Weekly Watch Goal — {week_label}**")
    g_col1, g_col2, g_col3 = st.columns([4, 1, 1])
    with g_col1:
        bar_text = (
            f"✅ Goal met! {watched_hours:.1f}h / {goal_hours:.1f}h"
            if goal_met
            else f"⏱ {watched_hours:.1f}h watched · {remaining:.1f}h to go · target {goal_hours:.1f}h"
        )
        st.progress(pct, text=bar_text)
    with g_col2:
        st.metric("⏱ Watched", f"{watched_hours:.1f}h")
    with g_col3:
        st.metric("🎯 Goal", f"{goal_hours:.1f}h")
    if goal_met:
        st.success("🏆 You hit your weekly goal — great work!")


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
    if getattr(video, "rating", 0):
        lines.append(f"**Rating:** {'⭐' * video.rating}")
    if getattr(video, "due_date", None):
        lines.append(f"**Due:** {video.due_date}")
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
    vid    = video.video_id
    has_ff = downloader.has_ffmpeg()
    ff_ver = ffmpeg_version()
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


# ── fix(B2/B10): clickable timestamps ─────────────────────────────────────────
def _linkify_timestamps(text: str, video_id: str) -> str:
    """Replace HH:MM:SS / MM:SS patterns with YouTube deep-link HTML anchors."""
    _TS_RE = re.compile(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b")

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


# ── F1 + F2: rating & due-date tab ────────────────────────────────────────────
def _render_rating_due_tab(video: Video) -> None:
    """Render the ⭐ Rating & 📅 Reminders controls (F1 + F2)."""
    vid = video.video_id

    # ── F1: Star rating ───────────────────────────────────────────
    st.markdown("### ⭐ Your Rating")
    current_rating = getattr(video, "rating", 0) or 0
    new_rating = st.radio(
        "Rate this video",
        options=list(range(6)),
        index=current_rating,
        format_func=lambda n: _STAR_LABELS[n],
        horizontal=True,
        key=f"rating_radio_{vid}",
        label_visibility="collapsed",
    )

    st.divider()

    # ── F2: Due date / watch reminder ────────────────────────────
    st.markdown("### 📅 Watch Reminder")
    current_due = None
    if getattr(video, "due_date", None):
        try:
            current_due = date.fromisoformat(video.due_date)
        except ValueError:
            current_due = None

    badge = due_badge(video)
    if badge:
        emoji, label = badge
        d = days_until(video)
        if d is not None and d < 0:
            st.error(f"{emoji} **{label}** — {abs(d)} day(s) ago")
        elif d == 0:
            st.warning(f"{emoji} **{label}**")
        else:
            st.info(f"{emoji} **{label}** — {d} day(s) away")

    new_due_date = st.date_input(
        "Watch by (optional)",
        value=current_due,
        min_value=None,
        key=f"due_date_input_{vid}",
        help="Set a target date to watch this video. Leave blank to clear.",
    )

    # Clear button
    if current_due and st.button("🗑️ Clear due date", key=f"clear_due_{vid}"):
        video.due_date = None
        storage.update_video(video)
        st.success("✅ Due date cleared.")
        st.rerun()

    if st.button("💾 Save", key=f"save_rating_due_{vid}", type="primary"):
        video.rating = new_rating
        if new_due_date:
            video.due_date = new_due_date.isoformat()
        elif not current_due:
            video.due_date = None
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

        # ── F1 badge: star rating in header ──────────────────────
        rating = getattr(video, "rating", 0) or 0
        if rating:
            st.caption(f"{'⭐' * rating}  ({rating}/5)")

        # ── F2 badge: due-date indicator in header ────────────────
        badge = due_badge(video)
        if badge:
            emoji, label = badge
            d = days_until(video)
            if d is not None and d < 0:
                st.error(f"{emoji} {label} — {abs(d)}d overdue")
            elif d == 0:
                st.warning(f"{emoji} {label}")
            else:
                st.info(f"{emoji} {label} — in {d}d")

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

    # ── E5: per-video JSON export in detail header ──────────────────────────
    with st.expander("⬇️ Export this video", expanded=False):
        st.caption("Download the full record for this video as a JSON file (compatible with Settings → Import JSON).")
        video_json_str = export_video_json(video)
        st.download_button(
            label="📥 Download JSON",
            data=video_json_str.encode("utf-8"),
            file_name=f"{vid}.json",
            mime="application/json",
            key=f"export_video_json_{vid}",
        )

    tabs = st.tabs(["📝 Summary", "🗒️ Notes", "📄 Transcript", "❓ Ask", "⏱ Progress", "⭐ Rating & Reminder", "📁 Collections", "⬇️ Download"])

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
        _render_rating_due_tab(video)

    with tabs[6]:
        st.markdown("### 📁 Collections")
        all_colls     = storage.get_all_collections()
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

    with tabs[7]:
        _render_download_tab(video)


# ── Tag chips on video card ─────────────────────────────────────────────────
def _render_tag_chips(tags: list[str], max_tags: int = 3) -> None:
    if not tags:
        return
    chips    = tags[:max_tags]
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

        # ── F1 + F2 inline badges on card ───────────────────────
        meta_parts = [f"{video.channel} · {video.duration}"]
        rating = getattr(video, "rating", 0) or 0
        if rating:
            meta_parts.append("⭐" * rating)
        badge = due_badge(video)
        if badge:
            emoji, label = badge
            meta_parts.append(f"{emoji} {label}")
        st.caption("  ·  ".join(meta_parts))

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
    counts_local = {s: 0 for s in all_statuses}
    watch_hours  = {s: 0.0 for s in all_statuses}

    for v in videos:
        counts_local[v.status.value] += 1
        if v.duration_sec > 0:
            watch_hours[v.status.value] += v.duration_sec / 3600

    bands       = ["0–25%", "25–50%", "50–75%", "75–100%"]
    band_counts = {s: [0, 0, 0, 0] for s in all_statuses}
    for v in videos:
        pct = v.progress_pct
        idx = min(int(pct // 25), 3)
        band_counts[v.status.value][idx] += 1

    chart_col1, chart_col2, chart_col3 = st.columns(3)

    with chart_col1:
        st.markdown("**🍩 Library by Status**")
        labels = [s for s in all_statuses if counts_local[s] > 0]
        values = [counts_local[s] for s in labels]
        colors = [_STATUS_HEX[s] for s in labels]
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
        st.plotly_chart(fig1, width="stretch")

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
            st.plotly_chart(fig2, width="stretch")

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
                    hovertemplate="%{x}: %{y} video(s)<extra></extra>",
                ))
            fig3.update_layout(
                barmode="stack",
                margin=dict(t=10, b=10, l=10, r=10),
                height=260,
                xaxis=dict(title=""),
                yaxis=dict(title="Count"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig3, width="stretch")


# ╔══════════════════════════════════════════════════════
# ║  PAGES
# ╚══════════════════════════════════════════════════════

def page_dashboard() -> None:
    st.title("📊 Dashboard")
    videos = storage.get_all_videos()

    _render_weekly_goal(videos)
    st.divider()

    total     = len(videos)
    completed = sum(1 for v in videos if v.status == WatchStatus.COMPLETED)
    watching  = sum(1 for v in videos if v.status == WatchStatus.WATCHING)
    saved     = sum(1 for v in videos if v.status == WatchStatus.SAVED)
    total_hrs = sum(v.duration_sec for v in videos) / 3600
    watched_hrs = sum(v.watch_progress_sec for v in videos) / 3600

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("📚 Total",     total)
    m2.metric("✅ Completed", completed)
    m3.metric("🟡 Watching",  watching)
    m4.metric("🔵 Saved",     saved)
    m5.metric("⏱ Total hrs",  f"{total_hrs:.1f}h")
    m6.metric("👁 Watched",   f"{watched_hrs:.1f}h")

    if videos:
        st.divider()
        _render_dashboard_charts(videos)
    else:
        st.info("📭 No videos yet. Add some from ➕ Add Video.")


def page_library() -> None:
    if "detail_video_id" in st.session_state:
        vid = st.session_state["detail_video_id"]
        video = storage.get_video(vid)
        if video:
            _render_detail_page(video)
            return
        else:
            st.session_state.pop("detail_video_id", None)

    st.title("📚 Library")
    videos = storage.get_all_videos()
    if not videos:
        st.info("📭 No videos yet. Go to ➕ Add Video.")
        return

    # ── Filters ──────────────────────────────────────────────────────────────
    with st.expander("🔍 Filter & Search", expanded=False):
        col_s, col_t, col_sort, col_due = st.columns([2, 2, 2, 2])
        with col_s:
            status_filter = st.selectbox(
                "Status", ["All"] + [s.value.capitalize() for s in WatchStatus],
                key="lib_status_filter",
            )
        with col_t:
            all_tags = sorted({t for v in videos for t in v.tags})
            tag_filter = st.selectbox("Tag", ["All"] + all_tags, key="lib_tag_filter")
        with col_sort:
            sort_by = st.selectbox(
                "Sort by",
                ["Date added (newest)", "Date added (oldest)", "Title A→Z", "Title Z→A",
                 "Progress ↑", "Progress ↓", "Rating ↑", "Rating ↓",
                 "Due date (soonest)", "Due date (latest)"],
                key="lib_sort_by",
            )
        with col_due:
            due_filter = st.selectbox(
                "Due",
                ["All", "Overdue", "Due today", "Due this week", "Has due date", "No due date"],
                key="lib_due_filter",
            )

    search_q = st.text_input("🔎 Search title / channel / tags", key="lib_search", placeholder="Type to search…")

    filtered = list(videos)

    if status_filter != "All":
        filtered = [v for v in filtered if v.status.value.capitalize() == status_filter]
    if tag_filter != "All":
        filtered = [v for v in filtered if tag_filter in v.tags]
    if search_q.strip():
        q = search_q.strip().lower()
        filtered = [
            v for v in filtered
            if q in v.title.lower() or q in v.channel.lower() or any(q in t.lower() for t in v.tags)
        ]

    today = date.today()
    week_end = today + timedelta(days=7)
    if due_filter == "Overdue":
        filtered = [v for v in filtered if getattr(v, "due_date", None) and date.fromisoformat(v.due_date) < today]
    elif due_filter == "Due today":
        filtered = [v for v in filtered if getattr(v, "due_date", None) and date.fromisoformat(v.due_date) == today]
    elif due_filter == "Due this week":
        filtered = [v for v in filtered if getattr(v, "due_date", None) and today <= date.fromisoformat(v.due_date) <= week_end]
    elif due_filter == "Has due date":
        filtered = [v for v in filtered if getattr(v, "due_date", None)]
    elif due_filter == "No due date":
        filtered = [v for v in filtered if not getattr(v, "due_date", None)]

    def _due_sort_key(v: Video):
        dd = getattr(v, "due_date", None)
        return date.fromisoformat(dd) if dd else date(9999, 12, 31)

    if sort_by == "Date added (newest)":
        filtered.sort(key=lambda v: v.added_at or "", reverse=True)
    elif sort_by == "Date added (oldest)":
        filtered.sort(key=lambda v: v.added_at or "")
    elif sort_by == "Title A→Z":
        filtered.sort(key=lambda v: v.title.lower())
    elif sort_by == "Title Z→A":
        filtered.sort(key=lambda v: v.title.lower(), reverse=True)
    elif sort_by == "Progress ↑":
        filtered.sort(key=lambda v: v.progress_pct)
    elif sort_by == "Progress ↓":
        filtered.sort(key=lambda v: v.progress_pct, reverse=True)
    elif sort_by == "Rating ↑":
        filtered.sort(key=lambda v: getattr(v, "rating", 0) or 0)
    elif sort_by == "Rating ↓":
        filtered.sort(key=lambda v: getattr(v, "rating", 0) or 0, reverse=True)
    elif sort_by == "Due date (soonest)":
        filtered.sort(key=_due_sort_key)
    elif sort_by == "Due date (latest)":
        filtered.sort(key=_due_sort_key, reverse=True)

    st.caption(f"Showing {len(filtered)} of {len(videos)} videos")

    if not filtered:
        st.warning("No videos match your filters.")
        return

    cols = st.columns(3)
    for i, video in enumerate(filtered):
        with cols[i % 3]:
            _render_video_card(video)


def page_add_video() -> None:
    st.title("➕ Add Video")

    url_input = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...", key="add_url")

    if st.button("🔍 Fetch Metadata", type="primary", key="fetch_btn"):
        if not url_input.strip():
            st.warning("⚠️ Enter a URL first.")
        else:
            with st.spinner("Fetching metadata…"):
                try:
                    video = fetcher.fetch(url_input.strip())
                    st.session_state["pending_video"] = video
                    st.session_state.pop("pending_transcript_done", None)
                except Exception as exc:
                    st.error(f"❌ {exc}")

    if "pending_transcript_done" in st.session_state:
        st.success("✅ Video already saved!")
        if st.button("➕ Add another"):
            st.session_state.pop("pending_transcript_done", None)
            st.session_state.pop("pending_video", None)
            st.rerun()
        return

    video: Video | None = st.session_state.get("pending_video")
    if video is None:
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, width="stretch")
    with col2:
        st.subheader(video.title)
        st.caption(f"📺 {video.channel}  ·  ⏱ {video.duration}  ·  {(video.published_at or '')[:10]}")

    st.divider()

    # Tags
    tags_input = st.text_input("🏷️ Tags (comma-separated)", key="add_tags", placeholder="python, tutorial, ml")
    if tags_input.strip():
        video.tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    # Collection
    all_colls = storage.get_all_collections()
    coll_options = ["None"] + [f"{c.emoji} {c.name}" for c in all_colls]
    selected_coll = st.selectbox("📁 Add to collection (optional)", coll_options, key="add_coll")

    # Transcript
    st.markdown("### 📄 Transcript")
    transcript_mode = st.radio(
        "Source",
        ["⚡ Auto-fetch", "✍️ Paste manually", "📁 Upload .txt", "⏭️ Skip"],
        horizontal=True,
        key="transcript_mode",
    )

    if transcript_mode == "⚡ Auto-fetch":
        if st.button("📥 Fetch Transcript", key="fetch_transcript_btn"):
            with st.spinner("Fetching transcript…"):
                try:
                    text, source = extractor.extract(video.video_id)
                    video.transcript_text   = text
                    video.transcript_source = source
                    st.success(f"✅ Transcript fetched ({source}).")
                except Exception as exc:
                    st.warning(f"⚠️ Could not fetch transcript: {exc}")

        if video.transcript_text:
            st.text_area("Preview", value=video.transcript_text[:500] + "…", height=100, disabled=True, key="preview_transcript")

        if st.button("💾 Save Video", type="primary", key="save_video_btn_auto"):
            _apply_collection(video, selected_coll, all_colls)
            if video.transcript_text:
                _finish_add_video(video)
            else:
                storage.save_video(video)
                st.session_state.pop("pending_video", None)
                st.session_state["pending_transcript_done"] = True
                st.balloons()
                st.success("✅ Video saved without transcript.")

    elif transcript_mode == "✍️ Paste manually":
        pasted = st.text_area("Paste transcript here", height=200, key="manual_transcript")
        if st.button("💾 Save Video", type="primary", key="save_video_btn_paste"):
            _apply_collection(video, selected_coll, all_colls)
            if pasted.strip():
                video.transcript_text   = pasted.strip()
                video.transcript_source = "manual"
                _finish_add_video(video)
            else:
                storage.save_video(video)
                st.session_state.pop("pending_video", None)
                st.session_state["pending_transcript_done"] = True
                st.balloons()
                st.success("✅ Video saved without transcript.")

    elif transcript_mode == "📁 Upload .txt":
        uploaded = st.file_uploader("Upload transcript (.txt)", type=["txt"], key="upload_transcript")
        if uploaded:
            raw = uploaded.read().decode("utf-8")
            st.text_area("Preview", value=raw[:500] + "…", height=100, disabled=True, key="preview_upload")
            if st.button("💾 Save Video", type="primary", key="save_video_btn_upload"):
                _apply_collection(video, selected_coll, all_colls)
                video.transcript_text   = raw.strip()
                video.transcript_source = "upload"
                _finish_add_video(video)

    else:  # Skip
        if st.button("💾 Save Video (no transcript)", type="primary", key="save_video_btn_skip"):
            _apply_collection(video, selected_coll, all_colls)
            storage.save_video(video)
            st.session_state.pop("pending_video", None)
            st.session_state["pending_transcript_done"] = True
            st.balloons()
            st.success("✅ Video saved!")


def _apply_collection(video: Video, selected_coll: str, all_colls: list[Collection]) -> None:
    if selected_coll != "None":
        for c in all_colls:
            if f"{c.emoji} {c.name}" == selected_coll:
                storage.save_video(video)
                storage.add_video_to_collection(c.id, video.video_id)
                return


def page_collections() -> None:
    st.title("📁 Collections")

    # ── Create new collection ─────────────────────────────────────────────────
    with st.expander("➕ Create New Collection", expanded=False):
        c1, c2, c3 = st.columns([1, 3, 1])
        with c1:
            emoji = st.selectbox("Icon", EMOJI_OPTIONS, key="new_coll_emoji")
        with c2:
            name = st.text_input("Name", key="new_coll_name", placeholder="e.g. Python Tutorials")
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Create", key="create_coll_btn", type="primary"):
                if name.strip():
                    coll = Collection(name=name.strip(), emoji=emoji)
                    storage.save_collection(coll)
                    st.success(f"✅ Created {emoji} {name.strip()}")
                    st.rerun()
                else:
                    st.warning("⚠️ Enter a name.")

    colls = storage.get_all_collections()
    if not colls:
        st.info("📦 No collections yet.")
        return

    for coll in colls:
        with st.expander(f"{coll.emoji} **{coll.name}** ({coll.video_count} videos)", expanded=False):
            col_r, col_d = st.columns([4, 1])
            with col_r:
                new_name = st.text_input("Rename", value=coll.name, key=f"rename_{coll.id}")
                new_emoji = st.selectbox("Icon", EMOJI_OPTIONS, index=EMOJI_OPTIONS.index(coll.emoji) if coll.emoji in EMOJI_OPTIONS else 0, key=f"emoji_{coll.id}")
                if st.button("💾 Save", key=f"save_coll_{coll.id}"):
                    coll.name  = new_name.strip() or coll.name
                    coll.emoji = new_emoji
                    storage.update_collection(coll)
                    st.success("✅ Updated.")
                    st.rerun()
            with col_d:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if st.button("🗑️ Delete", key=f"del_coll_{coll.id}", type="secondary"):
                    storage.delete_collection(coll.id)
                    st.warning(f"🗑️ Deleted {coll.emoji} {coll.name}")
                    st.rerun()

            vids_in_coll = storage.get_videos_in_collection(coll.id)
            if vids_in_coll:
                st.divider()
                st.caption(f"{len(vids_in_coll)} video(s) in this collection:")
                for v in vids_in_coll:
                    vc1, vc2 = st.columns([5, 1])
                    with vc1:
                        st.markdown(f"• **{v.title[:60]}** — {STATUS_COLORS.get(v.status.value,'⚪')} {v.status.value.capitalize()}")
                    with vc2:
                        if st.button("✖", key=f"rm_{coll.id}_{v.video_id}"):
                            storage.remove_video_from_collection(coll.id, v.video_id)
                            st.rerun()


def page_settings() -> None:
    st.title("⚙️ Settings")

    # ── Weekly goal ───────────────────────────────────────────────────────────
    st.markdown("### 🎯 Weekly Watch Goal")
    current_goal = settings.weekly_goal_hours
    new_goal = st.number_input(
        "Target hours per week (0 = disabled)",
        min_value=0.0,
        max_value=168.0,
        value=float(current_goal),
        step=0.5,
        key="settings_goal",
    )
    if st.button("💾 Save Goal", key="save_goal_btn", type="primary"):
        settings.weekly_goal_hours = new_goal
        st.success(f"✅ Goal set to {new_goal:.1f}h/week." if new_goal > 0 else "✅ Goal disabled.")

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("### 📤 Export Library")
    videos = storage.get_all_videos()

    e1, e2, e3 = st.columns(3)

    with e1:
        st.markdown("**CSV**")
        if st.button("📊 Generate CSV", key="gen_csv"):
            csv_data = export_csv(videos)
            st.download_button(
                "📥 Download CSV",
                data=csv_data,
                file_name="youtube_tracker_export.csv",
                mime="text/csv",
                key="dl_csv",
            )

    with e2:
        st.markdown("**Markdown**")
        if st.button("📝 Generate Markdown", key="gen_md"):
            md_data = export_markdown_library(videos)
            st.download_button(
                "📥 Download Markdown",
                data=md_data,
                file_name="youtube_tracker_library.md",
                mime="text/markdown",
                key="dl_md",
            )

    with e3:
        st.markdown("**JSON (full backup)**")
        if st.button("📦 Generate JSON", key="gen_json"):
            json_data = storage.export_json()
            st.download_button(
                "📥 Download JSON",
                data=json_data,
                file_name="youtube_tracker_backup.json",
                mime="application/json",
                key="dl_json",
            )

    st.divider()

    # ── Import ────────────────────────────────────────────────────────────────
    st.markdown("### 📥 Import Library")
    st.caption("Import a JSON backup. Choose whether to merge with existing data or replace it entirely.")
    uploaded_json = st.file_uploader("Upload JSON backup", type=["json"], key="import_json_file")
    import_mode   = st.radio("Mode", ["Merge (keep existing + add new)", "Replace (overwrite everything)"], key="import_mode")

    if uploaded_json and st.button("📥 Import", type="primary", key="import_btn"):
        raw = uploaded_json.read().decode("utf-8")
        merge = import_mode.startswith("Merge")
        try:
            added, skipped = storage.import_json(raw, merge=merge)
            st.success(f"✅ Imported: {added} added, {skipped} skipped.")
            st.rerun()
        except (ValueError, KeyError) as exc:
            st.error(f"❌ Import failed: {exc}")

    st.divider()

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.markdown("### 🗑️ Danger Zone")
    with st.expander("⚠️ Delete all videos", expanded=False):
        st.warning("This will permanently delete ALL videos from your library. This cannot be undone.")
        confirm = st.text_input("Type DELETE to confirm", key="delete_confirm")
        if st.button("🗑️ Delete All Videos", type="secondary", key="delete_all_btn"):
            if confirm == "DELETE":
                for v in storage.get_all_videos():
                    storage.delete_video(v.video_id)
                st.success("✅ All videos deleted.")
                st.rerun()
            else:
                st.error("❌ Type DELETE to confirm.")


# ╔══════════════════════════════════════════════════════
# ║  MAIN NAV
# ╚══════════════════════════════════════════════════════

PAGES = {
    "📊 Dashboard":   page_dashboard,
    "📚 Library":     page_library,
    "➕ Add Video":   page_add_video,
    "📁 Collections": page_collections,
    "⚙️ Settings":    page_settings,
}

with st.sidebar:
    st.markdown("## 📺 YT Tracker")
    page = st.radio("Navigate", list(PAGES.keys()), key="nav_page", label_visibility="collapsed")

PAGES[page]()
