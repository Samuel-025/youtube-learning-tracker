"""Auto and manual notes management."""

import os
from typing import Optional


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
            if self.provider == "anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                msg = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = msg.content[0].text
            elif self.provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                text = r.choices[0].message.content
            elif self.provider == "groq":
                from groq import Groq
                client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                r = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024,
                )
                text = r.choices[0].message.content
            else:
                return []

            return [line.strip()[1:].strip() for line in text.split("\n") if line.strip().startswith("-")]
        except Exception:
            return []

    def _basic_notes(self, transcript: str) -> list[str]:
        """Fallback: extract longer sentences as study points."""
        sentences = [s.strip() for s in transcript.split(".") if len(s.strip()) > 60]
        return [s + "." for s in sentences[:8]]
