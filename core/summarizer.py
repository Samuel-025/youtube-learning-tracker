"""AI-powered and fallback summarizer — bullets + paragraph + Q&A."""

import os
import re
from typing import Optional

from core import groq_chat  # centralised Groq cascade

# Strip timestamp markers like [MM:SS], [H:MM:SS], [HH:MM:SS]
_TIMESTAMP_RE = re.compile(r"\[\d+:\d{2}(?::\d{2})?\]\s*")


class Summarizer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("AI_PROVIDER", "none").lower()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def summarize(self, transcript: str, title: str = "") -> tuple[list, str]:
        """Returns (bullet_points: list[str], paragraph: str)."""
        if not transcript.strip():
            return [], "No transcript available to summarize."

        dispatch = {
            "anthropic": self._summarize_anthropic,
            "openai":    self._summarize_openai,
            "groq":      self._summarize_groq,
        }
        fn = dispatch.get(self.provider)
        return fn(transcript, title) if fn else self._summarize_basic(transcript)

    def answer_question(self, transcript: str, question: str, title: str = "") -> str:
        """Answer a question using transcript context."""
        if not transcript.strip():
            return "No transcript available to answer questions."

        prompt = self._build_qa_prompt(transcript, question, title)

        try:
            if self.provider == "groq":
                return groq_chat([{"role": "user", "content": prompt}], max_tokens=512) or "No answer returned."

            elif self.provider == "openai":
                from openai import OpenAI  # type: ignore[import-untyped]
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                )
                return r.choices[0].message.content or "No answer returned."

            elif self.provider == "anthropic":
                import anthropic  # type: ignore[import-untyped]
                from anthropic.types import TextBlock
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                msg = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        return block.text
                return "No answer returned."

            else:
                return self._basic_qa(transcript, question)

        except Exception as exc:
            return f"Could not answer: {exc}"

    # ------------------------------------------------------------------ #
    #  Provider implementations                                           #
    # ------------------------------------------------------------------ #

    def _summarize_anthropic(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            import anthropic  # type: ignore[import-untyped]
            from anthropic.types import TextBlock
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in message.content:
                if isinstance(block, TextBlock):
                    text = block.text
                    break
            return self._parse_response(text) if text else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    def _summarize_openai(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            content = r.choices[0].message.content
            return self._parse_response(content) if content else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    def _summarize_groq(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            prompt = self._build_prompt(transcript, title)
            content = groq_chat([{"role": "user", "content": prompt}], max_tokens=1024)
            return self._parse_response(content) if content else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    # ------------------------------------------------------------------ #
    #  Prompt builders                                                     #
    # ------------------------------------------------------------------ #

    def _clean_transcript(self, transcript: str) -> str:
        return _TIMESTAMP_RE.sub("", transcript)

    def _build_prompt(self, transcript: str, title: str) -> str:
        max_chars = 6000
        clean = self._clean_transcript(transcript)
        trimmed = clean[:max_chars] + ("..." if len(clean) > max_chars else "")
        return (
            "You are a helpful learning assistant. Given the transcript below, provide:\n"
            "1. BULLETS: 5-7 concise key takeaway bullet points (start each with '- ')\n"
            "2. PARAGRAPH: A 3-4 sentence summary paragraph\n\n"
            f"Video title: {title}\n\nTranscript:\n{trimmed}\n\n"
            "Respond in this exact format:\n"
            "BULLETS:\n- point one\n- point two\n...\n\nPARAGRAPH:\nYour paragraph summary here."
        )

    def _build_qa_prompt(self, transcript: str, question: str, title: str) -> str:
        max_chars = 5000
        clean = self._clean_transcript(transcript)
        return (
            "You are a helpful learning assistant. Answer the question based ONLY on the "
            "transcript below. If the answer is not in the transcript, say so clearly.\n\n"
            f"Video: {title}\nTranscript: {clean[:max_chars]}\n\nQuestion: {question}\nAnswer:"
        )

    # ------------------------------------------------------------------ #
    #  Response parsing & fallbacks                                        #
    # ------------------------------------------------------------------ #

    def _parse_response(self, text: str) -> tuple[list, str]:
        """Parse the structured BULLETS / PARAGRAPH response from the AI.

        fix #7: track a dedicated 'in_paragraph' flag so stray lines after
        the paragraph section (e.g. extra bullets from a non-conforming model)
        are not appended to the paragraph string.
        """
        bullets: list[str] = []
        para_lines: list[str] = []
        mode = None

        for line in text.strip().split("\n"):
            stripped = line.strip()
            if stripped.upper().startswith("BULLETS:"):
                mode = "bullets"
            elif stripped.upper().startswith("PARAGRAPH:"):
                mode = "paragraph"
                # Inline paragraph text on the same line as the header
                inline = stripped[len("PARAGRAPH:"):].strip()
                if inline:
                    para_lines.append(inline)
            elif mode == "bullets" and stripped.startswith("-"):
                bullets.append(stripped[1:].strip())
            elif mode == "paragraph":
                # fix #7: stop collecting paragraph lines when we hit a new
                # section marker or a bullet point (model formatting drift)
                if stripped.upper().startswith("BULLETS:") or stripped.startswith("-"):
                    mode = None  # stop collecting
                elif stripped:
                    para_lines.append(stripped)

        paragraph = " ".join(para_lines).strip()
        return bullets, paragraph

    def _basic_qa(self, transcript: str, question: str) -> str:
        clean    = self._clean_transcript(transcript)
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        sentences = [s.strip() for s in clean.split(".") if s.strip()]
        matches  = [s for s in sentences if any(k in s.lower() for k in keywords)]
        if matches:
            return ". ".join(matches[:3]) + "."
        return (
            "No relevant answer found in the transcript. "
            "Add a Groq/OpenAI/Anthropic key in .env for AI-powered answers."
        )

    def _summarize_basic(self, transcript: str) -> tuple[list, str]:
        clean     = self._clean_transcript(transcript)
        sentences = [s.strip() for s in clean.replace("\n", " ").split(".") if len(s.strip()) > 30]
        bullets   = [s + "." for s in sentences[:5]]
        paragraph = " ".join(sentences[:3]) + "."
        return bullets, paragraph
