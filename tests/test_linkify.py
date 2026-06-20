"""Tests for _linkify_timestamps — clickable timestamp conversion (B2 + B10).

Extracts _linkify_timestamps directly from streamlit_app.py via AST so we
never boot a Streamlit server.
"""

import ast
import pathlib
import textwrap
import pytest


def _import_linkify():
    src_path = pathlib.Path("app/streamlit_app.py")
    if not src_path.exists():
        return None
    src = src_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_linkify_timestamps":
            func_src = ast.get_source_segment(src, node)
            if func_src:
                ns: dict = {}
                exec(textwrap.dedent(func_src), {"re": __import__("re")}, ns)
                return ns["_linkify_timestamps"]
    return None


_linkify = _import_linkify()


@pytest.fixture
def linkify():
    if _linkify is None:
        pytest.skip("_linkify_timestamps not found in app/streamlit_app.py")
    return _linkify


class TestLinkifyTimestamps:
    def test_mm_ss_converted_to_anchor(self, linkify):
        result = linkify("See 2:34 for details.", "https://youtu.be/abc")
        assert "<a href=" in result
        assert "t=154" in result  # 2*60+34=154

    def test_hh_mm_ss_converted(self, linkify):
        result = linkify("Jump to 1:02:03 now.", "https://youtu.be/abc")
        assert "t=3723" in result  # 1*3600+2*60+3=3723

    def test_multiple_timestamps(self, linkify):
        result = linkify("Intro at 0:30, main topic at 5:00.", "https://youtu.be/abc")
        assert result.count("<a href=") == 2

    def test_no_timestamps_returns_text(self, linkify):
        result = linkify("No timestamps here.", "https://youtu.be/abc")
        assert "<a href=" not in result
        assert "No timestamps here." in result

    def test_output_is_html_not_markdown(self, linkify):
        """B2: output must be <a> HTML anchors, not Markdown [label](url)."""
        result = linkify("See 1:00 here.", "https://youtu.be/abc")
        assert "<a href=" in result
        assert "](http" not in result

    def test_script_tag_not_in_output(self, linkify):
        """B10: <script> in transcript must not pass through unescaped."""
        malicious = "<script>alert('xss')</script> See 1:00 too."
        result = linkify(malicious, "https://youtu.be/abc")
        assert "<script>" not in result

    def test_zero_seconds_timestamp(self, linkify):
        result = linkify("From the start 0:00.", "https://youtu.be/abc")
        assert "t=0" in result

    def test_url_in_anchor(self, linkify):
        result = linkify("At 1:30 mark.", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "dQw4w9WgXcQ" in result
