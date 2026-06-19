"""
core package — shared constants and utilities.
"""

# ---------------------------------------------------------------------------
# Groq model cascade
# ---------------------------------------------------------------------------
# Models are tried in order. On HTTP 429 (rate-limited) the next model is
# attempted automatically.  Any other error surfaces immediately.
#
# Limits as of June 2026 (free tier):
#   llama-3.3-70b-versatile                      1 K RPD / 6 K RPM
#   meta-llama/llama-4-scout-17b-16e-instruct    1 K RPD / 500 RPM
#   llama-3.1-8b-instant                        14.4 K RPD / 14.4 K RPM
# ---------------------------------------------------------------------------
GROQ_MODELS: list[str] = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]


def groq_chat(messages: list, max_tokens: int) -> str:
    """
    Call Groq with model cascade.  Tries GROQ_MODELS in order,
    skipping to the next model on 429 / rate_limit errors.
    """
    import os
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
        except Exception as exc:
            last_err = exc
            if "429" in str(exc) or "rate_limit" in str(exc).lower() or "model_decommissioned" in str(exc).lower():
                continue
            raise

    raise last_err
