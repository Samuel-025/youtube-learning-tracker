"""Auto and manual notes generation."""

import os
from typing import Optional

# Groq cascade: best quality first, fast fallback last.
# On HTTP 429 (rate-limit) the next model in the list is tried automatically.
GROQ_MODELS = [
    "llama-3.3-70b-versatile",                         # best free quality, 1K RPD
    "meta-llama/llama-4-scout-17b-16e-instruct",       # balanced, 1K RPD
    "llama-3.1-8b-instant",                            # fast fallback, 14.4K RPD
]


def _groq_chat(messages: list, max_tokens: int) -> str:
    """Try each GROQ_MODELS entry in order, skipping on 429 rate-limit errors."""
    from groq import Groq  # type: ignore[import-untyped]
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    last_err: Exception = RuntimeError("No Groq models available.")
    for model in GROQ_MODELS:
        try:
            r = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return r.choices[0].message.content or ""
        except Exception as e:
            last_err = e
            if "429" in str(e) or "rate_limit" in str(e).lower():
                continue
            raise
    raise last_err


class NotesGenerator:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("AI_PROVIDER", "none").lower()

    def generate_auto_notes(self, transcript: str, title: str = "") -> list[str]:
        """Generate structured study notes from transcript."""
        if not transcript.strip():
            return []

        if self.provider in ("anthropic", "openai", "groq"):
            notes = self._ai_notes(transcript, title)
            if notes:
                return notes

        return self._basic_notes(transcript)

    def _ai_notes(self, transcript: str, title: str) -> list[str]:
        prompt = f"""You are a learning assistant. From the transcript below, extract:
- Key concepts and definitions
- Important facts and figures
- Action items or things to remember
- Questions worth thinking about

Format as bullet points starting with '- '.

Video: {title}\n\nTranscript (first 5000 chars):\n{transcript[:5000]}"""
        try:
            raw_text: str = ""

            if self.provider == "anthropic":
                import anthropic
                from anthropic.types import TextBlock
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                msg = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        raw_text = block.text
                        break

            elif self.provider == "openai":
                from openai import OpenAI  # type: ignore[import-untyped]
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                raw_text = r.choices[0].message.content or ""

            elif self.provider == "groq":
                raw_text = _groq_chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )

            if not raw_text:
                return []

            return [
                line.strip()[1:].strip()
                for line in raw_text.split("\n")
                if line.strip().startswith("-")
            ]
        except Exception:
            return []

    def _basic_notes(self, transcript: str) -> list[str]:
        """Fallback: extract longer sentences as study points."""
        sentences = [s.strip() for s in transcript.split(".") if len(s.strip()) > 60]
        return [s + "." for s in sentences[:8]]
