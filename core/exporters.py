"""Export helpers for YouTube Learning Tracker — E3, E4, E5.

All functions are pure (no I/O, no Streamlit) so they can be called from
streamlit_app.py, cli.py, or tests without side-effects.

E3 — export_csv(videos)            -> str   (UTF-8 CSV text)
E4 — export_markdown_library(videos, collections) -> str   (Markdown text)
E5 — export_video_json(video)      -> str   (JSON text, single video)

v0.11.0: added 'rating' and 'due_date' columns to CSV + Markdown.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.video import Video
    from models.collection import Collection


# ── E3: CSV export ──────────────────────────────────────────────────────────

_CSV_FIELDS = [
    "video_id",
    "title",
    "channel",
    "url",
    "status",
    "rating",
    "due_date",
    "progress_pct",
    "watch_progress_sec",
    "duration_sec",
    "duration",
    "tags",
    "published_at",
    "created_at",
    "updated_at",
    "manual_notes",
    "summary_paragraph",
    "thumbnail_url",
]


def export_csv(videos: list["Video"]) -> str:
    """Serialise a list of Video objects to a UTF-8 CSV string.

    Tags are joined with ' | ' so they fit in a single cell.
    Numeric fields (progress_pct, duration_sec, watch_progress_sec) are
    formatted to two decimal places where applicable.
    Returns an empty CSV with headers only when *videos* is empty.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=_CSV_FIELDS,
        extrasaction="ignore",
        lineterminator="\r\n",
    )
    writer.writeheader()
    for v in videos:
        writer.writerow({
            "video_id":           v.video_id,
            "title":              v.title,
            "channel":            v.channel,
            "url":                v.url,
            "status":             v.status.value,
            "rating":             v.rating,
            "due_date":           v.due_date or "",
            "progress_pct":       f"{v.progress_pct:.2f}",
            "watch_progress_sec": v.watch_progress_sec,
            "duration_sec":       v.duration_sec,
            "duration":           v.duration,
            "tags":               " | ".join(v.tags or []),
            "published_at":       v.published_at,
            "created_at":         v.created_at,
            "updated_at":         v.updated_at,
            "manual_notes":       (v.manual_notes or "").replace("\n", " "),
            "summary_paragraph":  (v.summary_paragraph or "").replace("\n", " "),
            "thumbnail_url":      v.thumbnail_url,
        })
    return buf.getvalue()


# ── E4: Markdown library export ─────────────────────────────────────────────

_STATUS_EMOJI = {
    "saved":     "📌",
    "watching":  "▶️",
    "completed": "✅",
    "dropped":   "🗑️",
    "rewatch":   "🔁",
}

_STATUS_ORDER = ["watching", "saved", "completed", "rewatch", "dropped"]


def export_markdown_library(
    videos: list["Video"],
    collections: list["Collection"] | None = None,
) -> str:
    """Render the full library as a human-readable Markdown document.

    Structure:
        # YouTube Learning Library
        Generated: <timestamp>  |  N videos  |  N collections

        ## Collections
        - **<name>** — N videos: Title 1, Title 2 …

        ## Videos by Status
        ### ▶️ Watching  (N)
        #### Title
        - Channel | Duration | Progress | Rating | Tags
        - Due: <date> (if set)
        - Notes (if any)
        - Summary (if any)

    Notes and summary_paragraph are included only when non-empty so the
    document stays clean for users who haven't used those features.
    """
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_v = len(videos)
    n_c = len(collections) if collections else 0

    lines += [
        "# YouTube Learning Library",
        "",
        f"Generated: {now}  |  {n_v} video(s)  |  {n_c} collection(s)",
        "",
    ]

    # Collections section
    if collections:
        lines += ["## Collections", ""]
        vid_index = {v.video_id: v.title for v in videos}
        for coll in collections:
            titles = [vid_index.get(vid, vid) for vid in coll.video_ids]
            preview = ", ".join(titles[:5])
            if len(titles) > 5:
                preview += f" … +{len(titles) - 5} more"
            lines.append(f"- **{coll.name}** — {len(titles)} video(s): {preview}")
        lines.append("")

    # Videos grouped by status
    lines += ["## Videos by Status", ""]
    by_status: dict[str, list["Video"]] = {s: [] for s in _STATUS_ORDER}
    for v in videos:
        bucket = v.status.value if v.status.value in by_status else "saved"
        by_status[bucket].append(v)

    for status_key in _STATUS_ORDER:
        group = by_status[status_key]
        if not group:
            continue
        emoji = _STATUS_EMOJI.get(status_key, "")
        lines += [f"### {emoji} {status_key.capitalize()}  ({len(group)})", ""]

        for v in sorted(group, key=lambda x: x.title.lower()):
            lines.append(f"#### {v.title}")

            # Meta line
            dur = v.duration or "unknown"
            pct = f"{v.progress_pct:.0f}%" if v.duration_sec else "—"
            tags_str = " · ".join(f"`{t}`" for t in (v.tags or [])) or "—"
            stars = ("⭐" * v.rating) if v.rating else "—"
            lines.append(
                f"- **Channel:** {v.channel}  |  **Duration:** {dur}  |  "
                f"**Progress:** {pct}  |  **Rating:** {stars}  |  **Tags:** {tags_str}"
            )
            lines.append(f"- **URL:** {v.url}")

            if v.due_date:
                lines.append(f"- 📅 **Due:** {v.due_date}")

            if v.manual_notes and v.manual_notes.strip():
                lines.append("- **Notes:**")
                for note_line in v.manual_notes.strip().splitlines():
                    lines.append(f"  {note_line}")

            if v.summary_paragraph and v.summary_paragraph.strip():
                lines.append(f"- **Summary:** {v.summary_paragraph.strip()[:300]}{'…' if len(v.summary_paragraph) > 300 else ''}")

            lines.append("")

    return "\n".join(lines)


# ── E5: Single-video JSON export ─────────────────────────────────────────────

def export_video_json(video: "Video") -> str:
    """Serialise a single Video to a pretty-printed JSON string.

    Includes all fields: metadata, transcript, summary, notes, progress, tags.
    The output is a valid standalone JSON file that can be reimported via
    the E2 import flow (wrap in {videos: {id: record}, collections: {}}).
    """
    payload = {
        "schema_version": 1,
        "exported_at":    datetime.now().isoformat(),
        "video":          video.to_dict(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ── Study Integration Suite: Anki, Obsidian & Notion Exporters ──────────────

def export_anki_csv(video: "Video") -> str:
    """Export video flashcards as an Anki-importable CSV/TSV string.

    Format per row: Front (Question) \t Back (Answer) \t Tags \t URL
    If video has no explicit flashcards, uses summary bullets as Front/Back pairs.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", lineterminator="\r\n")

    cards = video.flashcards or []
    if not cards and video.summary_bullets:
        # Fallback card pairs from bullets
        for i in range(0, len(video.summary_bullets) - 1, 2):
            cards.append({
                "front": f"Key Takeaway: {video.title}",
                "back": f"{video.summary_bullets[i]} — {video.summary_bullets[i+1]}"
            })

    tags_str = " ".join(t.replace(" ", "_") for t in (video.tags or []))
    for card in cards:
        front = card.get("front", "").replace("\n", "<br>")
        back = card.get("back", "").replace("\n", "<br>")
        if front and back:
            writer.writerow([front, back, tags_str, video.url])

    return buf.getvalue()


def export_obsidian_markdown(video: "Video") -> str:
    """Render a Video as an Obsidian-optimized Markdown file with YAML frontmatter & callouts.

    Frontmatter includes tags, status, due_date, rating, video_id, url.
    Body includes GFM Callouts (> [!summary], > [!notes], > [!flashcards]).
    """
    safe_title = video.title.replace('"', '\\"')
    safe_channel = video.channel.replace('"', '\\"')
    due_str = video.due_date if video.due_date else ""
    lines: list[str] = [
        "---",
        f'title: "{safe_title}"',
        f'channel: "{safe_channel}"',
        f'video_id: "{video.video_id}"',
        f'url: "{video.url}"',
        f'status: "{video.status.value}"',
        f"rating: {video.rating}",
        f'due_date: "{due_str}"',
        f'duration: "{video.duration}"',
        "tags:",
    ]
    for tag in (video.tags or []):
        lines.append(f"  - {tag}")
    lines += [
        "---",
        "",
        f"# 📺 {video.title}",
        "",
        f"**Channel:** {video.channel}  |  **Duration:** {video.duration}  |  **URL:** [{video.url}]({video.url})",
        "",
    ]

    if video.summary_paragraph:
        lines += [
            "> [!summary] Summary",
            f"> {video.summary_paragraph}",
            "",
        ]

    if video.summary_bullets:
        lines += ["> [!abstract] Key Takeaways"]
        for b in video.summary_bullets:
            lines.append(f"> - {b}")
        lines.append("")

    if video.manual_notes:
        lines += [
            "> [!note] Manual Notes",
        ]
        for n_line in video.manual_notes.splitlines():
            lines.append(f"> {n_line}")
        lines.append("")

    if video.flashcards:
        lines += ["> [!question] Flashcards"]
        for fc in video.flashcards:
            lines.append(f"> **Q:** {fc.get('front', '')}")
            lines.append(f"> **A:** {fc.get('back', '')}")
            lines.append(">")
        lines.append("")

    if video.transcript_text:
        lines += [
            "## 📜 Transcript",
            "",
            video.transcript_text,
        ]

    return "\n".join(lines)


def sync_to_notion(video: "Video", api_key: str, database_id: str) -> bool:
    """Push video record to a Notion Database via official Notion API.

    Returns True on HTTP 200/201 success.
    """
    import requests

    if not api_key or not database_id:
        raise ValueError("Missing Notion API Key or Database ID.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Title": {
                "title": [{"text": {"content": video.title}}]
            },
            "Channel": {
                "rich_text": [{"text": {"content": video.channel}}]
            },
            "URL": {
                "url": video.url
            },
            "Status": {
                "select": {"name": video.status.value.capitalize()}
            },
        }
    }

    resp = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=10)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Notion API Error ({resp.status_code}): {resp.text}")
    return True

