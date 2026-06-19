"""AI-powered and fallback summarizer — bullets + paragraph + Q&A."""

import os
from typing import Optional


class Summarizer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("AI_PROVIDER", "none").lower()

    def summarize(self, transcript: str, title: str = "") -> tuple[list, str]:
        """Returns (bullet_points: list[str], paragraph: str)."""
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

    def answer_question(self, transcript: str, question: str, title: str = "") -> str:
        """Answer a question based on transcript context."""
        if not transcript.strip():
            return "No transcript available to answer questions."

        prompt = self._build_qa_prompt(transcript, question, title)

        try:
            if self.provider == "groq":
                from groq import Groq  # type: ignore[import-untyped]
                client = Groq(api_key=os.getenv("GROQ_API_KEY"))
                r = client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=512,
                )
                return r.choices[0].message.content or "No answer returned."
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
                client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                msg = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=512,
                    messages=[{"role": "user", "content": prompt}],
                )
                # Only TextBlock has .text — cast after isinstance check
                for block in msg.content:
                    if hasattr(block, "text"):
                        return str(block.text)  # type: ignore[union-attr]
                return "No answer returned."
        except Exception as e:
            return f"Could not answer: {e}"

        return self._basic_qa(transcript, question)

    def _summarize_anthropic(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            import anthropic  # type: ignore[import-untyped]
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            # Filter to TextBlock only — ThinkingBlock/ToolUseBlock etc. have no .text
            text = ""
            for block in message.content:
                if hasattr(block, "text"):
                    text = str(block.text)  # type: ignore[union-attr]
                    break
            return self._parse_response(text) if text else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    def _summarize_openai(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return self._parse_response(content) if content else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    def _summarize_groq(self, transcript: str, title: str) -> tuple[list, str]:
        try:
            from groq import Groq  # type: ignore[import-untyped]
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            prompt = self._build_prompt(transcript, title)
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            content = response.choices[0].message.content
            return self._parse_response(content) if content else self._summarize_basic(transcript)
        except Exception:
            return self._summarize_basic(transcript)

    def _build_prompt(self, transcript: str, title: str) -> str:
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

    def _build_qa_prompt(self, transcript: str, question: str, title: str) -> str:
        max_chars = 5000
        trimmed = transcript[:max_chars]
        return f"""You are a helpful learning assistant. Answer the question based ONLY on the transcript below.
If the answer is not in the transcript, say so clearly.

Video: {title}
Transcript: {trimmed}

Question: {question}
Answer:"""

    def _parse_response(self, text: str) -> tuple[list, str]:
        bullets: list[str] = []
        paragraph = ""
        lines = text.strip().split("\n")
        mode = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("BULLETS:"):
                mode = "bullets"
            elif stripped.startswith("PARAGRAPH:"):
                mode = "paragraph"
            elif mode == "bullets" and stripped.startswith("-"):
                bullets.append(stripped[1:].strip())
            elif mode == "paragraph" and stripped:
                paragraph += " " + stripped
        return bullets, paragraph.strip()

    def _basic_qa(self, transcript: str, question: str) -> str:
        """Very basic fallback: return transcript sentences containing question keywords."""
        keywords = [w.lower() for w in question.split() if len(w) > 3]
        sentences = [s.strip() for s in transcript.split(".") if s.strip()]
        matches = [s for s in sentences if any(k in s.lower() for k in keywords)]
        if matches:
            return ". ".join(matches[:3]) + "."
        return "Could not find a relevant answer in the transcript. Try adding an AI provider key in .env."

    def _summarize_basic(self, transcript: str) -> tuple[list, str]:
        """Fallback: extract first few sentences as a basic summary."""
        sentences = [s.strip() for s in transcript.replace("\n", " ").split(".") if len(s.strip()) > 30]
        bullets = [s + "." for s in sentences[:5]]
        paragraph = " ".join(sentences[:3]) + "."
        return bullets, paragraph
