"""Unit tests for Groq model cascade configuration."""

import os
from core import get_groq_models, DEFAULT_GROQ_MODELS


def test_default_groq_models(monkeypatch):
    monkeypatch.delenv("GROQ_MODELS", raising=False)
    models = get_groq_models()
    assert models == DEFAULT_GROQ_MODELS


def test_custom_groq_models(monkeypatch):
    custom_str = "llama-3.3-70b-versatile, custom-model-1"
    monkeypatch.setenv("GROQ_MODELS", custom_str)
    models = get_groq_models()
    assert models == ["llama-3.3-70b-versatile", "custom-model-1"]
