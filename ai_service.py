import logging
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from groq import AsyncGroq

from config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

_gemini_model = None
_groq_client = None

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


def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            genai.configure(api_key=GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    return _gemini_model


def _get_groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set")
        _groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    return _groq_client


async def _gemini_summary(prompt: str) -> str:
    model = _get_gemini()
    response = await model.generate_content_async(prompt)
    return response.text.strip()


async def _groq_summary(prompt: str) -> str:
    client = _get_groq()
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


async def generate_summary(entries_text: str) -> str:
    prompt = _PROMPT.format(entries=entries_text)
    try:
        return await _gemini_summary(prompt)
    except Exception as e:
        logger.warning("Gemini failed (%s) — falling back to Groq", e)
        return await _groq_summary(prompt)
