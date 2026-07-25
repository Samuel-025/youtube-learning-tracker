"""Unit tests for Study Suite Exporters (Anki, Obsidian, Notion) in core/exporters.py."""

from unittest.mock import MagicMock, patch
import pytest
from models.video import Video, WatchStatus
from core.exporters import export_anki_csv, export_obsidian_markdown, sync_to_notion


def make_test_video() -> Video:
    return Video(
        video_id="test_vid_123",
        url="https://www.youtube.com/watch?v=test_vid_123",
        title="Mastering Python Data Science",
        channel="Data School",
        thumbnail_url="https://img.youtube.com/vi/test_vid_123/hqdefault.jpg",
        published_at="2026-01-01",
        duration="15:30",
        status=WatchStatus.WATCHING,
        summary_bullets=["Learn pandas basics.", "Use matplotlib for plotting."],
        summary_paragraph="A complete guide to Python data analysis.",
        manual_notes="Great overview of dataframes.",
        tags=["python", "data-science"],
        flashcards=[
            {"front": "What is pandas?", "back": "A Python data manipulation library."},
            {"front": "What is matplotlib?", "back": "A plotting library for Python."},
        ],
        rating=5,
        due_date="2026-08-01",
        transcript_text="Hello and welcome to Python data science.",
    )


def test_export_anki_csv():
    video = make_test_video()
    tsv = export_anki_csv(video)
    assert "What is pandas?" in tsv
    assert "A Python data manipulation library." in tsv
    assert "python data-science" in tsv
    assert video.url in tsv


def test_export_obsidian_markdown():
    video = make_test_video()
    md = export_obsidian_markdown(video)
    assert "---" in md
    assert 'title: "Mastering Python Data Science"' in md
    assert 'status: "watching"' in md
    assert "> [!summary] Summary" in md
    assert "> [!abstract] Key Takeaways" in md
    assert "> [!question] Flashcards" in md
    assert "## 📜 Transcript" in md


def test_sync_to_notion_missing_keys():
    video = make_test_video()
    with pytest.raises(ValueError, match="Missing Notion API Key or Database ID"):
        sync_to_notion(video, "", "")


@patch("requests.post")
@patch("requests.patch")
@patch("requests.get")
def test_sync_to_notion_success(mock_get, mock_patch, mock_post):
    # Mock GET /databases/{id} — return schema with a "Name" title property
    mock_db_resp = MagicMock()
    mock_db_resp.status_code = 200
    mock_db_resp.json.return_value = {
        "properties": {
            "Name": {"type": "title", "title": {}},
        }
    }
    mock_get.return_value = mock_db_resp

    # Mock PATCH /databases/{id} — adding missing properties
    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200
    mock_patch.return_value = mock_patch_resp

    # Mock POST /pages — creating the page
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post.return_value = mock_post_resp

    video = make_test_video()
    res = sync_to_notion(video, "secret_test_key", "4a1118a392d04e3ba39f362e5e2d8a7b")
    assert res is True
    mock_get.assert_called_once()   # schema fetch
    mock_patch.assert_called_once() # property creation
    mock_post.assert_called_once()  # page creation

