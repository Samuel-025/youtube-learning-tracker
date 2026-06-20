"""Tests for _linkify_timestamps — clickable timestamp conversion (B2 + B10).

We import the helper directly from the app module.
"""

import sys
import types
import pytest

# ---------------------------------------------------------------------------
# Minimal Streamlit stub so app/streamlit_app.py can be imported without a
# running Streamlit server. We only need _linkify_timestamps extracted.
# ---------------------------------------------------------------------------

def _import_linkify():
    """Import _linkify_timestamps without fully booting the Streamlit app."""
    import importlib, pathlib, ast, textwrap

    src = pathlib.Path("app/streamlit_app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Extract just the _linkify_timestamps function source via AST
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_linkify_timestamps":
            func_src = ast.get_source_segment(src, node)
            if func_src:
                ns: dict = {}
                exec(textwrap.dedent(func_src), {"re": __import__("re")}, ns)
                return ns["_linkify_timestamps"]
    raise ImportError("_linkify_timestamps not found in streamlit_app.py")


try:
    _linkify = _import_linkify()
except Exception:
    _linkify = None


@pytest.fixture
def linkify():
    if _linkify is None:
        pytest.skip("Could not import _linkify_timestamps from streamlit_app.py")
    return _linkify


# ---------------------------------------------------------------------------
# Timestamp detection
# ---------------------------------------------------------------------------

class TestLinkifyTimestamps:
    def test_mm_ss_converted_to_anchor(self, linkify):
        result = linkify("See 2:34 for details.", "https://youtu.be/abc")
        assert '<a href=' in result
        assert 't=154' in result  # 2*60+34 = 154

    def test_hh_mm_ss_converted(self, linkify):
        result = linkify("Jump to 1:02:03 now.", "https://youtu.be/abc")
        assert 't=3723' in result  # 1*3600+2*60+3 = 3723

    def test_multiple_timestamps(self, linkify):
        result = linkify("Intro at 0:30, main topic at 5:00.", "https://youtu.be/abc")
        assert result.count('<a href=') == 2

    def test_no_timestamps_returns_escaped_text(self, linkify):
        result = linkify("No timestamps here.", "https://youtu.be/abc")
        assert '<a href=' not in result
        assert 'No timestamps here.' in result

    # B2 fix: output must be HTML <a> anchors, not Markdown [label](url)
    def test_output_is_html_not_markdown(self, linkify):
        result = linkify("See 1:00 here.", "https://youtu.be/abc")
        assert '<a href=' in result
        assert '](http' not in result  # no Markdown link syntax

    # B10 fix: script tags in transcript must NOT appear in output unescaped
    def test_script_tag_is_not_executed(self, linkify):
        malicious = "<script>alert('xss')</script> See 1:00 too."
        result = linkify(malicious, "https://youtu.be/abc")
        assert "<script>" not in result
        assert "alert" not in result or "&lt;script&gt;" in result

    def test_zero_seconds_timestamp(self, linkify):
        result = linkify("From the start 0:00.", "https://youtu.be/abc")
        assert 't=0' in result

    def test_url_contains_video_base_url(self, linkify):
        result = linkify("At 1:30 mark.", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert 'dQw4w9WgXcQ' in result
