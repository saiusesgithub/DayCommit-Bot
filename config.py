import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "daycommit.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "daycommit-backups")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_MODELS = os.getenv("OPENROUTER_MODELS", "") or OPENROUTER_MODEL
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
ALLOW_RAW_PUSH_WITHOUT_AI = os.getenv("ALLOW_RAW_PUSH_WITHOUT_AI", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set. Add it to your .env file.")
