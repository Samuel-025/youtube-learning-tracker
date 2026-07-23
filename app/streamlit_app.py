import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, date

import streamlit as st
from dotenv import load_dotenv

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
from core.downloader import Downloader, ffmpeg_version
from core.due_date import due_badge, due_status
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
    st.session_state.setdefault("sidebar_nav", "📊 Dashboard")
    st.session_state.setdefault("detail_video_id", None)
    st.session_state.setdefault("pending_video", None)
    st.session_state.setdefault("import_done", False)


def go(page: str, video_id: str | None = None) -> None:
    st.session_state["page"] = page
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
        except Exception as exc:
            st.warning(f"Summary generation skipped: {exc}")
        try:
            video.auto_notes = notes_gen.generate_auto_notes(video.transcript_text, video.title)
        except Exception as exc:
            st.warning(f"Auto-notes generation skipped: {exc}")
    storage.save_video(video)


def render_tag_chips(tags: list[str], max_display: int = 3) -> str:
    if not tags:
        return ""
    display = tags[:max_display]
    chips = " ".join(
        f'<span style="background:#333;color:#ccc;padding:1px 8px;border-radius:10px;font-size:0.8em;margin-right:4px">{t}</span>'
        for t in display
    )
    if len(tags) > max_display:
        chips += f'<span style="color:#888;font-size:0.8em"> +{len(tags) - max_display}</span>'
    return chips


def render_video_card(video: Video, key_prefix: str = "card") -> None:
    cols = st.columns([1, 3, 1, 1])
    with cols[0]:
        if video.thumbnail_url:
            st.image(video.thumbnail_url, use_container_width=True)
    with cols[1]:
        st.markdown(f"**{video.title}**")
        meta_parts = [video.channel, video.duration, video.status.value]
        badge = due_badge(video)
        if badge:
            meta_parts.append(f"{badge[0]} {badge[1]}")
        st.caption(" • ".join(meta_parts))
        chips = render_tag_chips(video.tags)
        if chips:
            st.markdown(chips, unsafe_allow_html=True)
        if video.duration_sec > 0:
            st.progress(video.progress_pct / 100)
    with cols[2]:
        if video.rating:
            st.markdown("⭐" * video.rating)
        else:
            st.write("")
    with cols[3]:
        if st.button("📌 View", key=f"{key_prefix}_view_{video.video_id}"):
            go("📚 Library", video.video_id)


# ── Sidebar ──

def render_sidebar() -> None:
    with st.sidebar:
        st.title("📺 YouTube Tracker")
        if "page" not in st.session_state:
            st.session_state["page"] = PAGES[0]
        current_index = PAGES.index(st.session_state["page"]) if st.session_state["page"] in PAGES else 0
        current = st.radio("Navigate", PAGES, index=current_index, key="sidebar_nav")
        if current != st.session_state["page"]:
            st.session_state["page"] = current
            st.session_state["detail_video_id"] = None
            st.rerun()


# ── Dashboard ──

def _render_weekly_goal() -> None:
    goal = settings.weekly_goal_hours
    watched = _week_watched_hours(all_videos())
    st.subheader("🎯 Weekly Watch Goal")
    if goal > 0:
        pct = min(100.0, watched / goal * 100)
        st.progress(pct / 100)
        st.caption(f"{watched:.1f}h / {goal:.1f}h watched this week")
        if watched >= goal:
            st.success("🏆 Weekly goal achieved!")
    else:
        st.caption(f"{watched:.1f}h watched this week")
        st.info("Set a goal in ⚙️ Settings to track your progress.")


def _render_insight_charts() -> None:
    if not _PLOTLY_AVAILABLE:
        st.info("💡 Install plotly for interactive charts: `pip install plotly`")
        return
    videos = all_videos()
    if not videos:
        return

    c1, c2 = st.columns(2)
    with c1:
        status_counts = storage.count_by_status()
        df_status = [{"Status": k.capitalize(), "Count": v} for k, v in status_counts.items() if v > 0]
        if df_status:
            fig = px.pie(df_status, names="Status", values="Count", title="🍩 Library by Status", hole=0.4)
            fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        by_status: dict[str, float] = {}
        for v in videos:
            key = v.status.value.capitalize()
            by_status[key] = by_status.get(key, 0) + v.duration_sec
        if by_status:
            df_time = [{"Status": k, "Hours": round(v / 3600, 1)} for k, v in sorted(by_status.items())]
            fig2 = px.bar(df_time, x="Hours", y="Status", title="⏱ Watch Time by Status", orientation="h")
            fig2.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📊 Progress Distribution")
    bands = {"0–25%": 0, "25–50%": 0, "50–75%": 0, "75–100%": 0}
    for v in videos:
        pct = v.progress_pct
        if pct < 25:
            bands["0–25%"] += 1
        elif pct < 50:
            bands["25–50%"] += 1
        elif pct < 75:
            bands["50–75%"] += 1
        else:
            bands["75–100%"] += 1
    df_prog = [{"Band": k, "Videos": v} for k, v in bands.items()]
    fig3 = px.bar(df_prog, x="Band", y="Videos", title="Progress Distribution")
    fig3.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)


def _render_due_reminders() -> None:
    videos = all_videos()
    due_groups: dict[str, list[Video]] = {"overdue": [], "today": [], "soon": [], "upcoming": []}
    for v in videos:
        status = due_status(v)
        if status in due_groups:
            due_groups[status].append(v)
    if not any(due_groups.values()):
        return
    st.subheader("📅 Watch Reminders")
    cols = st.columns(4)
    labels = [("🔴 Overdue", "overdue"), ("🟡 Due today", "today"), ("🟡 Due soon", "soon"), ("🟢 This week", "upcoming")]
    for col, (label, key) in zip(cols, labels):
        with col:
            group = due_groups[key]
            if group:
                st.metric(label, len(group))
                for v in group:
                    short = v.title[:40] + "…" if len(v.title) > 40 else v.title
                    st.caption(short)


def page_dashboard() -> None:
    st.title("📊 Dashboard")
    videos = all_videos()
    colls = all_collections()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Videos", len(videos))
    c2.metric("Collections", len(colls))
    c3.metric("Completed", sum(1 for v in videos if v.status == WatchStatus.COMPLETED))
    c4.metric("Watching", sum(1 for v in videos if v.status == WatchStatus.WATCHING))

    total_watched = sum(v.watch_progress_sec for v in videos)
    total_duration = sum(v.duration_sec for v in videos)
    if total_duration > 0:
        overall_pct = total_watched / total_duration * 100
        st.progress(overall_pct / 100)
        st.caption(f"Overall progress: {overall_pct:.1f}% of total library watched")

    _render_weekly_goal()
    _render_due_reminders()
    _render_insight_charts()

    st.subheader("Recently Added")
    recent = sorted(videos, key=lambda v: v.created_at, reverse=True)[:8]
    if not recent:
        st.info("No videos saved yet.")
        return
    for video in recent:
        render_video_card(video)


# ── Add Video ──

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
                fetched_text, fetched_source = extractor.extract(vid)
                if fetched_text:
                    video.transcript_text = fetched_text
                    video.transcript_source = fetched_source
                    st.success(f"Transcript fetched via {fetched_source}.")
                else:
                    st.warning("No transcript found.")
            except Exception as exc:
                st.error(f"Transcript fetch failed: {exc}")

    elif transcript_mode == "Paste manually":
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
            save_video_and_enrich(video)
            st.session_state["pending_video"] = None
            st.success("Video saved.")
            go("📚 Library", video.video_id)
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
            st.image(video.thumbnail_url, use_container_width=True)

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

    st.divider()

    tabs = st.tabs(["Summary", "Transcript", "Notes", "Progress", "Download", "Q&A"])

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
                    path = downloader.download(video.video_id, dl_mode)
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
            if st.button("← Back to Library"):
                st.session_state["detail_video_id"] = None
                st.rerun()
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
    for video in filtered:
        render_video_card(video, key_prefix="lib")


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
                        st.caption(f"**{v.title[:50]}**" if len(v.title) > 50 else f"**{v.title}**")
                        if v.thumbnail_url:
                            st.image(v.thumbnail_url, use_container_width=True)

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
            use_container_width=True,
        )
    with col_ex2:
        export_data = json.dumps(storage.export_json(), indent=2, ensure_ascii=False)
        st.download_button(
            "📦 Export JSON", export_data,
            file_name="youtube_tracker.json", mime="application/json",
            use_container_width=True,
        )
    with col_ex3:
        md_data = export_markdown_library(videos, colls)
        st.download_button(
            "📝 Export Markdown", md_data,
            file_name="youtube_tracker.md", mime="text/markdown",
            use_container_width=True,
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
        if st.button("Clear import state", key="clear_import"):
            st.session_state["import_done"] = False
            st.rerun()

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
