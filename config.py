import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "daycommit.db")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set. Add it to your .env file.")
