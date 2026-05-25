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
BACKUP_DIR=daycommit-backups
TIMEZONE=Asia/Kolkata
```

`DB_PATH=/data/daycommit.db` is recommended on Railway so the SQLite database is stored on the mounted volume and survives redeploys. For local development, `DB_PATH=daycommit.db` is fine.

Do not commit `.env`, `.db`, `.sqlite`, or `.sqlite3` files. They are ignored by `.gitignore`.

AI summaries use provider fallback in this order: OpenRouter, then Groq, then Gemini. Set at least one provider API key for `/summary`.

The `/summary` prompt style is editable in `prompts/daily_summary_template.md`. Keep the `{{DIARY_TEXT}}` placeholder in that file; DayCommit replaces it with the combined journal entries at runtime. If the template file is missing, the bot falls back to a built-in safe summary prompt.

Final DevLog files keep AI output and raw logs separate. AI generates only the summary; the `# Rough Journal (Raw Logs)` section is appended directly from stored Telegram messages with original order and line breaks preserved.

## Commands

- `/today` - Show today's logs
- `/status` - Show today's log count, summary state, GitHub push state, last push, and writing streak
- `/history YYYY-MM-DD` - Show logs for a specific date
- `/week` - Generate a weekly AI review for the last 7 local dates
- `/yesterday` - Show yesterday's logs
- `/summary` - Generate and save today's AI summary
- `/regenerate` - Regenerate and overwrite today's AI summary
- `/edit_summary` - Send today's saved summary back for manual editing
- `/preview` - Send the final Daily DevLog as `devlog_YYYY-MM-DD.md`
- `/push` - Push today's DevLog to GitHub
- `/backup` - Create a manual SQLite backup in `BACKUP_DIR`
- `/delete_last` - Delete the most recent log entry
- `/undo` - Undo the latest journal add/delete action
- `/cancel` - Cancel summary editing mode

DayCommit schedules a daily 11:00 PM reminder in the configured `TIMEZONE`: `Want to finish today's DevLog? /summary /preview /push`. It only sends to users who logged something that day.
