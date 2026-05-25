# DayCommit

DayCommit is a polling-mode Telegram bot for daily developer journaling. It stores journal entries in SQLite, generates AI summaries, previews Daily DevLog markdown, and can push the final DevLog to GitHub.

## Local Run

```powershell
pip install -r requirements.txt
copy .env.example .env
python main.py
```

The bot intentionally uses polling mode through `app.run_polling()` in `main.py`. There is no webhook setup yet.

## Railway Deployment

Use a Railway worker process, not a web service.

1. Create a new Railway project from this repository.
2. Add a persistent volume mounted at `/data`.
3. Set the start command through the included `Procfile`:

```text
worker: python main.py
```

4. Add these Railway variables:

```env
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
GEMINI_API_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_MODEL=gemini-3.5-flash
GITHUB_TOKEN=...
GITHUB_OWNER=...
GITHUB_REPO=...
GITHUB_BRANCH=main
DB_PATH=/data/daycommit.db
TIMEZONE=Asia/Kolkata
```

`DB_PATH=/data/daycommit.db` is recommended on Railway so the SQLite database is stored on the mounted volume and survives redeploys. For local development, `DB_PATH=daycommit.db` is fine.

Do not commit `.env`, `.db`, `.sqlite`, or `.sqlite3` files. They are ignored by `.gitignore`.

AI summaries use provider fallback in this order: OpenRouter, then Groq, then Gemini. Set at least one provider API key for `/summary`.

## Commands

- `/today` - Show today's logs
- `/yesterday` - Show yesterday's logs
- `/summary` - Generate and save today's AI summary
- `/preview` - Preview the final Daily DevLog markdown
- `/push` - Push today's DevLog to GitHub
- `/delete_last` - Delete the most recent log entry
