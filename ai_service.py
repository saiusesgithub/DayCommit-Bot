import logging
import warnings
from collections.abc import Awaitable, Callable

import httpx

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from groq import AsyncGroq

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL,
)

logger = logging.getLogger(__name__)

_OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_gemini_model = None
_groq_client = None

ProviderFn = Callable[[str], Awaitable[str]]

_PROMPT = """\
You are a personal developer journal assistant.
Analyze these raw journal entries from today and produce a concise structured summary.

Raw entries:
{entries}

Respond with exactly this Markdown (no extra text before or after):

**One-line summary:** <one sentence>

### Detailed Summary
<2-3 sentences>

### Timeline
- <event>

### Time Allocation
- <category>: <rough duration>

### Wins
- <win>

### Wasted Time / Distractions
- <item> (or: None identified)

### Improvements for Tomorrow
- <action>

### Tags
`tag1` `tag2` `tag3`
"""


def _safe_error(exc: Exception) -> str:
    """Return a short error string that avoids keys, URLs, and request payloads."""
    status_code = getattr(exc, "status_code", None)
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code

    if status_code:
        return f"{exc.__class__.__name__} status={status_code}"

    if isinstance(exc, RuntimeError):
        return str(exc)

    return exc.__class__.__name__


def _require(value: str, name: str) -> str:
    if not value:
        raise RuntimeError(f"{name} not set")
    return value


async def _openrouter_summary(prompt: str) -> str:
    api_key = _require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    model = _require(OPENROUTER_MODEL, "OPENROUTER_MODEL")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_OPENROUTER_CHAT_URL, headers=headers, json=payload)
        response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    if not content:
        raise RuntimeError("OpenRouter returned empty content")
    return content


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=_require(GROQ_API_KEY, "GROQ_API_KEY"))
    return _groq_client


async def _groq_summary(prompt: str) -> str:
    client = _get_groq()
    response = await client.chat.completions.create(
        model=_require(GROQ_MODEL, "GROQ_MODEL"),
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content.strip()
    if not content:
        raise RuntimeError("Groq returned empty content")
    return content


def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        _require(GEMINI_API_KEY, "GEMINI_API_KEY")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            genai.configure(api_key=GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel(_require(GEMINI_MODEL, "GEMINI_MODEL"))
    return _gemini_model


async def _gemini_summary(prompt: str) -> str:
    model = _get_gemini()
    response = await model.generate_content_async(prompt)
    content = response.text.strip()
    if not content:
        raise RuntimeError("Gemini returned empty content")
    return content


async def generate_summary(entries_text: str) -> str:
    prompt = _PROMPT.format(entries=entries_text)
    providers: tuple[tuple[str, ProviderFn], ...] = (
        ("OpenRouter", _openrouter_summary),
        ("Groq", _groq_summary),
        ("Gemini", _gemini_summary),
    )

    for provider_name, provider_fn in providers:
        try:
            return await provider_fn(prompt)
        except Exception as exc:
            logger.warning("%s provider failed: %s", provider_name, _safe_error(exc))

    raise RuntimeError(
        "Failed to generate summary. Check AI provider keys/models in .env and try again."
    )
