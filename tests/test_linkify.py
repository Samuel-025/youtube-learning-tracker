"""Tests for _linkify_timestamps — clickable timestamp conversion (B2 + B10).

Imports _linkify_timestamps directly from core.ui_helpers (pure Python,
no Streamlit or AST-exec tricks required).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ui_helpers import _linkify_timestamps


class TestLinkifyTimestamps:
    def test_mm_ss_converted_to_anchor(self):
        result = _linkify_timestamps("See 2:34 for details.", "https://youtu.be/abc")
        assert "<a href=" in result
        assert "t=154" in result  # 2*60+34=154

    def test_hh_mm_ss_converted(self):
        result = _linkify_timestamps("Jump to 1:02:03 now.", "https://youtu.be/abc")
        assert "t=3723" in result  # 1*3600+2*60+3=3723

    def test_multiple_timestamps(self):
        result = _linkify_timestamps("Intro at 0:30, main topic at 5:00.", "https://youtu.be/abc")
        assert result.count("<a href=") == 2

    def test_no_timestamps_returns_text(self):
        result = _linkify_timestamps("No timestamps here.", "https://youtu.be/abc")
        assert "<a href=" not in result
        assert "No timestamps here." in result

    def test_output_is_html_not_markdown(self):
        """B2: output must be <a> HTML anchors, not Markdown [label](url)."""
        result = _linkify_timestamps("See 1:00 here.", "https://youtu.be/abc")
        assert "<a href=" in result
        assert "](http" not in result

    def test_script_tag_not_in_output(self):
        """B10: <script> in transcript must not pass through unescaped."""
        malicious = "<script>alert('xss')</script> See 1:00 too."
        result = _linkify_timestamps(malicious, "https://youtu.be/abc")
        assert "<script>" not in result

    def test_zero_seconds_timestamp(self):
        result = _linkify_timestamps("From the start 0:00.", "https://youtu.be/abc")
        assert "t=0" in result

    def test_url_in_anchor(self):
        result = _linkify_timestamps("At 1:30 mark.", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "dQw4w9WgXcQ" in result

    def test_ampersand_escaped_in_plain_text(self):
        result = _linkify_timestamps("A & B, see 1:00.", "https://youtu.be/abc")
        assert "&amp;" in result
        assert "A & B" not in result

    def test_angle_brackets_escaped(self):
        result = _linkify_timestamps("<b>bold</b> at 2:00.", "https://youtu.be/abc")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result
