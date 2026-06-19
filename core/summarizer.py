"""AI-powered and fallback summarizer — bullets + paragraph."""

import os
from typing import Optional


class Summarizer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("AI_PROVIDER", "none").lower()

    def summarize(self, transcript: str, title: str = "") -> tuple[list, str]:
        """
        Returns (bullet_points: list[str], paragraph: str)
        Tries AI first, falls back to basic extraction.
        """
        if not transcript.strip():
            return [], "No transcript available to summarize."

        if self.provider == "anthropic":
            return self._summarize_anthropic(transcript, title)
        elif self.provider == "openai":
            return self._summarize_openai(transcript, title)
        elif self.provider == "groq":
            return self._summarize_groq(transcript, title)
        else:
            return self._summarize_basic(transcript)

    def _summarize_anthropic(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return self._parse_response(message.content[0].text)
        except Exception as e:
            return self._summarize_basic(transcript)

    def _summarize_openai(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception:
            return self._summarize_basic(transcript)

    def _summarize_groq(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            from groq import Groq
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception:
            return self._summarize_basic(transcript)

    def _build_prompt(self, transcript: str, title: str) -> str:
        # Trim transcript to avoid token limits
        max_chars = 6000
        trimmed = transcript[:max_chars] + ("..." if len(transcript) > max_chars else "")
        return f"""You are a helpful learning assistant. Given the transcript below, provide:
1. BULLETS: 5-7 concise key takeaway bullet points (start each with '- ')
2. PARAGRAPH: A 3-4 sentence summary paragraph

Video title: {title}

Transcript:
{trimmed}

Respond in this exact format:
BULLETS:
- point one
- point two
...

PARAGRAPH:
Your paragraph summary here."""

    def _parse_response(self, text: str) -> tuple[list, str]:
        bullets = []
        paragraph = ""
        lines = text.strip().split("\n")
        mode = None
        for line in lines:
            if line.strip().startswith("BULLETS:"):
                mode = "bullets"
            elif line.strip().startswith("PARAGRAPH:"):
                mode = "paragraph"
            elif mode == "bullets" and line.strip().startswith("-"):
                bullets.append(line.strip()[1:].strip())
            elif mode == "paragraph" and line.strip():
                paragraph += " " + line.strip()
        return bullets, paragraph.strip()

    def _summarize_basic(self, transcript: str) -> tuple[list, str]:
        """Fallback: extract first few sentences as a basic summary."""
        sentences = [s.strip() for s in transcript.replace("\n", " ").split(".") if len(s.strip()) > 30]
        bullets = [s + "." for s in sentences[:5]]
        paragraph = " ".join(sentences[:3]) + "."
        return bullets, paragraph
