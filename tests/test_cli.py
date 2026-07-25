"""Unit tests for cli.py commands."""

from unittest.mock import MagicMock, patch
from argparse import Namespace
import cli
from models.video import Video, WatchStatus


def test_cli_stats(capsys):
    args = Namespace(command="stats")
    cli.cmd_stats(args)
    captured = capsys.readouterr()
    assert "Library Stats" in captured.out or "Status" in captured.out


def test_cli_list(capsys):
    args = Namespace(command="list", status=None)
    cli.cmd_list(args)
    captured = capsys.readouterr()
    assert "YouTube Learning Tracker" in captured.out or "No videos" in captured.out


def test_cli_search(capsys):
    args = Namespace(command="search", query="Server")
    cli.cmd_search(args)
    captured = capsys.readouterr()
    assert "result(s)" in captured.out or "No videos found" in captured.out


def test_cli_view_not_found(capsys):
    args = Namespace(command="view", video_id="non_existent_id")
    cli.cmd_view(args)
    captured = capsys.readouterr()
    assert "Video not found" in captured.out


def test_cli_status_query(capsys):
    args = Namespace(command="status", video_id="S_-uD3GtFno", status=None)
    cli.cmd_status(args)
    captured = capsys.readouterr()
    assert "Current status:" in captured.out
