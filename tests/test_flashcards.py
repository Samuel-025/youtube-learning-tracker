"""Unit tests for AI Flashcards generation in summarizer.py."""

from unittest.mock import MagicMock, patch
from core.summarizer import Summarizer


def test_basic_flashcards_fallback():
    summarizer = Summarizer(provider="none")
    transcript = "Python is a programming language. It is widely used for data science and AI development. Streamlit is a web framework. It builds data apps fast."
    cards = summarizer.generate_flashcards(transcript, "Python Overview")
    assert isinstance(cards, list)
    assert len(cards) > 0
    assert "front" in cards[0]
    assert "back" in cards[0]


def test_parse_flashcard_response():
    summarizer = Summarizer(provider="none")
    raw_text = """
    Q: What is Python?
    A: A popular programming language.

    Q: What is Streamlit?
    A: A framework for building data apps.
    """
    cards = summarizer._parse_flashcard_response(raw_text)
    assert len(cards) == 2
    assert cards[0]["front"] == "What is Python?"
    assert cards[0]["back"] == "A popular programming language."
    assert cards[1]["front"] == "What is Streamlit?"
    assert cards[1]["back"] == "A framework for building data apps."
