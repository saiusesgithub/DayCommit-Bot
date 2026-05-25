import warnings
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from config import GEMINI_API_KEY

_model = None

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


def _get_model() -> genai.GenerativeModel:
    global _model
    if _model is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            genai.configure(api_key=GEMINI_API_KEY)
            _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model


async def generate_summary(entries_text: str) -> str:
    model = _get_model()
    response = await model.generate_content_async(
        _PROMPT.format(entries=entries_text)
    )
    return response.text.strip()
