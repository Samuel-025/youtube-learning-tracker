"""YouTube Learning Tracker — CLI interface."""

import argparse
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from core.storage import Storage
from core.youtube_fetcher import YouTubeFetcher
from core.transcript_extractor import TranscriptExtractor
from core.summarizer import Summarizer
from core.notes_generator import NotesGenerator
from models.video import WatchStatus

console = Console()
storage = Storage(os.getenv("STORAGE_PATH", "data/videos.json"))
fetcher = YouTubeFetcher()
extractor = TranscriptExtractor()
summarizer = Summarizer()
notes_gen = NotesGenerator()

STATUS_COLORS = {
    "saved": "blue",
    "watching": "yellow",
    "completed": "green",
    "dropped": "red",
    "rewatch": "magenta",
}


def cmd_add(args):
    console.print(f"[cyan]Fetching video info...[/cyan]")
    try:
        video = fetcher.fetch_video(args.url)
    except Exception as e:
        console.print(f"[red]Error fetching video: {e}[/red]")
        return

    # Extract transcript
    console.print(f"[cyan]Extracting transcript...[/cyan]")
    transcript, source = extractor.extract(video.video_id)
    if transcript:
        video.transcript_text = transcript
        video.transcript_source = source
        console.print(f"[green]✓ Transcript extracted ({source})[/green]")
    else:
        console.print(f"[yellow]⚠ Transcript not available — you can add it manually later.[/yellow]")

    # Summarize
    if transcript:
        console.print(f"[cyan]Generating summary...[/cyan]")
        bullets, paragraph = summarizer.summarize(transcript, video.title)
        video.summary_bullets = bullets
        video.summary_paragraph = paragraph
        console.print(f"[green]✓ Summary generated[/green]")

        console.print(f"[cyan]Generating notes...[/cyan]")
        video.auto_notes = notes_gen.generate_auto_notes(transcript, video.title)
        console.print(f"[green]✓ Notes generated[/green]")

    storage.save_video(video)
    console.print(Panel(
        f"[bold white]{video.title}[/bold white]\n"
        f"[dim]Channel:[/dim] {video.channel}\n"
        f"[dim]Duration:[/dim] {video.duration}\n"
        f"[dim]Status:[/dim] [blue]saved[/blue]\n"
        f"[dim]Video ID:[/dim] {video.video_id}",
        title="[green]✅ Video Saved[/green]",
        border_style="green"
    ))


def cmd_list(args):
    videos = storage.get_all_videos()
    if not videos:
        console.print("[yellow]No videos saved yet. Use: python cli.py add <url>[/yellow]")
        return

    if args.status:
        try:
            status = WatchStatus(args.status)
            videos = [v for v in videos if v.status == status]
        except ValueError:
            console.print(f"[red]Invalid status. Use: saved, watching, completed, dropped, rewatch[/red]")
            return

    table = Table(title=f"📺 YouTube Learning Tracker ({len(videos)} videos)", box=box.ROUNDED)
    table.add_column("ID", style="dim", width=12)
    table.add_column("Title", width=40)
    table.add_column("Channel", width=20)
    table.add_column("Duration", width=9)
    table.add_column("Status", width=12)
    table.add_column("Transcript", width=10)

    for v in videos:
        color = STATUS_COLORS.get(v.status.value, "white")
        has_transcript = "✓" if v.transcript_text else "✗"
        table.add_row(
            v.video_id[:11],
            v.title[:38] + ("..." if len(v.title) > 38 else ""),
            v.channel[:18] + ("..." if len(v.channel) > 18 else ""),
            v.duration,
            Text(v.status.value, style=color),
            has_transcript,
        )

    console.print(table)


def cmd_view(args):
    video = storage.get_video(args.video_id)
    if not video:
        console.print(f"[red]Video not found: {args.video_id}[/red]")
        return

    color = STATUS_COLORS.get(video.status.value, "white")
    console.print(Panel(
        f"[bold white]{video.title}[/bold white]\n"
        f"[dim]Channel:[/dim]  {video.channel}\n"
        f"[dim]Duration:[/dim] {video.duration}\n"
        f"[dim]Published:[/dim] {video.published_at[:10]}\n"
        f"[dim]URL:[/dim]      {video.url}\n"
        f"[dim]Status:[/dim]   [{color}]{video.status.value}[/{color}]\n"
        f"[dim]Transcript:[/dim] {'✓ Available' if video.transcript_text else '✗ Not available'} ({video.transcript_source})",
        title=f"[cyan]📺 Video Details[/cyan]",
        border_style="cyan"
    ))

    if video.summary_bullets:
        console.print("\n[bold]📝 Key Points:[/bold]")
        for b in video.summary_bullets:
            console.print(f"  • {b}")

    if video.summary_paragraph:
        console.print(f"\n[bold]📄 Summary:[/bold]\n  {video.summary_paragraph}")

    if video.manual_notes:
        console.print(f"\n[bold]🗒️ Notes:[/bold]\n  {video.manual_notes}")


def cmd_status(args):
    video = storage.get_video(args.video_id)
    if not video:
        console.print(f"[red]Video not found: {args.video_id}[/red]")
        return
    try:
        new_status = WatchStatus(args.status)
    except ValueError:
        console.print(f"[red]Invalid status. Choose from: saved, watching, completed, dropped, rewatch[/red]")
        return

    old = video.status.value
    video.status = new_status
    storage.update_video(video)
    console.print(f"[green]✓ Status updated:[/green] {old} → {new_status.value}")


def cmd_transcript(args):
    video = storage.get_video(args.video_id)
    if not video:
        console.print(f"[red]Video not found: {args.video_id}[/red]")
        return
    if not video.transcript_text:
        console.print(f"[yellow]No transcript for this video. Paste one below (Ctrl+D or Ctrl+Z to finish):[/yellow]")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        text = " ".join(lines).strip()
        if text:
            video.transcript_text = text
            video.transcript_source = "manual"
            storage.update_video(video)
            console.print("[green]✓ Transcript saved.[/green]")
    else:
        console.print(Panel(
            video.transcript_text[:2000] + ("..." if len(video.transcript_text) > 2000 else ""),
            title=f"[cyan]Transcript ({video.transcript_source})[/cyan]",
            border_style="cyan"
        ))


def cmd_summary(args):
    video = storage.get_video(args.video_id)
    if not video:
        console.print(f"[red]Video not found: {args.video_id}[/red]")
        return
    if not video.transcript_text:
        console.print("[yellow]No transcript available. Add transcript first.[/yellow]")
        return
    console.print("[cyan]Generating summary...[/cyan]")
    bullets, paragraph = summarizer.summarize(video.transcript_text, video.title)
    video.summary_bullets = bullets
    video.summary_paragraph = paragraph
    storage.update_video(video)
    console.print("\n[bold]📝 Key Points:[/bold]")
    for b in bullets:
        console.print(f"  • {b}")
    console.print(f"\n[bold]📄 Summary:[/bold]\n  {paragraph}")


def cmd_note(args):
    video = storage.get_video(args.video_id)
    if not video:
        console.print(f"[red]Video not found: {args.video_id}[/red]")
        return
    video.manual_notes = args.text
    storage.update_video(video)
    console.print(f"[green]✓ Note saved.[/green]")


def cmd_search(args):
    results = storage.search_videos(args.query)
    if not results:
        console.print(f"[yellow]No videos found for: '{args.query}'[/yellow]")
        return
    console.print(f"[cyan]Found {len(results)} result(s) for '{args.query}':[/cyan]")
    for v in results:
        color = STATUS_COLORS.get(v.status.value, "white")
        console.print(f"  [{color}]{v.status.value}[/{color}] {v.video_id[:11]} — {v.title[:50]}")


def cmd_stats(args):
    counts = storage.count_by_status()
    total = sum(counts.values())
    table = Table(title="📊 Library Stats", box=box.SIMPLE)
    table.add_column("Status")
    table.add_column("Count", justify="right")
    for status, count in counts.items():
        color = STATUS_COLORS.get(status, "white")
        table.add_row(Text(status, style=color), str(count))
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        prog="python cli.py",
        description="📺 YouTube Learning Tracker CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = subparsers.add_parser("add", help="Save a YouTube video")
    p_add.add_argument("url", help="YouTube video URL")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = subparsers.add_parser("list", help="List saved videos")
    p_list.add_argument("--status", help="Filter by status", default=None)
    p_list.set_defaults(func=cmd_list)

    # view
    p_view = subparsers.add_parser("view", help="View video details")
    p_view.add_argument("video_id", help="YouTube video ID")
    p_view.set_defaults(func=cmd_view)

    # status
    p_status = subparsers.add_parser("status", help="Update watch status")
    p_status.add_argument("video_id", help="YouTube video ID")
    p_status.add_argument("status", help="New status: saved|watching|completed|dropped|rewatch")
    p_status.set_defaults(func=cmd_status)

    # transcript
    p_trans = subparsers.add_parser("transcript", help="View or add transcript")
    p_trans.add_argument("video_id", help="YouTube video ID")
    p_trans.set_defaults(func=cmd_transcript)

    # summary
    p_sum = subparsers.add_parser("summary", help="Generate or view summary")
    p_sum.add_argument("video_id", help="YouTube video ID")
    p_sum.set_defaults(func=cmd_summary)

    # note
    p_note = subparsers.add_parser("note", help="Add a manual note")
    p_note.add_argument("video_id", help="YouTube video ID")
    p_note.add_argument("text", help="Note text")
    p_note.set_defaults(func=cmd_note)

    # search
    p_search = subparsers.add_parser("search", help="Search saved videos")
    p_search.add_argument("query", help="Search query")
    p_search.set_defaults(func=cmd_search)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show library stats")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
