import logging
import warnings
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from groq import AsyncGroq

from config import (
    CEREBRAS_API_KEY,
    CEREBRAS_BASE_URL,
    CEREBRAS_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_MODELS,
)

logger = logging.getLogger(__name__)

_OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_gemini_model = None
_groq_client = None

ProviderFn = Callable[[str], Awaitable[str]]
_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompts" / "daily_summary_template.md"
_DIARY_PLACEHOLDER = "{{DIARY_TEXT}}"

_DEFAULT_PROMPT_TEMPLATE = """\
You are a personal developer journal assistant.
Analyze these raw journal entries from today and produce a concise structured summary.

Raw entries:
{{DIARY_TEXT}}

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


class ProviderUnavailable(RuntimeError):
    pass


def _safe_error(exc: Exception) -> str:
    """Return a short error string that avoids keys, URLs, and request payloads."""
    status_code = getattr(exc, "status_code", None)
    message = ""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        message = _response_error_message(exc.response)

    if status_code:
        suffix = f" message={message}" if message else ""
        return f"status={status_code}{suffix}"

    if isinstance(exc, RuntimeError) and str(exc):
        return _short_message(str(exc))

    return exc.__class__.__name__


def _short_message(message: str, limit: int = 120) -> str:
    safe = " ".join(message.replace("\n", " ").split())
    return safe[:limit]


def _response_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return _short_message(response.reason_phrase)

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code")
            if message:
                return _short_message(str(message))
        if isinstance(error, str):
            return _short_message(error)
        message = data.get("message")
        if message:
            return _short_message(str(message))

    return _short_message(response.reason_phrase)


def _require(value: str, name: str) -> str:
    if not value:
        raise ProviderUnavailable(f"{name} not set")
    return value


def _model_list(raw_models: str) -> list[str]:
    return [model.strip() for model in raw_models.split(",") if model.strip()]


def _load_prompt_template() -> str:
    try:
        template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Prompt template missing; using built-in default")
        return _DEFAULT_PROMPT_TEMPLATE

    if _DIARY_PLACEHOLDER not in template:
        logger.warning("Prompt template missing diary placeholder; using built-in default")
        return _DEFAULT_PROMPT_TEMPLATE

    return template


def _build_prompt(entries_text: str) -> str:
    template = _load_prompt_template()
    return template.replace(_DIARY_PLACEHOLDER, entries_text)


async def _openrouter_summary(prompt: str) -> str:
    api_key = _require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    models = _model_list(_require(OPENROUTER_MODELS, "OPENROUTER_MODELS"))
    if not models:
        raise ProviderUnavailable("OPENROUTER_MODELS not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for model in models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(_OPENROUTER_CHAT_URL, headers=headers, json=payload)
                response.raise_for_status()

            return _content_from_chat_response(response.json(), "OpenRouter")
        except Exception as exc:
            last_error = exc
            logger.warning("OpenRouter model failed: %s", _safe_error(exc))

    raise RuntimeError(
        f"OpenRouter failed after {len(models)} configured model(s): "
        f"{_safe_error(last_error) if last_error else 'no models attempted'}"
    )


async def _cerebras_summary(prompt: str) -> str:
    api_key = _require(CEREBRAS_API_KEY, "CEREBRAS_API_KEY")
    model = _require(CEREBRAS_MODEL, "CEREBRAS_MODEL")
    base_url = _require(CEREBRAS_BASE_URL, "CEREBRAS_BASE_URL").rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()

    return _content_from_chat_response(response.json(), "Cerebras")


def _content_from_chat_response(data: dict, provider_name: str) -> str:
    content = data["choices"][0]["message"]["content"].strip()
    if not content:
        raise RuntimeError(f"{provider_name} returned empty content")
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
    prompt = _build_prompt(entries_text)
    return await generate_from_prompt(prompt)


async def generate_from_prompt(prompt: str) -> str:
    providers: tuple[tuple[str, ProviderFn], ...] = (
        ("OpenRouter", _openrouter_summary),
        ("Cerebras", _cerebras_summary),
        ("Groq", _groq_summary),
        ("Gemini", _gemini_summary),
    )

    for provider_name, provider_fn in providers:
        try:
            return await provider_fn(prompt)
        except ProviderUnavailable:
            continue
        except Exception as exc:
            logger.warning("%s provider failed: %s", provider_name, _safe_error(exc))

    raise RuntimeError(
        "Failed to generate summary. Check AI provider keys/models in .env and try again."
    )
